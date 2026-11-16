from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "planning"

reinit = dict(
    email_template_name="registration/reinit_email.txt",
    subject_template_name="registration/reinit_sujet.txt",
    success_url=reverse_lazy("planning:reinit_envoyee"),
    template_name="registration/reinit_demande.html",
)

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("sante/", views.sante, name="sante"),
    path("connexion/", views.connexion, name="connexion"),
    path("deconnexion/", views.deconnexion, name="deconnexion"),
    path("inscription/", views.inscription, name="inscription"),
    path("activation/renvoyer/", views.renvoyer_activation, name="renvoyer_activation"),
    path("activation/<uidb64>/<token>/", views.activation, name="activation"),
    path("mot-de-passe/", auth_views.PasswordResetView.as_view(**reinit), name="reinit"),
    path("mot-de-passe/envoye/", auth_views.PasswordResetDoneView.as_view(template_name="registration/reinit_envoyee.html"), name="reinit_envoyee"),
    path("mot-de-passe/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="registration/reinit_nouveau.html", success_url=reverse_lazy("planning:reinit_fait")), name="reinit_confirmer"),
    path("mot-de-passe/fait/", auth_views.PasswordResetCompleteView.as_view(template_name="registration/reinit_fait.html"), name="reinit_fait"),
    path("ecran/", views.ecran_choix, name="ecran_choix"),
    path("locaux/export/", views.export_salles, name="export_salles"),
    path("locaux/modele/", views.modele_import, name="modele_import"),
    path("<slug:site>/semaine/", views.semaine, name="semaine"),
    path("<slug:site>/ecran/", views.ecran, name="ecran"),
    path("<slug:site>/intervention/nouvelle/", views.saisie, name="nouvelle"),
    path("<slug:site>/intervention/<int:pk>/", views.detail, name="detail"),
    path("<slug:site>/intervention/<int:pk>/modifier/", views.saisie, name="modifier"),
    path("<slug:site>/intervention/<int:pk>/supprimer/", views.suppression, name="supprimer"),
    path("<slug:site>/intervention/<int:pk>/securite/", views.securite, name="securite"),
    path("<slug:site>/administration/", views.administration, name="administration"),
    path("<slug:site>/administration/import-locaux/", views.import_salles, name="import_salles"),
]
