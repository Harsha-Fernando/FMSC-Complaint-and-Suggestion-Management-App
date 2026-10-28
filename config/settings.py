"""
Django settings for the FMSC Complaint and Suggestion Management App.

Every value that differs between a laptop and the faculty server is read from
an environment variable, so the same code runs in both places. See README.md
for the full list.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
DEBUG = env_bool("DJANGO_DEBUG", True)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is off.")
    SECRET_KEY = "dev-only-insecure-key-change-me"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "cases",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "cases.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database: SQLite for development, PostgreSQL for the faculty server
# ---------------------------------------------------------------------------
if env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "fmsc_cms"),
            "USER": env("DB_USER", "fmsc_cms"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrRegistrationNumberBackend"]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "cases:home"
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

SESSION_COOKIE_AGE = 60 * 60 * 8  # one working day
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("si", "සිංහල"), ("ta", "தமிழ்")]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = "Lax"
TIME_ZONE = "Asia/Colombo"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files and uploads
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploaded evidence lives here. It is deliberately NOT exposed through
# MEDIA_URL: every file is served by a view that checks who is asking.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))

# Attachment rules (Section 5.1: "Image and video upload with file size restrictions")
MAX_IMAGE_SIZE_MB = int(env("MAX_IMAGE_SIZE_MB", "5"))
MAX_VIDEO_SIZE_MB = int(env("MAX_VIDEO_SIZE_MB", "50"))
MAX_ATTACHMENTS_PER_UPLOAD = int(env("MAX_ATTACHMENTS_PER_UPLOAD", "5"))
ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ALLOWED_VIDEO_EXTENSIONS = ["mp4", "mov", "webm"]

FILE_UPLOAD_PERMISSIONS = 0o640
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# ---------------------------------------------------------------------------
# Email notifications (Section 13: email + in-app in the first phase)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "FMSC Case Desk <no-reply@fmsc.local>")
NOTIFY_BY_EMAIL = env_bool("NOTIFY_BY_EMAIL", True)

# Official logos (Wireframe 1: "University Logo / Faculty Logo"). Download them from the
# university's branding page and save them under static/ with these names. If a file is
# missing, the app shows the name in text instead. Logos are never recoloured or redrawn here.
UNIVERSITY_LOGO = env("UNIVERSITY_LOGO", "img/usj-logo.png")
FACULTY_LOGO = env("FACULTY_LOGO", "img/fmsc-logo.png")

# Public address of the site, used for links inside emails.
SITE_URL = env("SITE_URL", "http://127.0.0.1:8000")

# Pending case reminders (Section 11): remind after this many days without action.
REMINDER_AFTER_DAYS_NORMAL = int(env("REMINDER_AFTER_DAYS_NORMAL", "3"))
REMINDER_AFTER_DAYS_URGENT = int(env("REMINDER_AFTER_DAYS_URGENT", "1"))

# ---------------------------------------------------------------------------
# Production hardening (applies automatically when DEBUG is off)
# ---------------------------------------------------------------------------
if not DEBUG:
    LANGUAGE_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    CSRF_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", True)
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    if env("DJANGO_BEHIND_PROXY"):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "cases": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    },
}
