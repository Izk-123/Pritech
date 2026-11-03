# core/management/commands/seed.py
"""
Comprehensive seeding script for Pritech ERP – with realistic data.
Seeds all apps: accounts, clients, services, tickets, finance, portfolio, and core.
Includes:
- Real staff: Isaac Ndoka, Prince Chipeta, Portia Domasi
- Real clients: J&N, MAME (2 projects), Villa Grande, Abby Investment, Hillcrest Primary
- Exact QUO-0001 for Villa Grande
- Subscriptions, tickets, invoices, quotations, expenses, analytics
- Core models: site config, branches, widgets, announcements, activity feed
"""

import json
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.base import ContentFile

# Try to import Pillow for image generation (optional)
try:
    from PIL import Image, ImageDraw
    from io import BytesIO
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from tickets.models import Ticket
from finance.models import Plan, ClientSubscription
from tickets.models import CannedResponse
from services.models import Service, ServiceCategory, ServicePackage
from clients.models import ClientOrganization, ClientContact
from accounts.models import (
    Role, Permission, UserRole, RolePermission,
    UserProfile, UserSession, LoginEvent, RecoveryCode
)
from core.models import (
    SiteConfig, CompanyBranch, DashboardWidget,
    Announcement, ActivityFeed, SystemNotification
)
from portfolio.models import (
    PortfolioCategory, PortfolioTechnology, PortfolioProject,
    PortfolioImage, Testimonial, PortfolioSettings
)

User = get_user_model()


def to_quill_json(text):
    """Convert plain text to Quill JSON format."""
    return json.dumps({"html": f"<p>{text}</p>", "delta": ""})


