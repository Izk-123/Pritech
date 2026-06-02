"""
Pritech Production Settings
===========================
Environment: Production (VPS)
Python: 3.11+
Django: 5.2.7
"""

import os
from pathlib import Path
from decouple import config
from django.templatetags.static import static
from django.urls import reverse_lazy
from celery.schedules import crontab

# -----------------------------------------------------------------------------
# PATH CONFIGURATION
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# SECURITY
# -----------------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(',')

# -----------------------------------------------------------------------------
# APPLICATION DEFINITION
# -----------------------------------------------------------------------------
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.inlines',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',               # Required for allauth
    'django_quill',
    'django_htmx',
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'django_celery_beat',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.linkedin_oauth2',
    'simple_history',
    'core',
    'accounts',
    'clients',
    'services',
    'tickets',
    'finance',
    'portfolio',
    'tracking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
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
            'core.context_processors.pending_expenses_count',
            'portfolio.context_processors.portfolio_settings',
        ],
    },
}]

WSGI_APPLICATION = 'pritech.wsgi.application'

# -----------------------------------------------------------------------------
# DATABASE (PostgreSQL)
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# AUTHENTICATION
# -----------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
    'accounts.backends.EmailOrPhoneBackend',
]
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# -----------------------------------------------------------------------------
# DJANGO-ALLAUTH (Updated to remove deprecation warnings)
# -----------------------------------------------------------------------------
SITE_ID = 1
# New allauth settings (replaces deprecated ACCOUNT_EMAIL_REQUIRED, ACCOUNT_USERNAME_REQUIRED, ACCOUNT_AUTHENTICATION_METHOD)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.SocialAccountAdapter'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    },
    'linkedin_oauth2': {
        'SCOPE': ['r_emailaddress', 'r_liteprofile'],
        'PROFILE_FIELDS': ['id', 'first-name', 'last-name', 'email-address'],
    }
}

# -----------------------------------------------------------------------------
# PASSWORD VALIDATION
# -----------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -----------------------------------------------------------------------------
# INTERNATIONALISATION
# -----------------------------------------------------------------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Blantyre'
USE_I18N = True
USE_TZ = True

# -----------------------------------------------------------------------------
# STATIC & MEDIA
# -----------------------------------------------------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# -----------------------------------------------------------------------------
# BUSINESS CONFIG
# -----------------------------------------------------------------------------
VAT_RATE = 0.175
CURRENCY = 'MWK'
CURRENCY_SYMBOL = 'K'

# -----------------------------------------------------------------------------
# EMAIL (SMTP)
# -----------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# -----------------------------------------------------------------------------
# CELERY & REDIS
# -----------------------------------------------------------------------------
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    'generate-subscription-invoices': {
        'task': 'finance.tasks.generate_subscription_invoices',
        'schedule': crontab(day_of_month='1', hour=0, minute=0),
    },
    'check-sla-breaches': {
        'task': 'tickets.tasks.check_sla_breaches',
        'schedule': crontab(minute='*/30'),
    },
}

# -----------------------------------------------------------------------------
# CACHING (Redis)
# -----------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# -----------------------------------------------------------------------------
# SECURITY (HTTPS, HSTS)
# -----------------------------------------------------------------------------
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 1209600

