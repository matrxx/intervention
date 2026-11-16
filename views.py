import datetime as dt
import logging
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from . import import_locaux
from .forms import ConnexionForm, ImportLocauxForm, InscriptionForm, InterventionForm
from .models import Bandeau, Intervention, Salle, Site, TypeIntervention, Utilisateur
from .semaine import JOURS, MOIS, grille, jour_long, libelle_semaine, lundi

logger = logging.getLogger("planning")


class JetonActivation(PasswordResetTokenGenerator):
    """Le lien d'activation devient inutilisable dès que le compte est actif."""
    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}{user.password}{user.is_active}{timestamp}"


jeton_activation = JetonActivation()


# ---------------------------------------------------------------- utilitaires
def avec_site(vue):
    @wraps(vue)
    def enveloppe(request, site, *a, **kw):
        request.site_courant = get_object_or_404(Site, code=site, actif=True)
        request.session["site"] = site
        return vue(request, *a, **kw)
    return enveloppe


def admin_requis(vue):
    @wraps(vue)
    def enveloppe(request, *a, **kw):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('planning:connexion')}?next={request.path}")
        if not request.user.is_staff:
            return HttpResponseForbidden("Réservé aux administrateurs.")
        return vue(request, *a, **kw)
    return enveloppe


def _date(texte, defaut):
    try:
        return dt.date.fromisoformat(texte)
    except (TypeError, ValueError):
        return defaut


def _aujourdhui():
    return timezone.localdate()


