from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

couleur_hex = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Couleur au format #RRGGBB.")


class UtilisateurManager(BaseUserManager):
    use_in_migrations = True

    def _creer(self, email, password, **extra):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._creer(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, is_active=True)
        return self._creer(email, password, **extra)


class Utilisateur(AbstractUser):
    """Compte agent. L'identifiant est l'adresse prenom.nom@culture.gouv.fr.
    is_staff = administrateur de l'application."""

    username = None
    email = models.EmailField("adresse e-mail", unique=True)
    echecs_connexion = models.PositiveSmallIntegerField(default=0, editable=False)
    bloque_jusqua = models.DateTimeField("connexion bloquée jusqu'à", null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    objects = UtilisateurManager()

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["last_name", "first_name"]

    @property
    def nom_complet(self):
        nom = f"{self.first_name} {self.last_name.upper()}".strip()
        return nom or self.email

    def __str__(self):
        return f"{self.nom_complet} <{self.email}>"


class Site(models.Model):
    code = models.SlugField("code", unique=True, help_text="Utilisé dans les adresses et le fichier d'import (ex. versailles, louvre).")
    nom = models.CharField("nom court", max_length=60)
    nom_long = models.CharField("nom complet", max_length=120, blank=True)
    libelle_zone = models.CharField("nom d'une zone", max_length=30, default="Aile", help_text="Aile, Zone, Bâtiment…")
    couleur = models.CharField("couleur repère", max_length=7, default="#1d4b87", validators=[couleur_hex])
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom


class Zone(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="zones")
    code = models.CharField("code", max_length=20)
    nom = models.CharField("nom", max_length=120, blank=True, help_text="ex. avenue de Paris")
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "aile / zone"
        verbose_name_plural = "ailes / zones"
        ordering = ["site", "ordre", "code"]
        constraints = [models.UniqueConstraint(fields=["site", "code"], name="zone_unique_par_site")]

    def __str__(self):
        base = f"{self.site.libelle_zone} {self.code}"
        return f"{base} ({self.nom})" if self.nom else base


class Salle(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="salles")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="salles")
    niveau = models.CharField("niveau", max_length=40)
    ordre_niveau = models.SmallIntegerField("ordre du niveau", default=0)
    code = models.CharField("code", max_length=30)
    libelle = models.CharField("libellé", max_length=150, blank=True)
    active = models.BooleanField(default=True, help_text="Une salle inactive n'est plus proposée à la saisie.")

    class Meta:
        ordering = ["site", "zone__ordre", "zone__code", "ordre_niveau", "code"]
        constraints = [models.UniqueConstraint(fields=["site", "code"], name="salle_unique_par_site")]

    def __str__(self):
        return f"{self.code} · {self.libelle}" if self.libelle else self.code


class TypeIntervention(models.Model):
    code = models.SlugField(unique=True)
    nom = models.CharField(max_length=60)
    couleur = models.CharField(max_length=7, validators=[couleur_hex])
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "type d'intervention"
        verbose_name_plural = "types d'intervention"
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom


class Bandeau(models.Model):
    GENRES = [
        ("fermeture", "Fermeture du site"),
        ("telephone", "Accueil téléphonique uniquement"),
        ("autre", "Autre message"),
    ]
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, help_text="Vide = les deux sites.")
    genre = models.CharField(max_length=20, choices=GENRES, default="autre")
    texte = models.CharField("précision", max_length=200, blank=True)
    date_debut = models.DateField("du", null=True, blank=True)
    date_fin = models.DateField("au", null=True, blank=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "bandeau d'alerte"
        verbose_name_plural = "bandeaux d'alerte"
        ordering = ["-date_debut"]

    @property
    def message(self):
        if self.genre == "autre":
            return self.texte
        base = self.get_genre_display()
        return f"{base} — {self.texte}" if self.texte else base

    def __str__(self):
        return self.message or "(vide)"

    @classmethod
    def en_cours(cls, site, jour):
        qs = cls.objects.filter(actif=True).filter(models.Q(site=site) | models.Q(site__isnull=True))
        qs = qs.filter(models.Q(date_debut__isnull=True) | models.Q(date_debut__lte=jour))
        qs = qs.filter(models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=jour))
        return [b for b in qs if b.message]


