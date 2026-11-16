# Interventions C2RMF

Application web qui remplace le tableau Excel hebdomadaire des interventions : chaque agent déclare une intervention (salle, niveau, aile ou tout le site), le calendrier de la semaine s'affiche sur un écran, avec une couleur par type d'intervention. Deux espaces séparés : Versailles (Petites Écuries du Roi) et Paris · Louvre.

- Installation sur la VM : [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Import de la liste des locaux : [docs/IMPORT_LOCAUX.md](docs/IMPORT_LOCAUX.md)

Pile : Django 5.2 LTS, PostgreSQL 17, Gunicorn, Nginx, Docker Compose.

| Dossier | Contenu |
|---|---|
| `config/` | Paramètres Django (tout ce qui varie se règle dans `.env`) |
| `planning/` | L'application : modèles, vues, gabarits, import CSV, filtrage IP, tests |
| `docker/` | Nginx, démarrage du conteneur, sauvegarde, pare-feu facultatif |
| `docs/` | Guides et fichiers CSV |
