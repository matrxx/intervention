"""Import / export de la liste des locaux au format CSV.

Colonnes (l'ordre est libre, les intitulés sont lus sans tenir compte des majuscules ni des accents) :
    site ; zone ; zone_nom ; niveau ; ordre_niveau ; code ; libelle ; active
Obligatoires : site, zone, niveau, code.
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.db import transaction

from .models import Salle, Site, Zone

COLONNES = ["site", "zone", "zone_nom", "niveau", "ordre_niveau", "code", "libelle", "active"]
OBLIGATOIRES = ["site", "zone", "niveau", "code"]
ALIAS = {
    "aile": "zone", "batiment": "zone", "zone_code": "zone", "aile_nom": "zone_nom", "nom_zone": "zone_nom",
    "salle": "code", "code_salle": "code", "salle_code": "code", "libelle_salle": "libelle", "nom": "libelle",
    "actif": "active", "ordre": "ordre_niveau", "site_code": "site",
}
TAILLE_MAX = 2 * 1024 * 1024


def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").strip().lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def ordre_devine(niveau):
    n = _norm(niveau)
    if "sous_sol" in n or n.startswith("ss") or n.startswith("-"):
        return -1
    if n in ("rdc", "rez_de_chaussee") or n.startswith("rdc"):
        return 0
    if "entresol" in n or "mezzanine" in n:
        return 1
    m = re.match(r"(\d+)", n)
    if m:
        return 1 + int(m.group(1))
    return 50


def _bool(v):
    v = _norm(v)
    if v in ("", "oui", "o", "1", "true", "vrai", "x", "yes", "active", "actif"):
        return True
    if v in ("non", "n", "0", "false", "faux", "no", "inactive", "inactif"):
        return False
    return None


def decoder(contenu: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return contenu.decode(enc)
        except UnicodeDecodeError:
            continue
    return contenu.decode("latin-1")


@dataclass
class Analyse:
    lignes: list = field(default_factory=list)       # dict normalisés
    erreurs: list = field(default_factory=list)      # (n° de ligne, message)
    stats: dict = field(default_factory=dict)        # code site -> compteurs
    zones_nouvelles: list = field(default_factory=list)

    @property
    def valide(self):
        return not self.erreurs and bool(self.lignes)


def lire(texte: str, remplacer: bool) -> Analyse:
    res = Analyse()
    echantillon = texte[:4096]
    try:
        dialecte = csv.Sniffer().sniff(echantillon, delimiters=";,\t")
        sep = dialecte.delimiter
    except csv.Error:
        sep = ";"
    lecteur = csv.reader(io.StringIO(texte), delimiter=sep)
    try:
        entete = next(lecteur)
    except StopIteration:
        res.erreurs.append((1, "Le fichier est vide."))
        return res
    cles = [ALIAS.get(_norm(c), _norm(c)) for c in entete]
    manquantes = [c for c in OBLIGATOIRES if c not in cles]
    if manquantes:
        res.erreurs.append((1, "Colonnes obligatoires absentes : " + ", ".join(manquantes)
                            + ". Intitulés attendus : " + " ; ".join(COLONNES)))
        return res

    sites = {s.code: s for s in Site.objects.all()}
    vus = {}
    for num, valeurs in enumerate(lecteur, start=2):
        if not any(v.strip() for v in valeurs):
            continue
        if valeurs and valeurs[0].strip().startswith("#"):
            continue  # ligne de commentaire
        brut = {cles[i]: (valeurs[i].strip() if i < len(valeurs) else "") for i in range(len(cles))}
        site_code = _norm(brut.get("site")).replace("_", "-")
        code = brut.get("code", "").upper().replace(" ", "")
        ligne = {
            "num": num, "site": site_code, "zone": brut.get("zone", "").upper(), "zone_nom": brut.get("zone_nom", ""),
            "niveau": brut.get("niveau", ""), "code": code, "libelle": brut.get("libelle", ""),
        }
        if site_code not in sites:
            res.erreurs.append((num, f"site « {brut.get('site')} » inconnu (sites existants : {', '.join(sites) or 'aucun'})"))
            continue
        for c in OBLIGATOIRES:
            if not ligne[c]:
                res.erreurs.append((num, f"la colonne « {c} » est vide"))
                break
        else:
            o = brut.get("ordre_niveau", "")
            if o:
                try:
                    ligne["ordre_niveau"] = int(o)
                except ValueError:
                    res.erreurs.append((num, f"ordre_niveau « {o} » n'est pas un nombre entier"))
                    continue
            else:
                ligne["ordre_niveau"] = ordre_devine(ligne["niveau"])
            act = _bool(brut.get("active", ""))
            if act is None:
                res.erreurs.append((num, f"active « {brut.get('active')} » : indiquez oui ou non"))
                continue
            ligne["active"] = act
            if len(code) > 30 or len(ligne["libelle"]) > 150 or len(ligne["niveau"]) > 40 or len(ligne["zone"]) > 20:
                res.erreurs.append((num, "une valeur dépasse la longueur autorisée (code 30, libellé 150, niveau 40, zone 20)"))
                continue
            cle = (site_code, code)
            if cle in vus:
                res.erreurs.append((num, f"le code {code} apparaît déjà ligne {vus[cle]} pour ce site"))
                continue
            vus[cle] = num
            res.lignes.append(ligne)

    if not res.lignes and not res.erreurs:
        res.erreurs.append((2, "Aucune salle trouvée dans le fichier."))
    _comparer(res, sites, remplacer)
    return res


def _comparer(res, sites, remplacer):
    par_site = {}
    for l in res.lignes:
        par_site.setdefault(l["site"], []).append(l)
    for code_site, lignes in par_site.items():
        site = sites[code_site]
        existantes = {s.code: s for s in Salle.objects.filter(site=site).select_related("zone")}
        zones = {z.code for z in site.zones.all()}
        st = {"nouvelles": 0, "modifiees": 0, "inchangees": 0, "desactivees": 0, "total": len(lignes)}
        for l in lignes:
            if l["zone"] not in zones:
                zones.add(l["zone"])
                res.zones_nouvelles.append(f"{site.nom} · {site.libelle_zone} {l['zone']}")
            s = existantes.get(l["code"])
            if s is None:
                st["nouvelles"] += 1
            elif (s.zone.code, s.niveau, s.ordre_niveau, s.libelle, s.active) != (l["zone"], l["niveau"], l["ordre_niveau"], l["libelle"], l["active"]):
                st["modifiees"] += 1
            else:
                st["inchangees"] += 1
        if remplacer:
            codes = {l["code"] for l in lignes}
            st["desactivees"] = sum(1 for c, s in existantes.items() if c not in codes and s.active)
        res.stats[site.nom] = st


@transaction.atomic
def appliquer(res: Analyse, remplacer: bool):
    if not res.valide:
        raise ValueError("Import non valide")
    sites = {s.code: s for s in Site.objects.all()}
    par_site = {}
    for l in res.lignes:
        par_site.setdefault(l["site"], []).append(l)
    for code_site, lignes in par_site.items():
        site = sites[code_site]
        zones = {z.code: z for z in site.zones.all()}
        for ordre, l in enumerate(lignes):
            z = zones.get(l["zone"])
            if z is None:
                z = Zone.objects.create(site=site, code=l["zone"], nom=l["zone_nom"], ordre=len(zones))
                zones[z.code] = z
            elif l["zone_nom"] and z.nom != l["zone_nom"]:
                z.nom = l["zone_nom"]
                z.save(update_fields=["nom"])
            Salle.objects.update_or_create(
                site=site, code=l["code"],
                defaults={"zone": z, "niveau": l["niveau"], "ordre_niveau": l["ordre_niveau"],
                          "libelle": l["libelle"], "active": l["active"]},
            )
        if remplacer:
            codes = {l["code"] for l in lignes}
            Salle.objects.filter(site=site, active=True).exclude(code__in=codes).update(active=False)


def exporter(sites):
    sortie = io.StringIO()
    sortie.write("﻿")  # BOM : Excel ouvre correctement les accents
    w = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    w.writerow(COLONNES)
    for s in Salle.objects.filter(site__in=sites).select_related("site", "zone"):
        w.writerow([s.site.code, s.zone.code, s.zone.nom, s.niveau, s.ordre_niveau, s.code, s.libelle, "oui" if s.active else "non"])
    return sortie.getvalue()
