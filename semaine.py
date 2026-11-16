"""Construction de la grille hebdomadaire (calendrier et écran)."""
import datetime as dt

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def lundi(d):
    return d - dt.timedelta(days=d.weekday())


def jour_long(d):
    return f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]}"


def libelle_semaine(debut, nb):
    fin = debut + dt.timedelta(days=nb - 1)
    if debut.month == fin.month:
        gauche = f"{JOURS[debut.weekday()]} {debut.day}"
    else:
        gauche = jour_long(debut) + (f" {debut.year}" if debut.year != fin.year else "")
    return f"du {gauche} au {jour_long(fin)} {fin.year}"


def grille(interventions, debut, nb, aujourd_hui):
    """Retourne (jours, couloirs).

    jours : une entrée par jour avec les interventions d'une journée et, pour l'affichage
            étroit ou l'écran, celles sur plusieurs jours (avec leur rang « jour k/n »).
    couloirs : interventions sur plusieurs jours placées en bandeaux (colonne début/fin, ligne).
    """
    fin = debut + dt.timedelta(days=nb - 1)
    jours = []
    for i in range(nb):
        d = debut + dt.timedelta(days=i)
        du_jour = [iv for iv in interventions if iv.date_debut <= d <= iv.date_fin]
        du_jour.sort(key=lambda iv: (not iv.journee_entiere, iv.heure_debut or dt.time(0)))
        jours.append({
            "date": d,
            "nom": JOURS[d.weekday()],
            "aujourdhui": d == aujourd_hui,
            "uniques": [iv for iv in du_jour if not iv.sur_plusieurs_jours],
            "multi": [(iv, (d - iv.date_debut).days + 1) for iv in du_jour if iv.sur_plusieurs_jours],
            "tous": [(iv, (d - iv.date_debut).days + 1) for iv in du_jour],
        })
    couloirs, fins = [], []
    multi = sorted([iv for iv in interventions if iv.sur_plusieurs_jours], key=lambda iv: iv.date_debut)
    for iv in multi:
        a = max(0, (iv.date_debut - debut).days)
        b = min(nb - 1, (iv.date_fin - debut).days)
        if a > nb - 1 or b < 0 or iv.date_fin < debut or iv.date_debut > fin:
            continue
        ligne = next((k for k, f in enumerate(fins) if f < a), None)
        if ligne is None:
            ligne = len(fins)
            fins.append(-1)
        fins[ligne] = b
        couloirs.append({"iv": iv, "col": a + 1, "colfin": b + 2, "ligne": ligne + 2})
    return jours, couloirs
