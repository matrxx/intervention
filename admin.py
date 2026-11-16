from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Bandeau, Intervention, Salle, Site, TypeIntervention, Utilisateur, Zone

COULEUR = forms.TextInput(attrs={"type": "color", "style": "width:60px;height:32px;padding:0"})


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    ordering = ["last_name", "first_name"]
    list_display = ["email", "first_name", "last_name", "is_staff", "is_active", "date_joined", "last_login"]
    list_filter = ["is_staff", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    readonly_fields = ["date_joined", "last_login"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identité", {"fields": ("first_name", "last_name")}),
        ("Droits", {"fields": ("is_active", "is_staff", "is_superuser"),
                    "description": "« Statut équipe » = administrateur de l'application. Décochez « Actif » pour désactiver un compte."}),
        ("Sécurité", {"fields": ("bloque_jusqua", "last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "password1", "password2", "is_staff")}),)


class ZoneInline(admin.TabularInline):
    model = Zone
    extra = 0


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ["nom", "code", "nom_long", "libelle_zone", "actif"]
    inlines = [ZoneInline]
    formfield_overrides = {}

    def formfield_for_dbfield(self, db_field, request, **kw):
        if db_field.name == "couleur":
            kw["widget"] = COULEUR
        return super().formfield_for_dbfield(db_field, request, **kw)


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ["code", "libelle", "site", "zone", "niveau", "active"]
    list_editable = ["libelle", "active"]
    list_filter = ["site", "zone", "niveau", "active"]
    search_fields = ["code", "libelle"]
    list_per_page = 200
    list_select_related = ["site", "zone"]


@admin.register(TypeIntervention)
class TypeAdmin(admin.ModelAdmin):
    list_display = ["nom", "couleur", "ordre", "actif"]
    list_editable = ["couleur", "ordre", "actif"]
    prepopulated_fields = {"code": ["nom"]}

    def formfield_for_dbfield(self, db_field, request, **kw):
        if db_field.name == "couleur":
            kw["widget"] = COULEUR
        return super().formfield_for_dbfield(db_field, request, **kw)


@admin.register(Bandeau)
class BandeauAdmin(admin.ModelAdmin):
    list_display = ["__str__", "site", "date_debut", "date_fin", "actif"]
    list_editable = ["actif"]
    list_filter = ["site", "genre", "actif"]


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = ["date_debut", "date_fin", "type", "site", "description", "hote"]
    list_filter = ["site", "type", "date_debut"]
    search_fields = ["description", "hote", "entreprise", "precision"]
    date_hierarchy = "date_debut"
    filter_horizontal = ["salles"]
    readonly_fields = ["cree_par", "cree_le", "modifie_le"]