class Intervention(models.Model):
    PORTEES = [("salles", "Salle(s)"), ("niveau", "Un niveau"), ("zone", "Une aile / zone"), ("site", "Tout le site")]

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="interventions")
    type = models.ForeignKey(TypeIntervention, on_delete=models.PROTECT, verbose_name="type d'intervention")
    description = models.TextField()
    portee = models.CharField("lieu", max_length=10, choices=PORTEES, default="salles")
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, null=True, blank=True, verbose_name="aile / zone")
    niveau = models.CharField(max_length=40, blank=True)
    salles = models.ManyToManyField(Salle, blank=True)
    precision = models.CharField("précision du lieu", max_length=150, blank=True)
    date_debut = models.DateField("du")
    date_fin = models.DateField("au")
    journee_entiere = models.BooleanField("journée entière", default=False)
    heure_debut = models.TimeField("de", null=True, blank=True)
    heure_fin = models.TimeField("à", null=True, blank=True)
    hote = models.CharField("hôte (responsable)", max_length=150)
    entreprise = models.CharField("entreprise intervenante", max_length=150, blank=True)
    proxyclick = models.BooleanField("Proxyclick fait", default=False)
    visite_prevention = models.BooleanField("visite de prévention faite", default=False)
    plan_prevention = models.BooleanField("plan de prévention fait", default=False)
    protocole = models.CharField("protocole / prévenance", max_length=250, blank=True)
    observations = models.TextField(blank=True)
    cree_par = models.ForeignKey(Utilisateur, on_delete=models.PROTECT, related_name="interventions", verbose_name="déclarée par")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    SECURITE = [("proxyclick", "Proxyclick"), ("visite_prevention", "Visite de prévention"), ("plan_prevention", "Plan de prévention")]

    class Meta:
        ordering = ["date_debut", "journee_entiere", "heure_debut"]
        indexes = [models.Index(fields=["site", "date_debut", "date_fin"])]

    def __str__(self):
        return f"{self.type} · {self.description[:60]}"

    @property
    def sur_plusieurs_jours(self):
        return self.date_fin > self.date_debut

    @property
    def nb_jours(self):
        return (self.date_fin - self.date_debut).days + 1

    @property
    def horaire(self):
        if self.journee_entiere or not self.heure_debut:
            return "Journée"
        return f"{_hm(self.heure_debut)} – {_hm(self.heure_fin)}" if self.heure_fin else _hm(self.heure_debut)

    @property
    def securite(self):
        return [(champ, libelle, getattr(self, champ)) for champ, libelle in self.SECURITE]

    @property
    def securite_faite(self):
        return [libelle for champ, libelle, fait in self.securite if fait]

    def lieu(self):
        lz = self.site.libelle_zone
        if self.portee == "site":
            txt = "Tout le site"
        elif self.portee == "zone" and self.zone:
            txt = f"{lz} {self.zone.code}" + (f" ({self.zone.nom})" if self.zone.nom else "")
        elif self.portee == "niveau" and self.zone:
            txt = f"{lz} {self.zone.code} · {self.niveau}"
        else:
            salles = list(self.salles.all())
            if len(salles) == 1:
                txt = str(salles[0])
            else:
                libelles = {s.libelle for s in salles if s.libelle}
                txt = ", ".join(s.code for s in salles) + (f" · {libelles.pop()}" if len(libelles) == 1 else "")
        return f"{txt} · {self.precision}" if self.precision else txt

    def concerne_zone(self, zone_id):
        if self.portee == "site":
            return True
        if self.portee in ("zone", "niveau"):
            return self.zone_id == zone_id
        return any(s.zone_id == zone_id for s in self.salles.all())

    def modifiable_par(self, user):
        return user.is_authenticated and (user.is_staff or user.pk == self.cree_par_id)


def _hm(t):
    return f"{t.hour}h{t.minute:02d}" if t.minute else f"{t.hour}h"
