# Interventions C2RMF — installation en mode test sur la VM

Version de test (« mode dev ») de l'application de gestion des interventions, pour les sites de **Versailles** (Petites Écuries) et **Paris · Louvre**.

| Conteneur | Rôle | Exposé sur la VM |
|---|---|---|
| `nginx` | Proxy frontal, seul point d'entrée | port 80 (443 plus tard) |
| `web` | Application Django 5.2 LTS + Gunicorn | non (réseau interne seulement) |
| `db` | PostgreSQL 17 | non |
| `mailpit` | Boîte de réception de test : capte tous les e-mails | port 8025 (protégé par mot de passe) |

**Ce qui a été vérifié avant livraison** : 21 tests automatiques (comptes, droits, import CSV, filtrage IP) ; un parcours complet dans un navigateur, passant par Nginx, PostgreSQL et un vrai envoi SMTP : inscription, lien d'activation reçu, connexion, saisie, affichage sur l'écran ; le filtrage IP derrière Nginx (accepté puis refusé selon la plage, en-tête `X-Forwarded-For` falsifié ignoré).
**Ce qui n'a pas pu être vérifié** : la construction des conteneurs Docker eux-mêmes (le registre Docker Hub n'était pas joignable depuis l'environnement de développement) et le script de pare-feu `DOCKER-USER` (§ 7.2). Ces deux points sont à valider sur la VM.

---

## 1. Prérequis

- VM Ubuntu 24.04 LTS ou 26.04 LTS (versions prises en charge par Docker), 2 vCPU, 4 Go de RAM, 20 Go de disque libres, accès `sudo`.
- Le nom DNS attribué par la DSI, qui pointe vers l'adresse IP de la VM.
- Pendant l'installation, accès HTTPS sortant vers : `download.docker.com`, `registry-1.docker.io`, `production.cloudflare.docker.com`, `pypi.org`, `files.pythonhosted.org`. Si la VM sort par un proxy, voir § 11.

## 2. Installer Docker

