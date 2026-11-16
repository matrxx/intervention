from django import forms
from django.conf import settings
from django.contrib.auth import password_validation

from .models import Intervention, Salle, Site, TypeIntervention, Utilisateur, Zone


def domaine_autorise(email):
    email = (email or "").strip().lower()
    return any(email.endswith("@" + d) for d in settings.DOMAINES_EMAIL_AUTORISES)


class ConnexionForm(forms.Form):
    site = forms.ModelChoiceField(queryset=Site.objects.filter(actif=True), empty_label=None,
                                  widget=forms.RadioSelect, error_messages={"required": "Choisissez votre site."})
    email = forms.EmailField(label="Adresse e-mail professionnelle")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))


class InscriptionForm(forms.ModelForm):
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text="12 caractères minimum.")
    password2 = forms.CharField(label="Confirmer le mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = Utilisateur
        fields = ["email", "first_name", "last_name"]
        labels = {"email": "Adresse e-mail professionnelle", "first_name": "Prénom", "last_name": "Nom"}

    def __init__(self, *a, **kw):
        kw.setdefault("label_suffix", "")
        super().__init__(*a, **kw)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["email"].widget.attrs.update(placeholder="prenom.nom@culture.gouv.fr", autocomplete="username")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if not domaine_autorise(email):
            raise forms.ValidationError("Seules les adresses " + ", ".join("@" + d for d in settings.DOMAINES_EMAIL_AUTORISES)
                                        + " peuvent créer un compte.")
        if Utilisateur.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte existe déjà pour cette adresse. Utilisez « Mot de passe oublié » si besoin.")
        return email

    def clean(self):
        cd = super().clean()
        p1, p2 = cd.get("password1"), cd.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne sont pas identiques.")
        if p1:
            u = Utilisateur(email=cd.get("email", ""), first_name=cd.get("first_name", ""), last_name=cd.get("last_name", ""))
            try:
                password_validation.validate_password(p1, u)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return cd

    def save(self, commit=True):
        u = super().save(commit=False)
        u.first_name = u.first_name.strip()
        u.last_name = u.last_name.strip().upper()
        u.set_password(self.cleaned_data["password1"])
        u.is_active = False
        if commit:
            u.save()
        return u


class InterventionForm(forms.ModelForm):
    class Meta:
        model = Intervention
        fields = ["type", "description", "portee", "zone", "niveau", "salles", "precision",
                  "date_debut", "date_fin", "journee_entiere", "heure_debut", "heure_fin",
                  "entreprise", "proxyclick", "visite_prevention", "plan_prevention", "protocole", "observations"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "ex. Pose de pantographes, installation de 5 unités"}),
            "observations": forms.Textarea(attrs={"rows": 2}),
            "portee": forms.RadioSelect,
            "salles": forms.CheckboxSelectMultiple,
            "date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "date_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "heure_debut": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "heure_fin": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "niveau": forms.Select,
        }
        labels = {"precision": "Précision du lieu", "description": "Description"}
        help_texts = {"precision": "Facultatif, ex. TGBT, salle Laser."}

    def __init__(self, *a, site, **kw):
        kw.setdefault("label_suffix", "")
        super().__init__(*a, **kw)
        self.site = site
        self.fields["type"].queryset = TypeIntervention.objects.filter(actif=True)
        self.fields["type"].empty_label = None
        self.fields["zone"].queryset = Zone.objects.filter(site=site)
        self.fields["zone"].empty_label = None
        salles = Salle.objects.filter(site=site).select_related("zone")
        if self.instance.pk:
            salles = salles.filter(active=True) | salles.filter(pk__in=self.instance.salles.values("pk"))
        else:
            salles = salles.filter(active=True)
        self.fields["salles"].queryset = salles.distinct()
        niveaux = list(Salle.objects.filter(site=site).order_by("ordre_niveau").values_list("niveau", flat=True).distinct())
        vus = []
        for n in niveaux:
            if n not in vus:
                vus.append(n)
        self.fields["niveau"].widget.choices = [(n, n) for n in vus]
        self.niveaux_par_zone = {}
        for z_id, n, o in Salle.objects.filter(site=site).values_list("zone_id", "niveau", "ordre_niveau").order_by("ordre_niveau").distinct():
            lst = self.niveaux_par_zone.setdefault(str(z_id), [])
            if n not in lst:
                lst.append(n)
        if not Zone.objects.filter(site=site).exists():
            self.fields["portee"].choices = [c for c in Intervention.PORTEES if c[0] == "site"]
            self.initial.setdefault("portee", "site")
        else:
            lz = site.libelle_zone.lower()
            self.fields["portee"].choices = [(k, f"Une {lz}" if k == "zone" else v) for k, v in Intervention.PORTEES]
        self.fields["zone"].label = site.libelle_zone

    def clean(self):
        cd = super().clean()
        portee = cd.get("portee")
        if portee == "salles" and not cd.get("salles"):
            self.add_error("salles", "Choisissez au moins une salle, ou une autre étendue (niveau, aile, site).")
        if portee in ("zone", "niveau") and not cd.get("zone"):
            self.add_error("zone", "Choisissez une zone.")
        if portee == "niveau":
            z = cd.get("zone")
            if not cd.get("niveau"):
                self.add_error("niveau", "Choisissez un niveau.")
            elif z and cd["niveau"] not in self.niveaux_par_zone.get(str(z.pk), []):
                self.add_error("niveau", f"Le niveau « {cd['niveau']} » n'existe pas pour {z}.")
        d1, d2 = cd.get("date_debut"), cd.get("date_fin")
        if d1 and d2 and d2 < d1:
            self.add_error("date_fin", "La date de fin est avant la date de début.")
        if d1 and d2 and (d2 - d1).days > 366:
            self.add_error("date_fin", "Une intervention ne peut pas dépasser un an.")
        if not cd.get("journee_entiere"):
            h1, h2 = cd.get("heure_debut"), cd.get("heure_fin")
            if not h1 or not h2:
                self.add_error("heure_debut", "Indiquez les heures, ou cochez « Journée entière ».")
            elif h2 <= h1:
                self.add_error("heure_fin", "L'heure de fin doit être après l'heure de début.")
        else:
            cd["heure_debut"] = cd["heure_fin"] = None
        if portee != "salles":
            cd["salles"] = Salle.objects.none()
        if portee not in ("zone", "niveau"):
            cd["zone"] = None
        if portee != "niveau":
            cd["niveau"] = ""
        return cd


class ImportLocauxForm(forms.Form):
    label_suffix = ""

    MODES = [("maj", "Ajouter et mettre à jour (les salles absentes du fichier ne changent pas)"),
             ("remplacer", "Remplacer la liste : les salles absentes du fichier sont désactivées")]
    fichier = forms.FileField(label="Fichier CSV")
    mode = forms.ChoiceField(choices=MODES, widget=forms.RadioSelect, initial="maj")
