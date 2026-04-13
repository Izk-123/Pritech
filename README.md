# PIMS — Pritech ICT Management System

Full Django ERP for ICT service businesses. Mobile‑first, production‑ready, HTMX‑powered.

---

## Quick Start

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
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

### Public & Core
| Page             | URL                      |
|------------------|--------------------------|
| Public site      | /                        |
| Dashboard        | /dashboard/              |
| My Profile       | /accounts/profile/       |
| Admin Panel      | /admin/                  |

### Management
| Page             | URL                      |
|------------------|--------------------------|
| Clients          | /clients/                |
| Tickets          | /tickets/                |
| Services         | /services/               |
| → Categories     | /services/categories/    |
| → Packages       | /services/packages/      |

### Finance (Staff)
| Page             | URL                         |
|------------------|-----------------------------|
| Quotations       | /finance/quotations/        |
| Invoices         | /finance/invoices/          |
| Expenses         | /finance/expenses/          |
| Financial Reports| /finance/reports/           |

### Finance (Client Portal)
| Page             | URL                               |
|------------------|-----------------------------------|
| My Quotations    | /finance/client/quotations/       |
| My Invoices      | /finance/client/invoices/         |

### System Monitoring
| Page             | URL                      |
|------------------|--------------------------|
| Audit Log        | /dashboard/audit/        |
| Page Visits      | /dashboard/visits/       |

---

## Architecture

### Authentication
- Email **or** phone number + password login
- Custom `EmailOrPhoneBackend` handles both
- Session‑based with IP + user‑agent tracking
- Login/logout/failed‑login all logged to `UserAuditLog` via Django signals

### Authorization (RBAC)
- Roles: Administrator, Technician, Finance Officer, Client
- Permissions: `manage_invoices`, `manage_tickets`, `view_reports`, `manage_users`
- Enforced at view level via `RoleRequiredMixin` / `PermissionRequiredMixin`
- Decorators available for FBVs: `@role_required('ADMIN')`, `@permission_required('can_generate_reports')`
- Template‑level hiding with `{% if request.user.has_role('ADMIN') %}`

### Services App (Enhanced)
- **Service Categories**: Organise services with icons and descriptions.
- **Service Model**: Now includes `billing_type` (One Time / Recurring) for future recurring billing.
- **Service Packages**: Bundle multiple services into a fixed‑price monthly package.
- **Role‑Based Views**: Only Admins can create/edit services, categories, and packages; all staff can view.
- Admin interface fully supports all new fields and relations.

### Finance Workflow (Complete)
- **Quotations**: Create, send, approve, convert to invoice
- **Invoices**: Issue, record partial/full payments, track status (draft → issued → partial → paid → overdue)
- **Expenses**: Categorized expense tracking
- **Reports**: Income statement, accounts receivable aging, monthly trends, top clients
- **PDF Generation**: Branded invoices (download/view)
- **Email Notifications**: Sent on invoice issuance and payment receipt

### Real‑time (HTMX)
- **Ticket status transitions** — swap without page reload
- **Comments** — append new comment to list without reload
- **Work log** — append entries without reload
- **Ticket assignment** — update panel in‑place
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
ALLOWED_HOSTS = ['pritechmw.com', 'www.pritechmw.com', '204.168.251.91']
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
| 2     | ✅ Done    | Quotations, PDF invoices, financial reports, email alerts, **Service Categories & Packages**, Recurring billing flag |
| 3     | Planned    | WebSocket notifications, advanced analytics  |
| 4     | Future     | AI predictions, smart recommendations        |
```

The updated `README.md` now accurately reflects the **Services** enhancements (categories, packages, billing types) alongside the complete finance and RBAC features already present.