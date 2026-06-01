# Pritech ICT Management System (PIMS)

[![Django Version](https://img.shields.io/badge/django-5.2.7-green)](https://www.djangoproject.com/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Pritech System** is a modern, AI‑ready ERP platform designed for **Pritech Systems Malawi**. It centralises client management, ICT service delivery, support ticketing, financial operations, and business intelligence into one unified system.

> 🚀 **Live Demo** – *Coming soon*  
> 📖 **Documentation** – [Wiki](https://github.com/your-repo/wiki)

---

## ✨ Features

### 👥 Client Management
- Client organisations with contacts, industry, status (active/lead/inactive)
- Full client self‑service portal (invoices, quotations, tickets, team management)
- Role‑based access for staff (Admin, Sales, Finance, Technician)

### 🛠️ Service Catalogue
- Service categories with icons
- Services (one‑time / recurring), packages
- Client‑friendly service catalog with “Request Quotation”

### 🎫 Support Ticketing
- Full ticket lifecycle (open → assigned → in progress → resolved → closed)
- SLA deadlines (response & resolution based on priority)
- Work logs, comments (internal / public), file attachments (drag & drop)
- Mark comment as solution, canned responses for staff
- Email notifications (ticket creation, status change) – *SMTP config required*

### 💰 Financial Management
- Quotations → client approval → automatic invoice creation
- Invoices (draft, issued, partial, paid, overdue, cancelled)
- Payment recording (cash, bank transfer, mobile money)
- Expenses with approval workflow
- Financial reports: income statement, accounts receivable aging, top clients, monthly trends
- Branded PDF invoices & quotations (with company logo)
- Subscription plans & recurring monthly invoicing (Celery task)

### 🔐 Security & Access Control
- Custom user model with email/phone authentication
- Role‑based permissions (ADMIN, TECHNICIAN, FINANCE, CLIENT)
- Two‑factor authentication (TOTP) – optional
- Social login (Google, LinkedIn) via django‑allauth
- Rate limiting on login, registration, PDF generation
- HTML sanitisation (bleach) to prevent XSS in rich text fields
- Audit logs (user login, page visits, model history via simple_history)

### 📊 Dashboards & Real‑time
- Staff dashboard with key metrics, charts, recent tickets/invoices
- Client dashboard tailored to their organisation
- HTMX for live ticket search, inline status updates, comment posting
- Celery background tasks (SLA breach checks, subscription invoicing, async PDF generation)

### 🖥️ Admin Interface
- Modern Unfold admin theme with collapsible sidebar and tabs
- Full management of users, roles, permissions, social apps, sites

---

## 🛠️ Tech Stack

| Layer               | Technology                                                        |
|---------------------|-------------------------------------------------------------------|
| Backend             | Django 5.2.7, Celery, Redis                                       |
| Database            | SQLite (dev) / PostgreSQL (production)                            |
| Frontend            | Bootstrap 5, HTMX, custom CSS (mobile‑first)                      |
| Authentication      | django‑allauth, django‑otp                                        |
| PDF Generation      | WeasyPrint (sanitised with bleach)                                |
| Caching             | Django cache framework (database / Redis)                         |
| Task Queue          | Celery + Redis (or RabbitMQ)                                      |
| Admin Theme         | Unfold                                                            |

---

## 📦 Installation

### Prerequisites
- Python 3.11+
- Redis (for Celery) – optional but recommended
- PostgreSQL (production) or SQLite (development)

### Step‑by‑step

```bash
# 1. Clone the repository
git clone https://github.com/your-org/pritech.git
cd pritech

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (create .env file)
cp .env.example .env
# Edit .env with your SECRET_KEY, DATABASE_URL, EMAIL settings, etc.

# 5. Run migrations
python manage.py migrate

# 6. Seed demo data (optional)
python manage.py seed

# 7. Create superuser (if not using seed)
python manage.py createsuperuser

# 8. Start development server
python manage.py runserver
```

Access the application at `http://127.0.0.1:8000`

---

## ⚙️ Configuration

### Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Django secret key – **change in production** |
| `DEBUG` | Set to `False` in production |
| `ALLOWED_HOSTS` | Comma‑separated list of domains |
| `DATABASE_URL` | e.g. `postgres://user:pass@localhost/db` |
| `REDIS_URL` | For Celery broker (e.g. `redis://localhost:6379/0`) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | SMTP settings |
| `LINKEDIN_CLIENT_ID`, `LINKEDIN_SECRET` | For LinkedIn OAuth |
| `GOOGLE_CLIENT_ID`, `GOOGLE_SECRET` | For Google OAuth |

### Social Login Setup
1. Create OAuth applications on [Google Cloud Console](https://console.cloud.google.com/) and [LinkedIn Developer Portal](https://www.linkedin.com/developers/).
2. Add `SocialApp` records in Django admin (`/admin/socialaccount/socialapp/`).
3. Set redirect URIs:
   - Google: `http://127.0.0.1:8000/accounts/google/login/callback/`
   - LinkedIn: `http://127.0.0.1:8000/accounts/linkedin_oauth2/login/callback/`

### Celery (for production)
```bash
celery -A pritech worker -l info
celery -A pritech beat -l info   # for periodic tasks
```

---

## 🧪 Testing

Run the test suite (once written):

```bash
python manage.py test
```

Currently the project has no automated tests – **contribution welcome**.

---

## 🚀 Deployment

### Production Checklist

- [ ] Set `DEBUG=False`, `ALLOWED_HOSTS=[your-domain.com]`
- [ ] Use PostgreSQL database
- [ ] Configure HTTPS (SSL certificate)
- [ ] Set secure cookies: `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`
- [ ] Configure real email backend (SMTP)
- [ ] Run `python manage.py collectstatic`
- [ ] Use a production WSGI server (Gunicorn / uWSGI)
- [ ] Set up Celery with Redis/RabbitMQ and a supervisor
- [ ] Enable caching (Redis or Memcached)

### Example with Gunicorn + Nginx

```bash
# Install Gunicorn
pip install gunicorn

# Start Gunicorn
gunicorn pritech.wsgi:application --bind 0.0.0.0:8000
```

See `deployment/nginx.conf` for a sample Nginx configuration (not included – to be added).

---

## 📁 Project Structure

```
pritech/
├── accounts/          # Custom user model, roles, permissions, 2FA, social auth
├── clients/           # Client organisations, contacts, views
├── core/              # Site config, dashboard, context processors, admin badges
├── finance/           # Invoices, quotations, payments, expenses, reports, subscriptions
├── portfolio/         # Public site, projects, newsletter
├── services/          # Service catalogue, categories, packages
├── tickets/           # Tickets, SLA, comments, work logs, attachments
├── tracking/          # Page visits, user activity
├── infrastructure/    # PDF generation, notifications, sanitisation helpers
├── templates/         # Base templates, partials, email templates
├── static/            # CSS, JS, images
└── pritech/           # Project settings, URLs, Celery config
```

---

## 🤝 Contributing

Contributions are welcome! Please follow the standard GitHub flow:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing`)
5. Open a Pull Request

For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- Django community
- Bootstrap, HTMX, Unfold
- All open‑source libraries used

---

## 📞 Support

For questions or support, please contact:
- **Email**: info@pritech.mw
- **Issue Tracker**: [GitHub Issues](https://github.com/your-org/pritech/issues)

---

## 🗺️ Roadmap

### ✅ Completed
- Core RBAC, client management, ticketing, finance (quotations, invoices, payments, expenses)
- Client self‑service portal (approve quotes, view invoices, manage team)
- Real‑time HTMX interactions, PDF generation, Celery tasks
- 2FA, social login, rate limiting, sanitisation, audit logs

### 🔄 In Progress
- Email notifications (templates ready, SMTP needed)
- Online payment gateway integration
- Mobile app (API first)

### 📅 Planned
- AI features: revenue forecasting, service recommendations, anomaly detection
- Multi‑tenant SaaS offering
- Advanced analytics with drill‑downs
- WebSocket real‑time dashboards

---

**Built with ❤️ for Pritech Systems Malawi**
```

This README provides a clear, professional overview of the project, its capabilities, and how to get started. It also highlights the current gaps (email, payment gateway, AI) and future plans, which is honest and helps set expectations.
