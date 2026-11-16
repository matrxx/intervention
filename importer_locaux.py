"""Import des locaux en ligne de commande (même règles que la page d'administration).

    python manage.py importer_locaux fichier.csv               # aperçu seulement
    python manage.py importer_locaux fichier.csv --appliquer   # import réel
    python manage.py importer_locaux fichier.csv --remplacer --appliquer
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from planning import import_locaux


class Command(BaseCommand):
    help = "Importe la liste des locaux depuis un fichier CSV."

    def add_arguments(self, parser):
        parser.add_argument("fichier")
        parser.add_argument("--remplacer", action="store_true", help="Désactive les salles absentes du fichier (pour les sites présents).")
        parser.add_argument("--appliquer", action="store_true", help="Sans cette option, affiche seulement l'aperçu.")

    def handle(self, fichier, remplacer=False, appliquer=False, **kw):
        p = Path(fichier)
        if not p.is_file():
            raise CommandError(f"Fichier introuvable : {p}")
        analyse = import_locaux.lire(import_locaux.decoder(p.read_bytes()), remplacer)
        for num, msg in analyse.erreurs:
            self.stderr.write(f"ligne {num} : {msg}")
        for site, st in analyse.stats.items():
            self.stdout.write(f"{site} : {st['total']} lignes · {st['nouvelles']} nouvelles · {st['modifiees']} modifiées · "
                              f"{st['inchangees']} inchangées · {st['desactivees']} à désactiver")
        if analyse.zones_nouvelles:
            self.stdout.write("Zones créées : " + ", ".join(analyse.zones_nouvelles))
        if not analyse.valide:
            raise CommandError("Import annulé : corrigez les erreurs ci-dessus.")
        if appliquer:
            import_locaux.appliquer(analyse, remplacer)
            self.stdout.write(self.style.SUCCESS("Import appliqué."))
        else:
            self.stdout.write("Aperçu uniquement : relancez avec --appliquer pour importer.")