def create_placeholder_image(width=600, height=400, bg_color=(14, 165, 233), text_color=(255, 255, 255), text=""):
    if not HAS_PIL:
        return None
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    draw.text((width//2, height//2), text or "Pritech", fill=text_color, anchor="mm")
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return ContentFile(buffer.getvalue(), name=f"{text.replace(' ', '_')}.jpg")


class Command(BaseCommand):
    help = 'Seed the database with realistic Pritech demo data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database with real‑world Pritech data...')

        # ── Site config ──────────────────────────────────────────────────────
        cfg = SiteConfig.get()
        cfg.company_name = 'Pritech ICT Solutions'
        cfg.tagline = 'Delivering reliable ICT solutions for businesses across Malawi'
        cfg.email = 'info@pritechmw.com'
        cfg.phone = '+265 999 777 822'
        cfg.address = 'Area 51/24 Kanengo, Lilongwe, Malawi'
        cfg.bank_name = 'National Bank of Malawi'
        cfg.bank_account = '1234567890'
        cfg.mobile_money = '+265 888 123 456'
        cfg.invoice_footer = 'Thank you for your business! Payment due within 30 days.'
        cfg.maintenance_mode = False
        cfg.vat_rate = 0.175   # 17.5%
        cfg.save()
        self.stdout.write('  ✓ Site config')

        # ── Company Branch ──────────────────────────────────────────────────
        CompanyBranch.objects.get_or_create(
            name='Head Office - Lilongwe',
            defaults={
                'address': 'Area 51/24 Kanengo, Lilongwe, Malawi',
                'phone': '+265 999 777 822',
                'email': 'info@pritechmw.com',
                'is_main': True
            }
        )
        self.stdout.write('  ✓ Company branches created')

        # ── Dashboard Widgets ──────────────────────────────────────────────
        admin_role, _ = Role.objects.get_or_create(code='ADMIN', defaults={'name': 'Administrator'})
        finance_role, _ = Role.objects.get_or_create(code='FINANCE', defaults={'name': 'Finance Officer'})
        tech_role, _ = Role.objects.get_or_create(code='TECHNICIAN', defaults={'name': 'Technician'})
        client_role, _ = Role.objects.get_or_create(code='CLIENT', defaults={'name': 'Client'})

        widgets_data = [
            {'name': 'Revenue Overview', 'code': 'revenue_overview', 'description': 'Monthly revenue and pending revenue', 'roles': [admin_role, finance_role]},
            {'name': 'Client Statistics', 'code': 'client_stats', 'description': 'Total and active clients', 'roles': [admin_role, finance_role]},
            {'name': 'Ticket Status', 'code': 'ticket_status', 'description': 'Open tickets by status', 'roles': [admin_role, tech_role]},
            {'name': 'Recent Tickets', 'code': 'recent_tickets', 'description': 'Latest 5 tickets', 'roles': []},
            {'name': 'Recent Invoices', 'code': 'recent_invoices', 'description': 'Latest invoices', 'roles': [admin_role, finance_role]},
            {'name': 'Assigned to Me', 'code': 'assigned_tickets', 'description': 'Tickets assigned to the logged-in user', 'roles': [tech_role]},
            {'name': 'My Services', 'code': 'my_services', 'description': 'Client services overview', 'roles': [client_role]},
        ]
        for wdata in widgets_data:
            widget, created = DashboardWidget.objects.get_or_create(
                code=wdata['code'],
                defaults={
                    'name': wdata['name'],
                    'description': wdata['description'],
                    'is_active': True,
                    'order': 0
                }
            )
            if created and wdata['roles']:
                widget.roles.set(wdata['roles'])
        self.stdout.write('  ✓ Dashboard widgets created')

        # ── Announcements ──────────────────────────────────────────────────
        now = timezone.now()
        Announcement.objects.get_or_create(
            title='Welcome to Pritech ERP',
            defaults={
                'message': 'We are excited to have you on board! Explore the new dashboard and real‑time updates.',
                'start_date': now - timedelta(days=5),
                'end_date': now + timedelta(days=10),
                'is_active': True,
            }
        )
        Announcement.objects.get_or_create(
            title='Scheduled Maintenance – Sunday',
            defaults={
                'message': 'System maintenance on Sunday, 2 AM – 4 AM. Downtime expected.',
                'start_date': now + timedelta(days=3),
                'end_date': now + timedelta(days=4),
                'is_active': True,
            }
        )
        Announcement.objects.get_or_create(
            title='New Feature: Global Search',
            defaults={
                'message': 'You can now search across clients, tickets, invoices, and services from the top bar.',
                'start_date': now - timedelta(days=1),
                'end_date': now + timedelta(days=30),
                'is_active': True,
            }
        )
        self.stdout.write('  ✓ Announcements created')

        # ── Activity Feed initial entry ───────────────────────────────────
        ActivityFeed.objects.get_or_create(
            module='system',
            action='System seeded with demo data',
            defaults={'user': None, 'object_id': ''}
        )
        self.stdout.write('  ✓ Initial activity feed entry')

        # ── Roles & Permissions ──────────────────────────────────────────
        roles = {}
        for code, name in [('ADMIN', 'Administrator'), ('TECHNICIAN', 'Technician'),
                           ('FINANCE', 'Finance Officer'), ('CLIENT', 'Client')]:
            r, _ = Role.objects.get_or_create(code=code, defaults={'name': name})
            roles[code] = r

        perms = {}
        for code, desc in [
            ('view_reports', 'View financial reports'),
            ('manage_users', 'Manage users'),
            ('manage_invoices', 'Manage invoices'),
            ('manage_tickets', 'Manage tickets'),
            ('view_finance_dashboard', 'Access finance dashboard and menu'),
        ]:
            p, _ = Permission.objects.get_or_create(code=code, defaults={'description': desc})
            perms[code] = p

        for perm in perms.values():
            RolePermission.objects.get_or_create(role=roles['ADMIN'], permission=perm)

        RolePermission.objects.get_or_create(role=roles['FINANCE'], permission=perms['manage_invoices'])
        RolePermission.objects.get_or_create(role=roles['FINANCE'], permission=perms['view_reports'])
        RolePermission.objects.get_or_create(role=roles['FINANCE'], permission=perms['view_finance_dashboard'])
        RolePermission.objects.get_or_create(role=roles['TECHNICIAN'], permission=perms['manage_tickets'])
        self.stdout.write('  ✓ Roles & permissions')

        # ── REAL STAFF USERS ──────────────────────────────────────────────
        isaac = self._create_user(
            email='isaacndoka7@gmail.com',
            first='Isaac',
            last='Ndoka',
            password='admin123',
            user_type='staff',
            is_superuser=True,
            phone='+265 886 166 498'
        )
        UserRole.objects.get_or_create(user=isaac, role=roles['ADMIN'])
        UserProfile.objects.get_or_create(user=isaac, defaults={'bio': 'Co-founder & ICT Director'})

        prince = self._create_user(
            email='info@pritechmw.com',
            first='Prince',
            last='Chipeta',
            password='admin123',
            user_type='staff',
            is_superuser=True,
            phone='+265 997 779 822'
        )
        UserRole.objects.get_or_create(user=prince, role=roles['ADMIN'])
        UserProfile.objects.get_or_create(user=prince, defaults={'bio': 'Co-founder & Technical Lead'})

        portia = self._create_user(
            email='sales@pritechmw.com',
            first='Portia',
            last='Domasi',
            password='fin123',
            user_type='staff',
            is_superuser=False,
            phone='+265 887 729 829'
        )
        UserRole.objects.get_or_create(user=portia, role=roles['FINANCE'])
        UserProfile.objects.get_or_create(user=portia, defaults={'bio': 'Sales & Finance Manager'})

        self.stdout.write('  ✓ Staff users created (Isaac, Prince, Portia)')

        # ── SYSTEM NOTIFICATIONS FOR STAFF ──────────────────────────────
        for user in [isaac, prince, portia]:
            SystemNotification.objects.get_or_create(
                user=user,
                title='Welcome to Pritech',
                defaults={
                    'message': 'Thank you for joining the Pritech ERP platform.',
                    'notification_type': 'success',
                    'is_read': False,
                }
            )

        # ── Services (needed for projects and tickets) ──────────────────
        cats = {}
        for name, icon in [('Networking', '🌐'), ('Hardware', '🖥'), ('Software', '💻'),
                           ('Security', '🔒'), ('Training', '🎓')]:
            c, _ = ServiceCategory.objects.get_or_create(name=name, defaults={'icon': icon})
            cats[name] = c

        services_data = [
            ('Network Installation', 'Networking', 85000, 'job', 'one_time'),
            ('Wireless Setup', 'Networking', 45000, 'job', 'one_time'),
            ('IT Support – On-site', 'Hardware', 15000, 'visit', 'recurring'),
            ('Computer Repair', 'Hardware', 20000, 'job', 'one_time'),
            ('Website Development', 'Software', 250000, 'project', 'one_time'),
            ('Software Installation', 'Software', 8000, 'job', 'one_time'),
            ('CCTV Installation', 'Security', 120000, 'job', 'one_time'),
            ('Firewall Setup', 'Security', 95000, 'job', 'one_time'),
            ('Staff ICT Training', 'Training', 50000, 'day', 'recurring'),
        ]
        svcs = {}
        for name, cat, price, unit, billing_type in services_data:
            s, _ = Service.objects.get_or_create(
                name=name,
                defaults={
                    'category': cats[cat],
                    'base_price': price,
                    'unit': unit,
                    'billing_type': billing_type,
                }
            )
            svcs[name] = s
        self.stdout.write('  ✓ Services created')

        # ── CLIENT ORGANISATIONS (with linked client users and projects) ──
        clients_data = [
            {
                'name': 'J&N Private Ltd',
                'industry': 'construction',
                'email': 'info@jandn.mw',
                'phone': '+265 999 261 921',
                'address': 'Area 51/24 Kanengo, Lilongwe, Malawi',
                'website': 'https://jandn.mw',
                'contact_name': 'James Banda',
                'contact_role': 'Managing Director',
                'contact_email': 'james@jandn.mw',
                'contact_phone': '+265 999 261 921',
                'client_user_email': 'client.jn@pritech.mw',
                'client_user_first': 'James',
                'client_user_last': 'Banda',
                'password': 'client123',
                'client_role': 'admin',
                'website_projects': [
                    {
                        'title': 'J&N Private Ltd – Corporate Website',
                        'description': 'Professional corporate website for J&N Private Ltd, showcasing construction projects, company profile, and contact information.',
                        'project_url': 'https://jandn.mw',
                        'completion_date': date(2024, 3, 15),
                        'is_featured': True,
                        'order': 1,
                        'technologies': ['Django', 'React', 'PostgreSQL'],
                        'services': ['Website Development'],
                    }
                ]
            },
            {
                'name': 'MAME Foods & Car Hire',
                'industry': 'food',
                'email': 'info@mamefoods.mw',
                'phone': '+265 999 950 489',
                'address': 'MAME House, Plot 10/069, Luther Street, Area 10, Lilongwe',
                'website': 'https://mamefoods.com',
                'contact_name': 'Mary Mwale',
                'contact_role': 'Managing Director',
                'contact_email': 'mary@mamefoods.mw',
                'contact_phone': '+265 999 950 489',
                'client_user_email': 'client.mame@pritech.mw',
                'client_user_first': 'Mary',
                'client_user_last': 'Mwale',
                'password': 'client123',
                'client_role': 'admin',
                'website_projects': [
                    {
                        'title': 'MAME Car Hire – Online Booking',
                        'description': 'Fleet management and online booking platform for MAME Car Hire, allowing customers to reserve vehicles, view availability, and manage bookings in real time.',
                        'project_url': 'https://mamecarhire.com',
                        'completion_date': date(2024, 6, 20),
                        'is_featured': True,
                        'order': 2,
                        'technologies': ['Django', 'Flutter', 'PostgreSQL'],
                        'services': ['Website Development', 'Software Installation'],
                    },
                    {
                        'title': 'MAME Foods – E‑Commerce & Delivery',
                        'description': 'E‑commerce platform for MAME Foods, enabling online ordering, payment integration, and delivery tracking for food products.',
                        'project_url': 'https://mamefoods.com',
                        'completion_date': date(2024, 8, 15),
                        'is_featured': True,
                        'order': 3,
                        'technologies': ['Django', 'React', 'PostgreSQL'],
                        'services': ['Website Development'],
                    }
                ]
            },
            {
                'name': 'Villa Grande Motel',
                'industry': 'hospitality',
                'email': 'reservations@villagrandemw.com',
                'phone': '+265 997 000 019',
                'address': 'M1 Kaphiri, Area 38, Lilongwe, Malawi',
                'website': 'https://villagrandemw.com',
                'contact_name': 'Grace Mhango',
                'contact_role': 'Manager',
                'contact_email': 'grace@villagrandemw.com',
                'contact_phone': '+265 997 000 019',
                'client_user_email': 'client.villa@pritech.mw',
                'client_user_first': 'Grace',
                'client_user_last': 'Mhango',
                'password': 'client123',
                'client_role': 'admin',
                'website_projects': [
                    {
                        'title': 'Villa Grande Motel',
                        'description': 'Online booking system for Villa Grande Motel, with room management, reservation engine, and real‑time availability.',
                        'project_url': 'https://villagrandemw.com',
                        'completion_date': date(2024, 9, 10),
                        'is_featured': True,
                        'order': 4,
                        'technologies': ['Django', 'React', 'PostgreSQL'],
                        'services': ['Website Development'],
                    }
                ]
            },
            {
                'name': 'Abby Investment – Cleaning Services',
                'industry': 'services',
                'email': 'emwikho@abbysinvestment.com',
                'phone': '+265 994 883 759',
                'address': 'Kawale 1, Behind Enjen Filling Station, Lilongwe, Malawi',
                'website': 'https://abbysinvestment.com',
                'contact_name': 'Abigail Chimwaza',
                'contact_role': 'CEO',
                'contact_email': 'abigail@abbysinvestment.com',
                'contact_phone': '+265 994 883 759',
                'client_user_email': 'client.abby@pritech.mw',
                'client_user_first': 'Abigail',
                'client_user_last': 'Chimwaza',
                'password': 'client123',
                'client_role': 'admin',
                'website_projects': [
                    {
                        'title': 'Abby Investment – Cleaning Services',
                        'description': 'Corporate website for Abby Investment, showcasing professional cleaning services, client testimonials, and service packages.',
                        'project_url': 'https://abbysinvestment.com',
                        'completion_date': date(2024, 11, 5),
                        'is_featured': False,
                        'order': 5,
                        'technologies': ['Django', 'PostgreSQL'],
                        'services': ['Website Development'],
                    }
                ]
            },
            {
                'name': 'Hillcrest Primary School',
                'industry': 'education',
                'email': 'info@hillcrest.mw',
                'phone': '+265 888 555 666',
                'address': 'Area 18, Lilongwe, Malawi',
                'website': 'https://hillcrest.mw',
                'contact_name': 'Dr. Peter Mwale',
                'contact_role': 'Principal',
                'contact_email': 'peter@hillcrest.mw',
                'contact_phone': '+265 999 555 666',
                'client_user_email': 'client.hillcrest@pritech.mw',
                'client_user_first': 'Peter',
                'client_user_last': 'Mwale',
                'password': 'client123',
                'client_role': 'admin',
                'website_projects': [
                    {
                        'title': 'Hillcrest Primary School',
                        'description': 'School website with student portal, fees management, event calendar, and parent communication features.',
                        'project_url': 'https://hillcrest.mw',
                        'completion_date': date(2025, 1, 20),
                        'is_featured': False,
                        'order': 6,
                        'technologies': ['Django', 'React', 'PostgreSQL'],
                        'services': ['Website Development', 'Software Installation'],
                    }
                ]
            },
        ]

        # Process clients and create organisations, users, contacts, and projects
        clients = []
        web_cat, _ = PortfolioCategory.objects.get_or_create(
            name='Web Development',
            defaults={'icon': 'fa-solid fa-globe', 'is_active': True}
        )

        for cd in clients_data:
            # Create organisation
            org, created = ClientOrganization.objects.get_or_create(
                email=cd['email'],
                defaults={
                    'name': cd['name'],
                    'industry': cd['industry'],
                    'phone': cd['phone'],
                    'address': cd['address'],
                    'website': cd['website'],
                    'status': 'active',
                }
            )
            clients.append(org)

            # Create client user
            client_user = User.objects.filter(email=cd['client_user_email']).first()
            if not client_user:
                client_user = User.objects.create_user(
                    username=cd['client_user_email'],
                    email=cd['client_user_email'],
                    password=cd['password'],
                    first_name=cd['client_user_first'],
                    last_name=cd['client_user_last'],
                    user_type='client',
                    client_role=cd['client_role'],
                    is_active=True,
                )
                UserRole.objects.get_or_create(user=client_user, role=roles['CLIENT'])
                client_user.client_organization = org
                client_user.save(update_fields=['client_organization'])

            # Create primary contact
            ClientContact.objects.get_or_create(
                client=org,
                email=cd['contact_email'],
                defaults={
                    'name': cd['contact_name'],
                    'role': cd['contact_role'],
                    'phone': cd['contact_phone'],
                    'is_primary': True,
                }
            )

            # Create portfolio projects
            for project_data in cd.get('website_projects', []):
                tech_objs = []
                for tech_name in project_data['technologies']:
                    tech, _ = PortfolioTechnology.objects.get_or_create(
                        name=tech_name,
                        defaults={'is_active': True}
                    )
                    tech_objs.append(tech)

                proj, created = PortfolioProject.objects.get_or_create(
                    title=project_data['title'],
                    defaults={
                        'client_name': cd['name'],
                        'category': web_cat,
                        'description': to_quill_json(project_data['description']),
                        'full_description': to_quill_json(project_data['description'] + ' (detailed)'),
                        'completion_date': project_data['completion_date'],
                        'is_featured': project_data['is_featured'],
                        'order': project_data['order'],
                        'status': 'published',
                        'project_url': project_data.get('project_url', ''),
                    }
                )
                if created:
                    # Link services
                    svc_objs = [svcs[name] for name in project_data['services'] if name in svcs]
                    proj.services.set(svc_objs)
                    proj.technologies.set(tech_objs)
                    if HAS_PIL and not proj.featured_image:
                        img_file = create_placeholder_image(text=proj.title[:20], bg_color=(14, 165, 233))
                        if img_file:
                            proj.featured_image.save(f"{proj.title.replace(' ', '_')}.jpg", img_file, save=True)
                    proj.save()

        self.stdout.write('  ✓ Realistic clients created with website projects (including 2 for MAME)')

        # ── Portfolio Settings (with Facebook link) ──────────────────────
        ps, _ = PortfolioSettings.objects.get_or_create(pk=1)
        ps.hero_title = "Smart ICT Solutions for Modern Businesses"
        ps.hero_subtitle = "From managed IT support to custom software, we deliver technology that drives growth and keeps your business running 24/7."
        ps.about_title = "Your Trusted Technology Partner"
        ps.about_text = "We are a team of passionate engineers, developers, and support specialists dedicated to solving business problems with technology."
        ps.projects_count = PortfolioProject.objects.filter(status='published').count()
        ps.satisfaction_percent = 98
        ps.support_hours = 24
        ps.years_experience = 12
        ps.facebook_url = "https://www.facebook.com/share/18moi3PTLW/"
        ps.twitter_url = ""
        ps.linkedin_url = ""
        ps.instagram_url = ""
        ps.whatsapp_number = "265999777822"
        ps.meta_description = "Pritech ICT Solutions delivers managed IT, custom software, and digital transformation for modern businesses in Malawi."
        ps.meta_keywords = "ICT solutions Malawi, managed IT support, software development, digital transformation, Pritech"
        ps.footer_copyright = "All Rights Reserved."
        ps.save()
        self.stdout.write('  ✓ Portfolio settings configured with Facebook link')

        # ── Subscription Plans ───────────────────────────────────────────
        plans_data = [
            {'name': 'Basic', 'monthly_price': 49.99, 'features': {'tickets': 5, 'storage_gb': 1}, 'is_active': True},
            {'name': 'Pro', 'monthly_price': 99.99, 'features': {'tickets': 20, 'storage_gb': 5}, 'is_active': True},
            {'name': 'Enterprise', 'monthly_price': 299.99, 'features': {'tickets': 'unlimited', 'storage_gb': 20}, 'is_active': True},
        ]
        plan_objects = {}
        for pdata in plans_data:
            plan, _ = Plan.objects.get_or_create(
                name=pdata['name'],
                defaults={
                    'monthly_price': pdata['monthly_price'],
                    'features': pdata['features'],
                    'is_active': pdata['is_active']
                }
            )
            plan_objects[plan.name] = plan
        self.stdout.write('  ✓ Subscription plans created')

        # ── Assign subscriptions to clients ─────────────────────────────
        today = date.today()
        for client in clients:
            if ClientSubscription.objects.filter(client=client).exists():
                continue
            if client.name == 'J&N Private Ltd':
                plan = plan_objects['Enterprise']
            elif client.name in ['Villa Grande Motel', 'Hillcrest Primary School']:
                plan = plan_objects['Pro']
            else:
                plan = plan_objects['Basic']
            start_date = today - timedelta(days=random.randint(30, 90))
            ClientSubscription.objects.create(
                client=client,
                plan=plan,
                status='active',
                start_date=start_date,
                current_period_start=start_date,
                current_period_end=start_date + timedelta(days=30),
                cancel_at_period_end=False
            )
        self.stdout.write('  ✓ Subscriptions assigned to clients')

        # ── Additional generic clients (for variety) ────────────────────
        extra_clients = [
            ('Malawi Revenue Authority', 'government', 'info@mra.mw', '+265 1 822 588'),
            ('Standard Bank Malawi', 'finance', 'it@standardbank.mw', '+265 1 820 144'),
        ]
        for name, industry, email, phone in extra_clients:
            c, _ = ClientOrganization.objects.get_or_create(name=name, defaults={
                'industry': industry, 'email': email, 'phone': phone,
                'address': 'Lilongwe, Malawi', 'status': 'active'
            })
            clients.append(c)
            ClientContact.objects.get_or_create(
                client=c, name='IT Manager', defaults={
                    'role': 'IT Manager', 'email': email, 'is_primary': True
                }
            )
        self.stdout.write('  ✓ Additional clients added')

        # ── Tickets for the real clients ────────────────────────────────
        from tickets.services import TicketService

        ticket_data = [
            ('Website not loading – J&N', clients[0], 'Website Development', 'high', 'open'),
            ('Reservation system down – Villa Grande', clients[2], 'Website Development', 'critical', 'assigned'),
            ('Payment gateway issue – MAME', clients[1], 'Website Development', 'high', 'in_progress'),
            ('Student portal login problem – Hillcrest', clients[4], 'Website Development', 'medium', 'open'),
            ('Cleaning service page update – Abby', clients[3], 'Website Development', 'low', 'closed'),
        ]
        tickets = []
        for title, client, svc_name, priority, status in ticket_data:
            if Ticket.objects.filter(title=title, client=client).exists():
                t = Ticket.objects.get(title=title, client=client)
            else:
                desc_text = f'Client reported: {title}. Requires urgent attention.'
                desc_json = to_quill_json(desc_text)
                t = TicketService.create_ticket(
                    title=title,
                    description=desc_json,
                    client=client,
                    service=svcs.get(svc_name),
                    priority=priority,
                    created_by=isaac
                )
                if status != 'open':
                    t.status = status
                    if status == 'assigned':
                        t.assigned_to = prince
                    elif status in ['in_progress', 'resolved', 'closed']:
                        t.assigned_to = prince
                        if status == 'resolved':
                            t.resolved_at = timezone.now()
                        elif status == 'closed':
                            t.resolved_at = timezone.now()
                    t.save()
                comment_json = to_quill_json("Ticket logged and assigned to technical team.")
                t.comments.create(author=isaac, content=comment_json, is_internal=True)
            tickets.append(t)

        for t in tickets:
            if not hasattr(t, 'sla') and t.status not in ['closed', 'resolved']:
                TicketService.create_sla(t)
        self.stdout.write('  ✓ Tickets created for real clients')

        # ── QUO-0001 for Villa Grande (exact as PDF) ────────────────────
        from finance.models import Quotation, QuotationItem

        villa_client = ClientOrganization.objects.filter(name='Villa Grande Motel').first()
        if villa_client and not Quotation.objects.filter(quotation_number='QUO-0001').exists():
            items = [
                {'description': 'Switch', 'qty': 1, 'unit_price': 750000},
                {'description': 'Ethernet Cable Roll', 'qty': 1, 'unit_price': 650000},
                {'description': 'Cable Clips', 'qty': 1, 'unit_price': 0},
                {'description': 'Routers', 'qty': 16, 'unit_price': 150000},
                {'description': 'Conduit Bend', 'qty': 1, 'unit_price': 0},
                {'description': 'Switch Cabinet', 'qty': 1, 'unit_price': 0},
                {'description': 'Starlink', 'qty': 1, 'unit_price': 0},
                {'description': 'Nails 2inch', 'qty': 1, 'unit_price': 0},
                {'description': 'Conduits Saddles', 'qty': 1, 'unit_price': 0},
                {'description': 'Conduits 25mm & 30mm', 'qty': 1, 'unit_price': 0},
                {'description': 'DVR 8 Channels', 'qty': 1, 'unit_price': 550000},
            ]
            subtotal = sum(i['qty'] * i['unit_price'] for i in items)  # 4,350,000
            tax_rate = float(cfg.vat_rate)
            tax_amount = subtotal * tax_rate   # 761,250
            total = subtotal + tax_amount      # 5,111,250

            quote = Quotation.objects.create(
                client=villa_client,
                quotation_number='QUO-0001',
                issue_date=date(2026, 6, 8),
                valid_until=date(2026, 6, 19),
                status='sent',
                created_by=portia,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total,
                notes=to_quill_json("Thank you for your business! Payment due within 30 days. This quotation is valid until June 19, 2026.")
            )
            for it in items:
                if it['unit_price'] > 0:
                    QuotationItem.objects.create(
                        quotation=quote,
                        description=it['description'],
                        quantity=it['qty'],
                        unit_price=it['unit_price'],
                        total=it['qty'] * it['unit_price']
                    )
            self.stdout.write(f'  ✓ Created QUO-0001 for Villa Grande (MWK {total:,.2f})')

        # ── Other quotations and invoices ──────────────────────────────
        from finance.models import Invoice, InvoiceItem, Payment
        from finance.services import QuotationService

        # Additional quotations for J&N and Hillcrest
        quote_data = [
            (clients[0], [('Website Development', 1, 250000), ('Hosting Setup', 1, 50000)], 'sent'),
            (clients[4], [('School Website', 1, 120000), ('Student Portal', 1, 80000)], 'sent'),
        ]
        for client, items, target_status in quote_data:
            if Quotation.objects.filter(client=client, status=target_status).exists():
                continue
            notes_json = to_quill_json("Please review and approve at your earliest convenience.")
            quote = Quotation.objects.create(
                client=client,
                issue_date=today - timedelta(days=random.randint(5, 30)),
                valid_until=today + timedelta(days=30),
                status='draft',
                created_by=portia,
                notes=notes_json
            )
            subtotal = 0
            for desc, qty, price in items:
                total = qty * price
                QuotationItem.objects.create(
                    quotation=quote, description=desc,
                    quantity=qty, unit_price=price, total=total
                )
                subtotal += total
            quote.subtotal = subtotal
            quote.tax_amount = subtotal * float(cfg.vat_rate)
            quote.total_amount = subtotal + quote.tax_amount
            quote.status = target_status
            quote.save()
            if target_status == 'approved':
                QuotationService.convert_to_invoice(quote, created_by=portia)
        self.stdout.write('  ✓ Additional quotations created')

        # ── Expenses ────────────────────────────────────────────────────
        from finance.models import Expense

        for cat, desc, amount in [
            ('salaries', 'Staff salaries – June', 850000),
            ('equipment', 'Network switches purchase', 320000),
            ('transport', 'Field visits – June', 45000),
            ('utilities', 'Office rent & utilities', 180000),
            ('marketing', 'Social media advertising', 35000),
        ]:
            Expense.objects.get_or_create(
                description=desc,
                defaults={'category': cat, 'amount': amount,
                          'date': today - timedelta(days=random.randint(1, 30)),
                          'recorded_by': portia}
            )
        self.stdout.write('  ✓ Expenses created')

        # ── Analytics data ──────────────────────────────────────────────
        self.stdout.write('  Adding test session & login event data...')
        now = timezone.now()
        UserSession.objects.filter(
            user__in=[isaac, prince, portia],
            session_key__startswith='test_session_'
        ).delete()
        LoginEvent.objects.filter(
            user__in=[isaac, prince, portia]
        ).delete()

        for user in [isaac, prince, portia]:
            for i in range(random.randint(3, 8)):
                login_time = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
                session_key = f"test_session_{user.id}_{i}_{random.randint(1000,9999)}"
                UserSession.objects.create(
                    user=user,
                    session_key=session_key,
                    ip_address=f"192.168.1.{random.randint(10,200)}",
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    device=random.choice(['Desktop', 'Mobile', 'Tablet']),
                    login_time=login_time,
                    last_activity=login_time + timedelta(minutes=random.randint(5, 120)),
                    is_active=random.choice([True, False]),
                    logout_time=login_time + timedelta(hours=random.randint(1, 8)) if random.choice([True, False]) else None
                )
        for user in [isaac, prince, portia]:
            for i in range(random.randint(5, 15)):
                timestamp = now - timedelta(days=random.randint(1, 30), hours=random.randint(0, 23))
                LoginEvent.objects.create(
                    user=user,
                    event_type=random.choice(['success', 'success', 'failed']),
                    ip_address=f"192.168.1.{random.randint(10,200)}",
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    timestamp=timestamp,
                    reason='' if random.random() > 0.3 else 'Invalid password'
                )
        self.stdout.write('  ✓ Session and login events added')

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Isaac Ndoka (Admin):   isaacndoka7@gmail.com / admin123')
        self.stdout.write('  Prince Chipeta (Admin): info@pritechmw.com / admin123')
        self.stdout.write('  Portia Domasi (Finance): sales@pritechmw.com / fin123')
        self.stdout.write('\nClient accounts:')
        for cd in clients_data:
            self.stdout.write(f'  {cd["name"]}: {cd["client_user_email"]} / {cd["password"]}')

    def _create_user(self, email, first, last, password, user_type, is_superuser, client_role=None, phone=None):
        if User.objects.filter(email=email).exists():
            return User.objects.get(email=email)
        u = User(
            email=email, username=email,
            first_name=first, last_name=last,
            user_type=user_type, is_active=True,
            is_staff=is_superuser, is_superuser=is_superuser,
        )
        if client_role is not None:
            u.client_role = client_role
        if phone:
            u.phone_number = phone
        u.set_password(password)
        u.save()
        return u