import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'django-insecure-pritech-dev-key-change-in-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

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
    'django_htmx',                       # ← add this
    'core', 'accounts', 'clients', 'services', 'tickets', 'finance', 'portfolio', 'tracking',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django_htmx.middleware.HtmxMiddleware',   # ← add here (after SessionMiddleware)
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
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context_processors.site_config',
        'core.context_processors.sidebar_recent_items',
        'portfolio.context_processors.portfolio_settings',
        'django.template.context_processors.request',  # required by Unfold
    ]},
}]

WSGI_APPLICATION = 'pritech.wsgi.application'

# ── Database ──
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Blantyre'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

VAT_RATE = 0.175
CURRENCY = 'MWK'
CURRENCY_SYMBOL = 'K'

# ── EMAIL CONFIGURATION ──
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
    EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

# ═══════════════ UNFOLD CONFIGURATION ═══════════════
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
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
            "href": lambda request: static("images/logo.png"),
        },
    ],
    "DASHBOARD_CALLBACK": "core.dashboard.dashboard_callback",
    "INDEX_VIEW": "core.admin_views.htmx_admin_index",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": True,
    "ENVIRONMENT": "Development" if DEBUG else "Production",
    "COLORS": {
        "primary": {
            "50": "238 242 255",
            "100": "224 231 255",
            "200": "199 210 255",
            "300": "165 180 252",
            "400": "129 148 248",
            "500": "65 84 241",          # your brand #4154f1
            "600": "53 70 217",
            "700": "45 57 191",
            "800": "38 47 159",
            "900": "30 37 130",
            "950": "21 26 95",
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
                    {
                        "title": "Overview",
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                    {
                        "title": "View Website",
                        "icon": "open_in_new",
                        "link": "/",
                        "target": "_blank",
                    },
                ],
            },
            {
                "title": "Clients",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Organizations",
                        "icon": "corporate_fare",
                        "link": reverse_lazy("admin:clients_clientorganization_changelist"),
                    },
                    {
                        "title": "Contacts",
                        "icon": "contacts",
                        "link": reverse_lazy("admin:clients_clientcontact_changelist"),
                    },
                ],
            },
            {
                "title": "Services",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Services",
                        "icon": "miscellaneous_services",
                        "link": reverse_lazy("admin:services_service_changelist"),
                    },
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": reverse_lazy("admin:services_servicecategory_changelist"),
                    },
                    {
                        "title": "Packages",
                        "icon": "package_2",
                        "link": reverse_lazy("admin:services_servicepackage_changelist"),
                    },
                ],
            },
            {
                "title": "Support",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Tickets",
                        "icon": "support_agent",
                        "link": reverse_lazy("admin:tickets_ticket_changelist"),
                        "badge": "core.admin_badges.open_tickets",
                    },
                    {
                        "title": "Attachments",
                        "icon": "attach_file",
                        "link": reverse_lazy("admin:tickets_ticketattachment_changelist"),
                    },
                    {
                        "title": "SLAs",
                        "icon": "timer",
                        "link": reverse_lazy("admin:tickets_ticketsla_changelist"),
                    },
                ],
            },
            {
                "title": "Finance",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Invoices",
                        "icon": "receipt",
                        "link": reverse_lazy("admin:finance_invoice_changelist"),
                    },
                    {
                        "title": "Quotations",
                        "icon": "description",
                        "link": reverse_lazy("admin:finance_quotation_changelist"),
                    },
                    {
                        "title": "Expenses",
                        "icon": "money_off",
                        "link": reverse_lazy("admin:finance_expense_changelist"),
                    },
                ],
            },
            {
                "title": "Portfolio",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Projects",
                        "icon": "design_services",
                        "link": reverse_lazy("admin:portfolio_portfolioproject_changelist"),
                    },
                    {
                        "title": "Inquiries",
                        "icon": "mail",
                        "link": reverse_lazy("admin:portfolio_inquiry_changelist"),
                        "badge": "core.admin_badges.unread_inquiries",
                    },
                    {
                        "title": "Newsletter",
                        "icon": "subscriptions",
                        "link": reverse_lazy("admin:portfolio_newslettersubscriber_changelist"),
                    },
                ],
            },
            {
                "title": "Users & Permissions",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "Users",
                        "icon": "manage_accounts",
                        "link": reverse_lazy("admin:accounts_user_changelist"),
                    },
                    {
                        "title": "Roles",
                        "icon": "badge",
                        "link": reverse_lazy("admin:accounts_role_changelist"),
                    },
                    {
                        "title": "Permissions",
                        "icon": "lock",
                        "link": reverse_lazy("admin:accounts_permission_changelist"),
                    },
                    {
                        "title": "Audit Logs",
                        "icon": "history",
                        "link": reverse_lazy("admin:accounts_userauditlog_changelist"),
                    },
                ],
            },
            {
                "title": "Tracking",
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": "User Activities",
                        "icon": "timeline",
                        "link": reverse_lazy("admin:tracking_useractivity_changelist"),
                    },
                    {
                        "title": "Page Visits",
                        "icon": "visibility",
                        "link": reverse_lazy("admin:tracking_pagevisit_changelist"),
                    },
                ],
            },
            {
                "title": "Configuration",
                "separator": True,
                "items": [
                    {
                        "title": "Site Settings",
                        "icon": "settings",
                        "link": reverse_lazy("admin:core_siteconfig_changelist"),
                    },
                ],
            },
        ],
    },
    "TABS": [
        {
            "models": ["clients.clientorganization", "clients.clientcontact"],
            "items": [
                {"title": "Organizations", "link": reverse_lazy("admin:clients_clientorganization_changelist")},
                {"title": "Contacts",      "link": reverse_lazy("admin:clients_clientcontact_changelist")},
            ],
        },
        {
            "models": ["services.service", "services.servicecategory", "services.servicepackage"],
            "items": [
                {"title": "Services",   "link": reverse_lazy("admin:services_service_changelist")},
                {"title": "Categories", "link": reverse_lazy("admin:services_servicecategory_changelist")},
                {"title": "Packages",   "link": reverse_lazy("admin:services_servicepackage_changelist")},
            ],
        },
        {
            "models": ["tickets.ticket", "tickets.ticketattachment", "tickets.ticketsla"],
            "items": [
                {"title": "Tickets",     "link": reverse_lazy("admin:tickets_ticket_changelist")},
                {"title": "Attachments", "link": reverse_lazy("admin:tickets_ticketattachment_changelist")},
                {"title": "SLAs",        "link": reverse_lazy("admin:tickets_ticketsla_changelist")},
            ],
        },
        {
            "models": ["finance.invoice", "finance.quotation", "finance.expense"],
            "items": [
                {"title": "Invoices",   "link": reverse_lazy("admin:finance_invoice_changelist")},
                {"title": "Quotations", "link": reverse_lazy("admin:finance_quotation_changelist")},
                {"title": "Expenses",   "link": reverse_lazy("admin:finance_expense_changelist")},
            ],
        },
        {
            "models": ["portfolio.portfolioproject", "portfolio.inquiry", "portfolio.newslettersubscriber"],
            "items": [
                {"title": "Projects",   "link": reverse_lazy("admin:portfolio_portfolioproject_changelist")},
                {"title": "Inquiries",  "link": reverse_lazy("admin:portfolio_inquiry_changelist")},
                {"title": "Subscribers","link": reverse_lazy("admin:portfolio_newslettersubscriber_changelist")},
            ],
        },
        {
            "models": ["accounts.user", "accounts.role", "accounts.permission"],
            "items": [
                {"title": "Users",       "link": reverse_lazy("admin:accounts_user_changelist")},
                {"title": "Roles",       "link": reverse_lazy("admin:accounts_role_changelist")},
                {"title": "Permissions", "link": reverse_lazy("admin:accounts_permission_changelist")},
            ],
        },
    ],
    "STYLES": [
        lambda request: static("css/unfold-overrides.css"),
    ],
    "SCRIPTS": [],
    "EXTRA_SCRIPTS": [
        {
            "src": "https://unpkg.com/htmx.org@1.9.10",
            "integrity": "sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2",
            "crossorigin": "anonymous",
        },
    ],
}

# ═══════════════ QUILL EDITOR CONFIG ═══════════════
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
