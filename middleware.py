"""Filtrage des accès par plage IP (variable RESEAUX_AUTORISES du fichier .env).

Derrière Nginx, l'adresse vue par l'application est celle du proxy : on lit alors
l'en-tête X-Forwarded-For, mais seulement si la requête arrive d'une adresse listée
dans PROXYS_DE_CONFIANCE. Sans cette précaution, n'importe quel poste pourrait
falsifier l'en-tête pour se faire passer pour une adresse autorisée.
"""
import ipaddress
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

logger = logging.getLogger("planning.acces")


def _ip(texte):
    try:
        ip = ipaddress.ip_address(texte.strip())
    except ValueError:
        return None
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip


def _dans(ip, reseaux):
    return any(ip in r for r in reseaux if r.version == ip.version)


def ip_client(request):
    distante = _ip(request.META.get("REMOTE_ADDR", "")) or ipaddress.ip_address("0.0.0.0")
    proxys = settings.PROXYS_DE_CONFIANCE
    if proxys and _dans(distante, proxys):
        chaine = [p for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        # on remonte depuis la droite : la première adresse qui n'est pas un proxy de confiance est le client
        for part in reversed(chaine):
            ip = _ip(part)
            if ip is None:
                break
            if not _dans(ip, proxys):
                return ip
    return distante


class FiltrageIPMiddleware:
    CHEMINS_LIBRES = ("/sante/",)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/sante/":
            # contrôle de santé du conteneur : répondu ici, avant la vérification du nom d'hôte
            return HttpResponse("ok", content_type="text/plain")
        ip = ip_client(request)
        request.ip_client = ip
        reseaux = settings.RESEAUX_AUTORISES
        if reseaux and not ip.is_loopback and request.path not in self.CHEMINS_LIBRES and not _dans(ip, reseaux):
            logger.warning("Accès refusé : %s → %s", ip, request.path)
            return render(request, "planning/acces_refuse.html", {"ip": ip}, status=403)
        return self.get_response(request)
