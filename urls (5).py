from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Interventions C2RMF · administration"
admin.site.site_title = "Interventions C2RMF"
admin.site.index_title = "Administration avancée"

urlpatterns = [
    path("gestion/", admin.site.urls),
    path("", include("planning.urls")),
]

handler403 = "planning.views.erreur_403"
handler404 = "planning.views.erreur_404"
