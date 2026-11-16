"""Crée les données de référence si elles n'existent pas (sans rien écraser).

    python manage.py initialiser             # sites, types, locaux de Versailles
    python manage.py initialiser --exemples  # + quelques interventions d'exemple sur la semaine en cours
"""
import datetime as dt
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from planning import import_locaux
from planning.models import Intervention, Salle, Site, TypeIntervention, Utilisateur, Zone

SITES = [
    dict(code="versailles", nom="Versailles", nom_long="Petites Écuries du Roi", libelle_zone="Aile", couleur="#1d4b87", ordre=1),
    dict(code="louvre", nom="Paris · Louvre", nom_long="Palais du Louvre", libelle_zone="Zone", couleur="#a0522d", ordre=2),
]
TYPES = [
    ("reunion", "Réunion / Visite groupe", "#0e8fa3"),
    ("fermeture", "Fermeture congés", "#6b7280"),
    ("travaux", "Travaux", "#e0761c"),
    ("maintenance", "Maintenance", "#2d6cdf"),
    ("oeuvres", "Arrivée/départ d’œuvres", "#b58a12"),
    ("vernissage", "Vernissage", "#8b5a2b"),
    ("tournage", "Tournage / Reportage", "#8a4fd1"),
    ("photoradio", "Séance photo/radio", "#4c8c2b"),
    ("laser", "Microsablage / Laser", "#c0392b"),
]


class Command(BaseCommand):
    help = "Initialise les sites, types d'intervention et locaux de Versailles (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--exemples", action="store_true", help="Ajoute des interventions d'exemple sur la semaine en cours.")

    def handle(self, *args, exemples=False, **kw):
        for s in SITES:
            _, cree = Site.objects.get_or_create(code=s["code"], defaults=s)
            if cree:
                self.stdout.write(f"Site créé : {s['nom']}")
        for i, (code, nom, coul) in enumerate(TYPES):
            _, cree = TypeIntervention.objects.get_or_create(code=code, defaults=dict(nom=nom, couleur=coul, ordre=i))
            if cree:
                self.stdout.write(f"Type créé : {nom}")
        versailles = Site.objects.get(code="versailles")
        if not Salle.objects.filter(site=versailles).exists():
            fichier = Path(__file__).resolve().parents[2] / "data" / "locaux_versailles.csv"
            analyse = import_locaux.lire(import_locaux.decoder(fichier.read_bytes()), remplacer=False)
            if analyse.valide:
                import_locaux.appliquer(analyse, remplacer=False)
                self.stdout.write(f"{len(analyse.lignes)} salles de Versailles importées.")
            else:
                self.stderr.write(f"Import des locaux de Versailles impossible : {analyse.erreurs[:3]}")
        if exemples:
            self._exemples(versailles)
        self.stdout.write(self.style.SUCCESS("Initialisation terminée."))

    def _exemples(self, site):
        if Intervention.objects.filter(description__startswith="Exemple :").exists():
            self.stdout.write("Exemples déjà présents.")
            return
        auteur, _ = Utilisateur.objects.get_or_create(
            email="exemple.demonstration@culture.gouv.fr",
            defaults=dict(first_name="Exemple", last_name="DÉMONSTRATION", is_active=False),
        )
        lun = timezone.localdate() - dt.timedelta(days=timezone.localdate().weekday())
        T = {t.code: t for t in TypeIntervention.objects.all()}
        zg, zh = Zone.objects.get(site=site, code="G"), Zone.objects.get(site=site, code="H")
        h = lambda s: dt.time.fromisoformat(s)
        donnees = [
            dict(type=T["travaux"], description="Exemple : pose de pantographes, fin du chantier", portee="niveau", zone=zh,
                 niveau="1er étage", precision="Ateliers organique et inorganique", date_debut=lun, date_fin=lun + dt.timedelta(days=2),
                 heure_debut=h("08:00"), heure_fin=h("17:00"), entreprise="Entreprise de pose", proxyclick=True, visite_prevention=True, plan_prevention=True),
            dict(type=T["maintenance"], description="Exemple : maintenance annuelle de la CTA des réserves", portee="salles",
                 date_debut=lun + dt.timedelta(days=1), date_fin=lun + dt.timedelta(days=1), heure_debut=h("09:00"), heure_fin=h("12:00"),
                 protocole="Accompagnement obligatoire en réserve", proxyclick=True, _salles=["G205", "G206", "G207"]),
            dict(type=T["photoradio"], description="Exemple : campagne d'imagerie RX sur une peinture sur bois", portee="salles",
                 date_debut=lun + dt.timedelta(days=3), date_fin=lun + dt.timedelta(days=3), heure_debut=h("10:00"), heure_fin=h("16:00"),
                 protocole="Accès interdit pendant les tirs", _salles=["H208B", "H208D2"]),
            dict(type=T["oeuvres"], description="Exemple : arrivée d'œuvres, déchargement et constat d'état", portee="salles",
                 date_debut=lun + dt.timedelta(days=3), date_fin=lun + dt.timedelta(days=3), heure_debut=h("14:00"), heure_fin=h("17:00"),
                 proxyclick=True, _salles=["G011A", "G011B"]),
            dict(type=T["reunion"], description="Exemple : visite d'un groupe d'étudiants", portee="zone", zone=zg,
                 date_debut=lun + dt.timedelta(days=4), date_fin=lun + dt.timedelta(days=4), heure_debut=h("10:00"), heure_fin=h("12:00")),
        ]
        for d in donnees:
            codes = d.pop("_salles", [])
            iv = Intervention.objects.create(site=site, cree_par=auteur, hote=auteur.nom_complet, **d)
            if codes:
                iv.salles.set(Salle.objects.filter(site=site, code__in=codes))
        self.stdout.write(f"{len(donnees)} interventions d'exemple créées (supprimables depuis /gestion/).")
