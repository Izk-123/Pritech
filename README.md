# PIMS — Pritech ICT Management System

Full Django ERP for ICT service businesses. Mobile-first, production-ready, HTMX-powered.

---

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install django pillow
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Open **http://127.0.0.1:8000**

---

## Login Credentials

| Role           | Email                  | Password  | Phone (alt login)  |
|----------------|------------------------|-----------|--------------------|
| Administrator  | admin@pritech.mw       | admin123  | +265111000001      |
| Technician     | tech@pritech.mw        | tech123   | —                  |
| Finance        | finance@pritech.mw     | fin123    | —                  |
| Client         | client@acme.mw         | client123 | —                  |

---

## System URLs

| Page             | URL                      |
|------------------|--------------------------|
| Public site      | /                        |
| Dashboard        | /dashboard/              |
| Clients          | /clients/                |
| Tickets          | /tickets/                |
| Services         | /services/               |
| Invoices         | /finance/invoices/       |
| Expenses         | /finance/expenses/       |
| Audit Log        | /dashboard/audit/        |
| Page Visits      | /dashboard/visits/       |
| My Profile       | /accounts/profile/       |
| Admin Panel      | /admin/                  |

---

## Architecture

### Authentication
- Email **or** phone number + password login
- Custom `EmailOrPhoneBackend` handles both
- Session-based with IP + user-agent tracking
- Login/logout/failed-login all logged to `UserAuditLog` via Django signals

### Authorization (RBAC)
- Roles: Administrator, Technician, Finance Officer, Client
- Permissions: `manage_invoices`, `manage_tickets`, `view_reports`, `manage_users`
- Enforced at view level via `RoleRequiredMixin` / `PermissionRequiredMixin`
- Decorators available for FBVs: `@role_required('ADMIN')`, `@permission_required('can_generate_reports')`
- Template-level hiding with `{% if request.user.has_role('ADMIN') %}`

### Real-time (HTMX)
- **Ticket status transitions** — swap without page reload
- **Comments** — append new comment to list without reload
- **Work log** — append entries without reload
- **Ticket assignment** — update panel in-place
- **Live ticket search** — 300ms debounce, filters as you type
- **Status/priority dropdowns** — filter table live on change

### Tracking
- `ActivityMiddleware` — logs every page visit (URL, IP, user, timestamp)
- `LastLoginIPMiddleware` — records current IP on each request
- Audit log viewable at `/dashboard/audit/`
- Page visits viewable at `/dashboard/visits/`

---

## RBAC Quick Reference

```python
# In a CBV
from core.mixins import RoleRequiredMixin

class ReportView(RoleRequiredMixin, TemplateView):
    required_roles = ['ADMIN', 'FINANCE']

# In a FBV
from core.decorators import role_required, permission_required

@role_required('ADMIN')
def admin_only(request): ...

@permission_required('manage_invoices')
def invoices(request): ...

# In a template
{% if request.user.has_role('ADMIN') %}
  <a href="...">Admin only link</a>
{% endif %}
```

---

## Production Deployment

```bash
# settings.py — switch to PostgreSQL
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
  'NAME': 'pritech_db', 'USER': 'pritech', 'PASSWORD': 'yourpassword', 'HOST': 'localhost'}}

DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
SECRET_KEY = 'generate-a-real-key'

python manage.py collectstatic
gunicorn pritech.wsgi:application --bind 0.0.0.0:8000
```

---

## Phase Roadmap

| Phase | Status     | Features                                     |
|-------|------------|----------------------------------------------|
| 1     | ✅ Done    | Auth, Clients, Tickets, Finance, Services    |
| 1b    | ✅ Done    | RBAC, Phone login, HTMX, Audit log, Tracking |
| 2     | Next       | PDF invoices, financial reports, email alerts|
| 3     | Planned    | WebSocket notifications, analytics charts    |
| 4     | Future     | AI predictions, smart recommendations        |
