from django.conf import settings

from .models import Site


def commun(request):
    site = getattr(request, "site_courant", None)
    autres = []
    if site is not None:
        autres = list(Site.objects.filter(actif=True).exclude(pk=site.pk))
    return {
        "site": site,
        "autres_sites": autres,
        "mode_dev": settings.DEBUG or settings.EMAIL_HOST == "mailpit",
    }
