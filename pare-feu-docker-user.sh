#!/bin/sh
# Deuxième barrière (facultative) : filtre au niveau de la VM les ports publiés par Docker.
# Docker contourne ufw pour les ports des conteneurs ; la chaîne DOCKER-USER est l'endroit prévu
# par Docker pour ces règles (https://docs.docker.com/engine/network/firewall-iptables/).
# N'affecte PAS l'accès SSH à la VM (trafic local, pas transféré vers un conteneur).
#
# Usage :  sudo sh docker/pare-feu-docker-user.sh <interface> <plage1> [plage2 ...]
#   ex.  :  sudo sh docker/pare-feu-docker-user.sh ens160 10.21.4.0/24 10.80.0.0/16
# Retour arrière :  sudo iptables -F DOCKER-USER   (puis   sudo systemctl restart docker)
set -eu
[ "$#" -ge 2 ] || { echo "Usage : $0 <interface> <plage> [plage ...]"; exit 1; }
IF="$1"; shift
iptables -N DOCKER-USER 2>/dev/null || true
iptables -F DOCKER-USER
iptables -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
for P in "$@"; do
  iptables -A DOCKER-USER -i "$IF" -s "$P" -j RETURN
done
iptables -A DOCKER-USER -i "$IF" -j DROP
iptables -A DOCKER-USER -j RETURN
echo "Règles DOCKER-USER appliquées :"; iptables -L DOCKER-USER -n -v --line-numbers