Commandes de la documentation officielle (https://docs.docker.com/engine/install/ubuntu/) :

```bash
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world          # doit afficher « Hello from Docker! »
```

## 3. Copier l'application

Depuis votre poste (PowerShell), puis sur la VM :

```bash
scp interventions-c2rmf.zip <compte>@<IP_VM>:/tmp/            # depuis le poste
sudo apt install unzip                                         # sur la VM
sudo mkdir -p /opt/interventions && sudo unzip /tmp/interventions-c2rmf.zip -d /opt/interventions
cd /opt/interventions/interventions-c2rmf
```

## 4. Configurer

```bash
sudo cp .env.example .env
sudo chmod 600 .env
openssl rand -base64 48      # → coller dans DJANGO_SECRET_KEY
openssl rand -hex 24         # → coller dans POSTGRES_PASSWORD
sudo nano .env
```

À renseigner au minimum : `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (nom DNS et IP de la VM), `POSTGRES_PASSWORD`, `MAILPIT_MOT_DE_PASSE`. Laissez `RESEAUX_AUTORISES` vide pour le tout premier démarrage, puis renseignez-le (§ 7).

> `RESEAU_DOCKER` (172.31.250.0/24 par défaut) est le petit réseau privé entre Nginx et l'application. Ne le changez que s'il chevauche une plage utilisée sur le réseau du ministère.

## 5. Démarrer et créer le compte administrateur

```bash
sudo docker compose up -d --build        # première fois : 2 à 5 minutes
sudo docker compose ps                   # les 4 conteneurs doivent être « running » ou « healthy »
sudo docker compose logs web | tail -20  # « Initialisation terminée. » puis « Listening at: http://0.0.0.0:8000 »
sudo docker compose exec web python manage.py createsuperuser
```

`createsuperuser` demande l'adresse (prenom.nom@culture.gouv.fr), le prénom, le nom et le mot de passe. Ce compte est actif sans lien d'activation et a le rôle administrateur.

Ouvrez ensuite `http://<nom DNS>/` depuis votre poste.

| Adresse | Contenu |
|---|---|
| `http://<nom DNS>/` | Connexion (choix du site), puis calendrier de la semaine |
| `http://<nom DNS>/versailles/ecran/` | Écran d'affichage de Versailles, sans compte |
| `http://<nom DNS>/louvre/ecran/` | Écran d'affichage du Louvre |
| `http://<nom DNS>/versailles/administration/` | Administration : import des locaux, bandeau, types, comptes |
| `http://<nom DNS>/gestion/` | Administration avancée (toutes les tables) |
| `http://<nom DNS>:8025/` | Boîte de test Mailpit (identifiant et mot de passe du `.env`) |

Avec `DONNEES_EXEMPLE=1`, cinq interventions marquées « Exemple : » sont créées sur la semaine en cours, pour voir l'écran rempli. Pour les retirer : *Administration avancée → Interventions*, filtrer sur « Exemple », supprimer ; puis mettre `DONNEES_EXEMPLE=0`.

## 6. Messagerie

**En mode test**, tous les e-mails (activation de compte, mot de passe oublié) arrivent dans Mailpit, à `http://<nom DNS>:8025/`. Pour tester une inscription, créez un compte avec une adresse @culture.gouv.fr, puis ouvrez le lien dans Mailpit.

**Avec le compte générique Culture**, demandez à l'équipe messagerie :

1. le nom du serveur et le port (587 avec STARTTLS en général) ;
2. l'identifiant et le mot de passe du compte, et l'adresse d'expéditeur autorisée ;
3. **si ce compte est hébergé sur Microsoft 365** : l'envoi SMTP avec identifiant et mot de passe y est désactivé par défaut à partir de fin décembre 2026. Demandez s'il passe par un relais interne du ministère (aucun problème) ou par Exchange Online (il faudra alors une exception ou une autre méthode d'authentification) ;
4. que l'adresse IP de la VM soit autorisée sur le serveur, si celui-ci filtre les adresses.

Remplacez ensuite le bloc « MODE TEST » du `.env` par le bloc « MODE RÉEL », puis :

```bash
sudo docker compose up -d                                              # recharge la configuration
sudo docker compose exec web python manage.py sendtestemail prenom.nom@culture.gouv.fr
```

Le message de test doit arriver dans votre boîte. En cas d'erreur, le message s'affiche dans le terminal (authentification refusée, délai dépassé…). Quand la messagerie réelle fonctionne, supprimez le service `mailpit` de `docker-compose.yml` et fermez le port 8025.

## 7. Restreindre l'accès à des plages IP

### 7.1 Filtrage par l'application (à faire)

1. Relevez les plages des sites : réseau des postes de Versailles, du Louvre, plage du VPN, et l'adresse du poste d'affichage. Demandez-les à la DSI en notation CIDR (ex. `10.21.4.0/24`).
2. Éditez le fichier `.env` :
   ```
   RESEAUX_AUTORISES=10.21.4.0/24,10.21.5.0/24,10.80.0.0/16
   ```
   Séparez les plages par des virgules. Une adresse seule s'écrit `10.21.4.57/32` ou `10.21.4.57`.
3. Appliquez :
   ```bash
   sudo docker compose up -d
   ```
   Si une plage est mal écrite, l'application refuse de démarrer et le journal (`sudo docker compose logs web`) indique laquelle.
4. Contrôlez :
   - depuis un poste autorisé, la page de connexion s'affiche ;
   - depuis un poste hors plage, la page « Accès refusé » s'affiche et indique l'adresse vue par l'application ;
   - les refus sont journalisés : `sudo docker compose logs web | grep "Accès refusé"`.

**À savoir :**
- Testez depuis un poste, pas depuis la VM elle-même : vue de la VM, l'adresse source est celle du réseau Docker, qui n'est pas autorisée.
- Si un site arrive par une traduction d'adresses (NAT) sur le réseau du ministère, l'application voit l'adresse traduite, pas celle du poste. La page « Accès refusé » affiche l'adresse réellement vue : c'est celle-là qu'il faut autoriser.
- L'application lit l'adresse du client dans l'en-tête `X-Forwarded-For` uniquement quand la requête vient de Nginx. Nginx remplace cet en-tête : un poste ne peut pas se faire passer pour une adresse autorisée.
- Le chemin `/sante/` reste ouvert. Il ne renvoie que « ok » et sert au contrôle de santé du conteneur.

Retour arrière : videz `RESEAUX_AUTORISES=` puis `sudo docker compose up -d`.

### 7.2 Deuxième barrière au niveau de la VM (facultatif, à valider)

Docker ouvre ses ports publiés (80 et 8025) **sans passer par ufw**. Pour filtrer aussi au niveau du système, Docker prévoit la chaîne `DOCKER-USER` (https://docs.docker.com/engine/network/firewall-iptables/). Le script fourni n'agit que sur le trafic destiné aux conteneurs : l'accès SSH à la VM n'est pas concerné.

```bash
ip -br addr                                   # repérer l'interface réseau, ex. ens160
sudo sh docker/pare-feu-docker-user.sh ens160 10.21.4.0/24 10.21.5.0/24 10.80.0.0/16
```

Contrôles : un poste autorisé atteint l'application ; un poste hors plage n'obtient aucune réponse (délai dépassé), au lieu de la page « Accès refusé ».
Retour arrière : `sudo iptables -F DOCKER-USER`.

Ces règles disparaissent au redémarrage de la VM. Pour les rendre permanentes, créez `/etc/systemd/system/interventions-pare-feu.service` :

```ini
[Unit]
Description=Filtrage DOCKER-USER pour Interventions C2RMF
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/bin/sh /opt/interventions/interventions-c2rmf/docker/pare-feu-docker-user.sh ens160 10.21.4.0/24 10.21.5.0/24 10.80.0.0/16

[Install]
WantedBy=multi-user.target
```

puis `sudo systemctl daemon-reload && sudo systemctl enable --now interventions-pare-feu`. Vérifiez après un redémarrage de la VM : `sudo iptables -L DOCKER-USER -n -v`.

Ce script n'a pas pu être testé : appliquez-le d'abord quand la VM est joignable par sa console d'administration, en cas d'erreur.

## 8. Passer en HTTPS (quand la DSI fournit le certificat)

1. Déposez le certificat (avec la chaîne) et la clé dans `certs/interventions.crt` et `certs/interventions.key` (`sudo chmod 600 certs/interventions.key`).
2. `sudo cp docker/https.conf.exemple docker/https.conf`
3. Dans `docker-compose.yml`, service `nginx`, décommentez le port 443 et les deux montages `https.conf` et `certs`.
4. Dans `docker/nginx.conf`, décommentez `return 301 https://$host$request_uri;`.
5. Dans `.env` : `HTTPS_ACTIF=1`.
6. `sudo docker compose up -d`, puis vérifiez `https://<nom DNS>/`.

## 9. Importer la liste des locaux

Voir `docs/IMPORT_LOCAUX.md`. Les 116 salles de Versailles sont chargées au premier démarrage. Le Louvre est créé sans salle : on y saisit « Tout le site » jusqu'à l'import de ses locaux.

## 10. Exploitation courante

| Action | Commande (depuis `/opt/interventions/interventions-c2rmf`) |
|---|---|
| Voir les journaux | `sudo docker compose logs -f web` (ou `nginx`) |
| Redémarrer | `sudo docker compose restart` |
| Appliquer un changement du `.env` | `sudo docker compose up -d` |
| Mettre à jour l'application | remplacer les fichiers (sauf `.env`), puis `sudo docker compose up -d --build` |
| Sauvegarder la base | `sudo sh docker/sauvegarde.sh` (fichier dans `sauvegardes/`, conservé 30 jours) |
| Sauvegarde chaque nuit | `sudo crontab -e` puis `30 2 * * * cd /opt/interventions/interventions-c2rmf && sh docker/sauvegarde.sh` |
| Restaurer une sauvegarde (sur une base vide, après `sudo docker compose down -v` puis `up -d db`) | `gunzip -c sauvegardes/<fichier>.sql.gz \| sudo docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'` |
| Débloquer un compte | Administration → Comptes → vider « connexion bloquée jusqu'à » |
| Tests automatiques | `sudo docker compose exec web python manage.py test planning` |

Copiez régulièrement le dossier `sauvegardes/` sur un partage réseau : une sauvegarde restée sur la VM ne protège pas contre la perte de la VM.

## 11. Dépannage

- **« Bad Request (400) »** : le nom utilisé dans le navigateur n'est pas dans `DJANGO_ALLOWED_HOSTS`.
- **« Interdit (403) » à l'envoi d'un formulaire** : vous passez par une adresse inhabituelle (autre port, alias DNS) ; ajoutez-la à `DJANGO_CSRF_TRUSTED_ORIGINS`, ex. `http://interventions-alias.exemple`.
- **Page « Accès refusé »** : l'adresse affichée n'est dans aucune plage de `RESEAUX_AUTORISES` (§ 7.1).
- **La construction échoue (`pip`, `pull`)** : la VM n'atteint pas Internet directement. Si elle sort par un proxy, déclarez-le pour Docker. Dans `/etc/systemd/system/docker.service.d/http-proxy.conf` :
  ```ini
  [Service]
  Environment="HTTP_PROXY=http://<proxy>:<port>" "HTTPS_PROXY=http://<proxy>:<port>" "NO_PROXY=localhost,127.0.0.1"
  ```
  puis `sudo systemctl daemon-reload && sudo systemctl restart docker`. Pour la construction de l'image, dans `~/.docker/config.json` de l'utilisateur qui lance `docker compose` (`/root/.docker/config.json` avec `sudo`) :
  ```json
  { "proxies": { "default": { "httpProxy": "http://<proxy>:<port>", "httpsProxy": "http://<proxy>:<port>", "noProxy": "localhost,127.0.0.1" } } }
  ```
- **Aucun e-mail en mode réel** : `sudo docker compose exec web python manage.py sendtestemail <adresse>` affiche l'erreur du serveur de messagerie.
