"""Paramètres de l'application « Interventions C2RMF ».

Tout ce qui dépend de l'environnement (secrets, nom DNS, messagerie, plages IP)
se règle dans le fichier .env, jamais dans ce fichier.
"""
import ipaddress
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(cle, defaut=None):
    return os.environ.get(cle, defaut)


def env_bool(cle, defaut=False):
    v = os.environ.get(cle)
    if v is None or v.strip() == "":
        return defaut
    return v.strip().lower() in ("1", "true", "oui", "yes", "on")


def env_liste(cle, defaut=""):
    brut = os.environ.get(cle, defaut) or ""
    return [x.strip() for x in brut.replace(";", ",").replace(" ", ",").split(",") if x.strip()]


def env_reseaux(cle):
    reseaux = []
    for x in env_liste(cle):
        try:
            reseaux.append(ipaddress.ip_network(x, strict=False))
        except ValueError as exc:
            raise ImproperlyConfigured(f"{cle} : « {x} » n'est pas une adresse ou une plage IP valide ({exc}).")
    return reseaux


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être renseignée dans le fichier .env.")

ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_liste("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "planning",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "planning.middleware.FiltrageIPMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "planning.context_processors.commun",
            ],
        },
    },
]

if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST", "db"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:  # poste de développement sans PostgreSQL
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "planning.Utilisateur"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "planning:connexion"
LOGIN_REDIRECT_URL = "planning:accueil"
PASSWORD_RESET_TIMEOUT = 3 * 24 * 3600  # liens d'activation et de réinitialisation : 3 jours

# Session fermée après 8 heures d'inactivité
SESSION_COOKIE_AGE = 8 * 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Messagerie -------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "mailpit")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Interventions C2RMF <ne-pas-repondre@culture.gouv.fr>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[Interventions C2RMF] "

# --- Règles métier ------------------------------------------------------------
DOMAINES_EMAIL_AUTORISES = [d.lower().lstrip("@") for d in env_liste("DOMAINES_EMAIL_AUTORISES", "culture.gouv.fr")]
CONNEXION_ESSAIS_MAX = int(env("CONNEXION_ESSAIS_MAX", "5"))
CONNEXION_BLOCAGE_MINUTES = int(env("CONNEXION_BLOCAGE_MINUTES", "15"))
ECRAN_RAFRAICHISSEMENT_SECONDES = int(env("ECRAN_RAFRAICHISSEMENT_SECONDES", "300"))

# --- Filtrage réseau ----------------------------------------------------------
# Plages autorisées à joindre l'application (vide = pas de filtrage applicatif).
RESEAUX_AUTORISES = env_reseaux("RESEAUX_AUTORISES")
# Adresses du proxy Nginx dont on accepte l'en-tête X-Forwarded-For.
PROXYS_DE_CONFIANCE = env_reseaux("PROXYS_DE_CONFIANCE")

# --- HTTPS (à activer quand Nginx porte le certificat) ------------------------
HTTPS_ACTIF = env_bool("HTTPS_ACTIF", False)
if HTTPS_ACTIF:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} : {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "planning": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
