import os
from pathlib import Path
from decouple import config   # install: pip install python-decouple

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── SECURITY ───────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# ─── APPS ──────────────────────────────────────────────
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.inlines',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_quill',
    'django_htmx',
    'core', 'accounts', 'clients', 'services',
    'tickets', 'finance', 'portfolio', 'tracking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'tracking.middleware.ActivityMiddleware',
    'accounts.middleware.LastLoginIPMiddleware',
]

ROOT_URLCONF = 'pritech.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'core.context_processors.site_config',
            'core.context_processors.sidebar_recent_items',
            'portfolio.context_processors.portfolio_settings',
        ],
    },
}]

WSGI_APPLICATION = 'pritech.wsgi.application'

# ─── DATABASE (PostgreSQL) ─────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', 'localhost'),
        'PORT': config('DB_PORT', '5432'),
    }
}

# ─── AUTHENTICATION ────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailOrPhoneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 6}},
]

# ─── I18N ──────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Blantyre'
USE_I18N = True
USE_TZ = True

# ─── STATIC & MEDIA FILES ──────────────────────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ─── BUSINESS CONFIG ───────────────────────────────────
VAT_RATE = 0.175
CURRENCY = 'MWK'
CURRENCY_SYMBOL = 'K'

# ─── EMAIL (SMTP for production) ───────────────────────
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = config('EMAIL_HOST', default='')
    EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
    EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
    DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# ═══════════════ UNFOLD CONFIGURATION ══════════════════
from django.templatetags.static import static
from django.urls import reverse_lazy

UNFOLD = {
    "SITE_TITLE": "PriTech Admin",
    "SITE_HEADER": "PriTech Dashboard",
    "SITE_SUBHEADER": "Modern ICT. Always.",
    "SITE_URL": "/",
    "SITE_LOGO": lambda request: static("images/logo.png"),
    "SITE_LOGO_COLLAPSED": lambda request: static("images/logo.png"),
    "SITE_FAVICONS": [
        {"rel": "icon", "sizes": "32x32", "type": "image/png", "href": lambda request: static("images/logo.png")},
    ],
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
    "INDEX_VIEW": "core.admin_views.htmx_admin_index",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "ENVIRONMENT": "Production",
    "COLORS": {
        "primary": {
            "50": "238 242 255", "100": "224 231 255", "200": "199 210 255",
            "300": "165 180 252", "400": "129 148 248", "500": "65 84 241",
            "600": "53 70 217", "700": "45 57 191", "800": "38 47 159",
            "900": "30 37 130", "950": "21 26 95",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [   # unchanged – keep your existing navigation
            {
                "title": "Dashboard",
                "separator": False,
                "items": [
                    {"title": "Overview", "icon": "dashboard", "link": reverse_lazy("admin:index")},
                    {"title": "View Website", "icon": "open_in_new", "link": "/", "target": "_blank"},
                ],
            },
            # ... (the rest of your navigation – keep as is)
        ],
    },
    "TABS": [   # keep your existing tabs
        # ...
    ],
    "STYLES": [lambda request: static("css/unfold-overrides.css")],
    "SCRIPTS": [],
    "EXTRA_SCRIPTS": [
        {
            "src": "https://unpkg.com/htmx.org@1.9.10",
            "integrity": "sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2",
            "crossorigin": "anonymous",
        },
    ],
}

# ═══════════════ QUILL EDITOR CONFIG ══════════════════
QUILL_CONFIGS = {
    "default": {
        "theme": "snow",
        "modules": {
            "toolbar": [
                [{"header": [1, 2, False]}],
                ["bold", "italic", "underline", "strike"],
                [{"color": []}, {"background": []}],
                ["blockquote", "code-block"],
                [{"list": "ordered"}, {"list": "bullet"}],
                ["link", "image", "video"],
                ["clean"],
            ],
        },
        "placeholder": "Write something great...",
    },
}