def envoyer_activation(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    lien = request.build_absolute_uri(reverse("planning:activation", args=[uid, jeton_activation.make_token(user)]))
    corps = (
        f"Bonjour {user.first_name},\n\n"
        "Pour activer votre compte sur l'outil de gestion des interventions du C2RMF, ouvrez ce lien "
        f"(valable 3 jours) :\n\n{lien}\n\n"
        "Si vous n'avez pas demandé ce compte, ignorez ce message.\n"
    )
    send_mail(settings.EMAIL_SUBJECT_PREFIX + "Activez votre compte", corps, None, [user.email])
    logger.info("Lien d'activation envoyé à %s", user.email)


# ---------------------------------------------------------------- comptes
def accueil(request):
    code = request.session.get("site")
    if request.user.is_authenticated and code and Site.objects.filter(code=code, actif=True).exists():
        return redirect("planning:semaine", site=code)
    if request.user.is_authenticated:
        premier = Site.objects.filter(actif=True).first()
        if premier:
            return redirect("planning:semaine", site=premier.code)
    return redirect("planning:connexion")


def connexion(request):
    initial = {"site": Site.objects.filter(code=request.session.get("site")).first()}
    form = ConnexionForm(request.POST or None, initial=initial)
    renvoi = None
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        mdp = form.cleaned_data["password"]
        site = form.cleaned_data["site"]
        user = Utilisateur.objects.filter(email=email).first()
        maintenant = timezone.now()
        if user and user.bloque_jusqua and user.bloque_jusqua > maintenant:
            minutes = int((user.bloque_jusqua - maintenant).total_seconds() // 60) + 1
            form.add_error(None, f"Trop d'essais infructueux : réessayez dans {minutes} minute(s).")
        elif user and user.check_password(mdp):
            if not user.is_active:
                form.add_error(None, "Votre compte n'est pas encore activé : ouvrez le lien reçu par e-mail.")
                renvoi = user.email
            else:
                user.echecs_connexion = 0
                user.bloque_jusqua = None
                user.save(update_fields=["echecs_connexion", "bloque_jusqua"])
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                request.session["site"] = site.code
                logger.info("Connexion de %s (%s) sur %s", user.email, request.ip_client, site.code)
                suite = request.GET.get("next")
                if suite and url_has_allowed_host_and_scheme(suite, {request.get_host()}):
                    return redirect(suite)
                return redirect("planning:semaine", site=site.code)
        else:
            if user:
                user.echecs_connexion += 1
                if user.echecs_connexion >= settings.CONNEXION_ESSAIS_MAX:
                    user.bloque_jusqua = maintenant + dt.timedelta(minutes=settings.CONNEXION_BLOCAGE_MINUTES)
                    user.echecs_connexion = 0
                    logger.warning("Compte %s bloqué après échecs répétés (%s)", email, request.ip_client)
                user.save(update_fields=["echecs_connexion", "bloque_jusqua"])
            form.add_error(None, "Adresse ou mot de passe incorrect.")
    return render(request, "planning/connexion.html", {
        "form": form, "renvoi": renvoi, "sites": Site.objects.filter(actif=True),
        "essais_max": settings.CONNEXION_ESSAIS_MAX, "blocage": settings.CONNEXION_BLOCAGE_MINUTES,
    })


@require_POST
def renvoyer_activation(request):
    email = request.POST.get("email", "").strip().lower()
    user = Utilisateur.objects.filter(email=email, is_active=False).first()
    if user:
        envoyer_activation(request, user)
    messages.info(request, "Si un compte non activé existe pour cette adresse, un nouveau lien vient d'être envoyé.")
    return redirect("planning:connexion")


def inscription(request):
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        envoyer_activation(request, user)
        return render(request, "planning/inscription_envoyee.html", {"email": user.email})
    return render(request, "planning/inscription.html", {"form": form, "domaines": settings.DOMAINES_EMAIL_AUTORISES})


def activation(request, uidb64, token):
    try:
        user = Utilisateur.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (Utilisateur.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user and user.is_active:
        messages.info(request, "Ce compte est déjà actif : connectez-vous.")
    elif user and jeton_activation.check_token(user, token):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, "Compte activé. Vous pouvez vous connecter.")
        logger.info("Compte activé : %s", user.email)
    else:
        messages.error(request, "Ce lien d'activation n'est plus valable. Connectez-vous pour en recevoir un nouveau.")
    return redirect("planning:connexion")


@require_POST
def deconnexion(request):
    logout(request)
    messages.info(request, "Vous êtes déconnecté.")
    return redirect("planning:connexion")


# ---------------------------------------------------------------- calendrier
def _interventions(site, debut, fin):
    return list(
        Intervention.objects.filter(site=site, date_debut__lte=fin, date_fin__gte=debut)
        .select_related("type", "zone", "site", "cree_par").prefetch_related("salles")
    )


@login_required
@avec_site
def semaine(request):
    site = request.site_courant
    auj = _aujourdhui()
    debut = lundi(_date(request.GET.get("d"), auj))
    weekend = request.GET.get("we") == "1"
    nb = 7 if weekend else 5
    fin = debut + dt.timedelta(days=nb - 1)
    zone_id = request.GET.get("zone") or ""
    types_actifs = list(TypeIntervention.objects.filter(actif=True))
    masques = set(request.GET.getlist("sans"))
    ivs = [iv for iv in _interventions(site, debut, fin) if iv.type.code not in masques]
    if zone_id.isdigit():
        ivs = [iv for iv in ivs if iv.concerne_zone(int(zone_id))]
    jours, couloirs = grille(ivs, debut, nb, auj)
    base = {"we": "1"} if weekend else {}
    return render(request, "planning/semaine.html", {
        "jours": jours, "couloirs": couloirs, "nb": nb, "debut": debut,
        "num_semaine": debut.isocalendar()[1], "libelle": libelle_semaine(debut, nb),
        "prec": debut - dt.timedelta(days=7), "suiv": debut + dt.timedelta(days=7), "auj": auj,
        "weekend": weekend, "zone_id": zone_id, "zones": site.zones.all(), "types": types_actifs, "masques": masques,
        "bandeaux": Bandeau.en_cours(site, auj), "base": base, "onglet": "semaine",
    })


@login_required
@avec_site
def detail(request, pk):
    iv = get_object_or_404(Intervention.objects.select_related("type", "zone", "cree_par"), pk=pk, site=request.site_courant)
    return render(request, "planning/detail.html", {"iv": iv, "peut_modifier": iv.modifiable_par(request.user),
                                                    "retour": request.GET.get("retour", "")})


@login_required
@avec_site
def saisie(request, pk=None):
    site = request.site_courant
    iv = None
    if pk:
        iv = get_object_or_404(Intervention, pk=pk, site=site)
        if not iv.modifiable_par(request.user):
            return HttpResponseForbidden("Seul l'auteur ou un administrateur peut modifier cette intervention.")
    initial = {}
    if not iv:
        d = _date(request.GET.get("d"), _aujourdhui())
        initial = {"date_debut": d, "date_fin": d, "heure_debut": "09:00", "heure_fin": "12:00"}
    form = InterventionForm(request.POST or None, instance=iv, site=site, initial=initial)
    if request.method == "POST" and form.is_valid():
        nouvelle = form.save(commit=False)
        nouvelle.site = site
        if not iv:
            nouvelle.cree_par = request.user
            nouvelle.hote = request.user.nom_complet
        nouvelle.save()
        form.save_m2m()
        messages.success(request, "Intervention enregistrée.")
        logger.info("Intervention %s %s par %s", nouvelle.pk, "modifiée" if iv else "créée", request.user.email)
        return redirect(f"{reverse('planning:semaine', args=[site.code])}?d={lundi(nouvelle.date_debut).isoformat()}"
                        + ("&we=1" if nouvelle.date_debut.weekday() > 4 or nouvelle.date_fin.weekday() > 4 else ""))
    salles = form.fields["salles"].queryset
    choisies = set(map(str, form["salles"].value() or []))
    return render(request, "planning/saisie.html", {
        "form": form, "iv": iv, "salles": salles, "choisies": choisies,
        "hote": iv.hote if iv else request.user.nom_complet, "niveaux_par_zone": form.niveaux_par_zone,
    })


@login_required
@avec_site
def suppression(request, pk):
    iv = get_object_or_404(Intervention, pk=pk, site=request.site_courant)
    if not iv.modifiable_par(request.user):
        return HttpResponseForbidden("Seul l'auteur ou un administrateur peut supprimer cette intervention.")
    if request.method == "POST":
        d = lundi(iv.date_debut)
        logger.info("Intervention %s supprimée par %s", iv.pk, request.user.email)
        iv.delete()
        messages.success(request, "Intervention supprimée.")
        return redirect(f"{reverse('planning:semaine', args=[request.site_courant.code])}?d={d.isoformat()}")
    return render(request, "planning/suppression.html", {"iv": iv})


@login_required
@avec_site
@require_POST
def securite(request, pk):
    iv = get_object_or_404(Intervention, pk=pk, site=request.site_courant)
    if not iv.modifiable_par(request.user):
        return HttpResponseForbidden()
    for champ, _ in Intervention.SECURITE:
        setattr(iv, champ, request.POST.get(champ) == "on")
    iv.save(update_fields=[c for c, _ in Intervention.SECURITE] + ["modifie_le"])
    messages.success(request, "Suivi sécurité mis à jour.")
    return redirect("planning:detail", site=request.site_courant.code, pk=iv.pk)


# ---------------------------------------------------------------- écran
def ecran_choix(request):
    return render(request, "planning/ecran_choix.html", {"sites": Site.objects.filter(actif=True)})


@avec_site
def ecran(request):
    site = request.site_courant
    auj = _aujourdhui()
    debut = lundi(auj)
    ivs = _interventions(site, debut, debut + dt.timedelta(days=6))
    weekend = any(iv.date_fin >= debut + dt.timedelta(days=5) for iv in ivs)
    nb = 7 if weekend else 5
    jours, _ = grille(ivs, debut, nb, auj)
    bandeaux = Bandeau.en_cours(site, auj)
    message = "   •   ".join(b.message for b in bandeaux)
    return render(request, "planning/ecran.html", {
        "jours": jours, "nb": nb, "num_semaine": debut.isocalendar()[1], "libelle": libelle_semaine(debut, nb),
        "types": TypeIntervention.objects.filter(actif=True), "bandeau": message,
        "duree_bandeau": max(18, round(len(message) * 0.32)), "auj_long": jour_long(auj),
        "maintenant": timezone.localtime(), "rafraichir": settings.ECRAN_RAFRAICHISSEMENT_SECONDES,
        "rafraichir_min": max(1, settings.ECRAN_RAFRAICHISSEMENT_SECONDES // 60),
    })


# ---------------------------------------------------------------- administration
@admin_requis
@avec_site
def administration(request):
    site = request.site_courant
    salles = Salle.objects.filter(site=site)
    return render(request, "planning/administration.html", {
        "nb_salles": salles.count(), "nb_a_completer": salles.filter(libelle="").count(),
        "nb_inactives": salles.filter(active=False).count(),
        "nb_comptes": Utilisateur.objects.filter(is_active=True).count(),
        "bandeaux": Bandeau.en_cours(site, _aujourdhui()), "onglet": "admin",
    })


@admin_requis
@avec_site
def import_salles(request):
    site = request.site_courant
    cle = "import_locaux"
    if request.method == "POST" and request.POST.get("confirmer"):
        donnees = request.session.get(cle)
        if not donnees:
            messages.error(request, "L'aperçu a expiré : déposez à nouveau le fichier.")
            return redirect("planning:import_salles", site=site.code)
        remplacer = donnees["mode"] == "remplacer"
        analyse = import_locaux.lire(donnees["texte"], remplacer)
        if not analyse.valide:
            messages.error(request, "Le fichier contient des erreurs : import annulé.")
            return redirect("planning:import_salles", site=site.code)
        import_locaux.appliquer(analyse, remplacer)
        del request.session[cle]
        logger.info("Import des locaux par %s : %s", request.user.email, analyse.stats)
        messages.success(request, "Import terminé : " + " ; ".join(
            f"{nom} — {s['nouvelles']} ajoutée(s), {s['modifiees']} modifiée(s), {s['desactivees']} désactivée(s)"
            for nom, s in analyse.stats.items()))
        return redirect("planning:administration", site=site.code)

    form = ImportLocauxForm(request.POST or None, request.FILES or None)
    analyse = None
    if request.method == "POST" and form.is_valid():
        f = form.cleaned_data["fichier"]
        if f.size > import_locaux.TAILLE_MAX:
            form.add_error("fichier", "Fichier trop volumineux (2 Mo maximum).")
        else:
            texte = import_locaux.decoder(f.read())
            mode = form.cleaned_data["mode"]
            analyse = import_locaux.lire(texte, mode == "remplacer")
            if analyse.valide:
                request.session[cle] = {"texte": texte, "mode": mode, "nom": f.name}
    return render(request, "planning/import_salles.html", {"form": form, "analyse": analyse, "colonnes": import_locaux.COLONNES, "onglet": "admin"})


@admin_requis
def export_salles(request):
    codes = request.GET.getlist("site")
    sites = Site.objects.filter(code__in=codes) if codes else Site.objects.all()
    nom = "locaux_" + ("_".join(s.code for s in sites) or "aucun") + f"_{_aujourdhui():%Y%m%d}.csv"
    rep = HttpResponse(import_locaux.exporter(sites), content_type="text/csv; charset=utf-8")
    rep["Content-Disposition"] = f'attachment; filename="{nom}"'
    return rep


@admin_requis
def modele_import(request):
    from pathlib import Path
    contenu = (Path(__file__).resolve().parent / "data" / "modele_import_locaux.csv").read_bytes()
    rep = HttpResponse(contenu, content_type="text/csv; charset=utf-8")
    rep["Content-Disposition"] = 'attachment; filename="modele_import_locaux.csv"'
    return rep


# ---------------------------------------------------------------- divers
def sante(request):
    return HttpResponse("ok", content_type="text/plain")


def erreur_403(request, exception=None):
    return render(request, "planning/erreur.html", {"titre": "Accès refusé", "texte": str(exception or "")}, status=403)


def erreur_404(request, exception=None):
    return render(request, "planning/erreur.html", {"titre": "Page introuvable", "texte": ""}, status=404)