# -----------------------------------------------------------------------------
# UNFOLD ADMIN CONFIGURATION (with full SIDEBAR and TABS)
# -----------------------------------------------------------------------------
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
    "ENVIRONMENT": "Production" if not DEBUG else "Development",
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
        "navigation": [
            {
                "title": "Dashboard",
                "separator": False,
                "items": [
                    {"title": "Overview", "icon": "dashboard", "link": reverse_lazy("admin:index")},
                    {"title": "View Website", "icon": "open_in_new", "link": "/", "target": "_blank"},
                ],
            },
            {
                "title": "Clients",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Organizations", "icon": "corporate_fare", "link": reverse_lazy("admin:clients_clientorganization_changelist")},
                    {"title": "Contacts", "icon": "contacts", "link": reverse_lazy("admin:clients_clientcontact_changelist")},
                ],
            },
            {
                "title": "Services",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Services", "icon": "miscellaneous_services", "link": reverse_lazy("admin:services_service_changelist")},
                    {"title": "Categories", "icon": "category", "link": reverse_lazy("admin:services_servicecategory_changelist")},
                    {"title": "Packages", "icon": "package_2", "link": reverse_lazy("admin:services_servicepackage_changelist")},
                ],
            },
            {
                "title": "Support",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Tickets", "icon": "support_agent", "link": reverse_lazy("admin:tickets_ticket_changelist"), "badge": "core.admin_badges.open_tickets"},
                    {"title": "Comments", "icon": "chat", "link": reverse_lazy("admin:tickets_ticketcomment_changelist")},
                    {"title": "Work Logs", "icon": "clock_history", "link": reverse_lazy("admin:tickets_ticketworklog_changelist")},
                    {"title": "Attachments", "icon": "attach_file", "link": reverse_lazy("admin:tickets_ticketattachment_changelist")},
                    {"title": "SLAs", "icon": "timer", "link": reverse_lazy("admin:tickets_ticketsla_changelist")},
                    {"title": "Canned Responses", "icon": "reply_all", "link": reverse_lazy("admin:tickets_cannedresponse_changelist")},
                ],
            },
            {
                "title": "Finance",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Invoices", "icon": "receipt", "link": reverse_lazy("admin:finance_invoice_changelist")},
                    {"title": "Quotations", "icon": "description", "link": reverse_lazy("admin:finance_quotation_changelist")},
                    {"title": "Expenses", "icon": "money_off", "link": reverse_lazy("admin:finance_expense_changelist")},
                    {"title": "Plans", "icon": "card_membership", "link": reverse_lazy("admin:finance_plan_changelist")},
                    {"title": "Subscriptions", "icon": "subscriptions", "link": reverse_lazy("admin:finance_clientsubscription_changelist")},
                ],
            },
            {
                "title": "Portfolio",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Projects", "icon": "design_services", "link": reverse_lazy("admin:portfolio_portfolioproject_changelist")},
                    {"title": "Inquiries", "icon": "mail", "link": reverse_lazy("admin:portfolio_inquiry_changelist")},
                    {"title": "Newsletter", "icon": "subscriptions", "link": reverse_lazy("admin:portfolio_newslettersubscriber_changelist")},
                    {"title": "Portfolio Settings", "icon": "settings", "link": reverse_lazy("admin:portfolio_portfoliosettings_changelist")},
                ],
            },
            {
                "title": "Users & Permissions",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "Users", "icon": "manage_accounts", "link": reverse_lazy("admin:accounts_user_changelist")},
                    {"title": "Roles", "icon": "badge", "link": reverse_lazy("admin:accounts_role_changelist")},
                    {"title": "Permissions", "icon": "lock", "link": reverse_lazy("admin:accounts_permission_changelist")},
                    {"title": "Audit Logs", "icon": "history", "link": reverse_lazy("admin:accounts_userauditlog_changelist")},
                    {"title": "Social Applications", "icon": "share", "link": reverse_lazy("admin:socialaccount_socialapp_changelist")},
                    {"title": "Social Accounts", "icon": "people", "link": reverse_lazy("admin:socialaccount_socialaccount_changelist")},
                    {"title": "Email Verification Tokens", "icon": "mark_email_read", "link": reverse_lazy("admin:accounts_emailverificationtoken_changelist")},
                    {"title": "Invitation Tokens", "icon": "email", "link": reverse_lazy("admin:accounts_invitationtoken_changelist")},
                ],
            },
            {
                "title": "Tracking",
                "separator": True,
                "collapsible": True,
                "items": [
                    {"title": "User Activities", "icon": "timeline", "link": reverse_lazy("admin:tracking_useractivity_changelist")},
                    {"title": "Page Visits", "icon": "visibility", "link": reverse_lazy("admin:tracking_pagevisit_changelist")},
                ],
            },
            {
                "title": "Configuration",
                "separator": True,
                "items": [
                    {"title": "Site Settings", "icon": "settings", "link": reverse_lazy("admin:core_siteconfig_changelist")},
                    {"title": "Sites", "icon": "language", "link": reverse_lazy("admin:sites_site_changelist")},
                ],
            },
        ],
    },
    "TABS": [
        {
            "models": ["clients.clientorganization", "clients.clientcontact"],
            "items": [
                {"title": "Organizations", "link": reverse_lazy("admin:clients_clientorganization_changelist")},
                {"title": "Contacts", "link": reverse_lazy("admin:clients_clientcontact_changelist")},
            ],
        },
        {
            "models": ["services.service", "services.servicecategory", "services.servicepackage"],
            "items": [
                {"title": "Services", "link": reverse_lazy("admin:services_service_changelist")},
                {"title": "Categories", "link": reverse_lazy("admin:services_servicecategory_changelist")},
                {"title": "Packages", "link": reverse_lazy("admin:services_servicepackage_changelist")},
            ],
        },
        {
            "models": ["tickets.ticket", "tickets.ticketcomment", "tickets.ticketworklog", "tickets.ticketattachment", "tickets.ticketsla", "tickets.cannedresponse"],
            "items": [
                {"title": "Tickets", "link": reverse_lazy("admin:tickets_ticket_changelist")},
                {"title": "Comments", "link": reverse_lazy("admin:tickets_ticketcomment_changelist")},
                {"title": "Work Logs", "link": reverse_lazy("admin:tickets_ticketworklog_changelist")},
                {"title": "Attachments", "link": reverse_lazy("admin:tickets_ticketattachment_changelist")},
                {"title": "SLAs", "link": reverse_lazy("admin:tickets_ticketsla_changelist")},
                {"title": "Canned Responses", "link": reverse_lazy("admin:tickets_cannedresponse_changelist")},
            ],
        },
        {
            "models": ["finance.invoice", "finance.quotation", "finance.expense", "finance.plan", "finance.clientsubscription"],
            "items": [
                {"title": "Invoices", "link": reverse_lazy("admin:finance_invoice_changelist")},
                {"title": "Quotations", "link": reverse_lazy("admin:finance_quotation_changelist")},
                {"title": "Expenses", "link": reverse_lazy("admin:finance_expense_changelist")},
                {"title": "Plans", "link": reverse_lazy("admin:finance_plan_changelist")},
                {"title": "Subscriptions", "link": reverse_lazy("admin:finance_clientsubscription_changelist")},
            ],
        },
        {
            "models": ["portfolio.portfolioproject", "portfolio.inquiry", "portfolio.newslettersubscriber", "portfolio.portfoliosettings"],
            "items": [
                {"title": "Projects", "link": reverse_lazy("admin:portfolio_portfolioproject_changelist")},
                {"title": "Inquiries", "link": reverse_lazy("admin:portfolio_inquiry_changelist")},
                {"title": "Newsletter", "link": reverse_lazy("admin:portfolio_newslettersubscriber_changelist")},
                {"title": "Portfolio Settings", "link": reverse_lazy("admin:portfolio_portfoliosettings_changelist")},
            ],
        },
        {
            "models": ["accounts.user", "accounts.role", "accounts.permission", "accounts.userrole", "socialaccount.socialapp", "socialaccount.socialaccount"],
            "items": [
                {"title": "Users", "link": reverse_lazy("admin:accounts_user_changelist")},
                {"title": "Roles", "link": reverse_lazy("admin:accounts_role_changelist")},
                {"title": "Permissions", "link": reverse_lazy("admin:accounts_permission_changelist")},
                {"title": "User Roles", "link": reverse_lazy("admin:accounts_userrole_changelist")},
                {"title": "Social Apps", "link": reverse_lazy("admin:socialaccount_socialapp_changelist")},
                {"title": "Social Accounts", "link": reverse_lazy("admin:socialaccount_socialaccount_changelist")},
            ],
        },
        {
            "models": ["tracking.useractivity", "tracking.pagevisit"],
            "items": [
                {"title": "User Activities", "link": reverse_lazy("admin:tracking_useractivity_changelist")},
                {"title": "Page Visits", "link": reverse_lazy("admin:tracking_pagevisit_changelist")},
            ],
        },
        {
            "models": ["core.siteconfig", "sites.site"],
            "items": [
                {"title": "Site Settings", "link": reverse_lazy("admin:core_siteconfig_changelist")},
                {"title": "Sites", "link": reverse_lazy("admin:sites_site_changelist")},
            ],
        },
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

# -----------------------------------------------------------------------------
# QUILL EDITOR CONFIG
# -----------------------------------------------------------------------------
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
