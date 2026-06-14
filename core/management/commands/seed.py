# core/management/commands/seed.py
"""
Comprehensive seeding script for Pritech ERP.
Seeds all apps: accounts, clients, services, tickets, finance, portfolio, and core.
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
    help = 'Seed the database with comprehensive demo data (including portfolio and core)'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # ── Site config (Core) ─────────────────────────────────────────────
        cfg = SiteConfig.get()
        cfg.company_name = 'Pritech ICT Solutions'
        cfg.tagline = 'Delivering reliable ICT solutions for businesses across Malawi'
        cfg.email = 'info@pritech.mw'
        cfg.phone = '+265 999 123 456'
        cfg.address = 'Area 3, Lilongwe\nMalawi'
        cfg.bank_name = 'National Bank of Malawi'
        cfg.bank_account = '1234567890'
        cfg.mobile_money = '+265 888 123 456'
        cfg.invoice_footer = 'Thank you for your business! Payment due within 30 days.'
        cfg.maintenance_mode = False
        cfg.save()
        self.stdout.write('  ✓ Site config')

        # ── Company Branch (Core) ─────────────────────────────────────────
        main_branch, _ = CompanyBranch.objects.get_or_create(
            name='Head Office - Lilongwe',
            defaults={
                'address': 'Area 3, Lilongwe, Malawi',
                'phone': '+265 999 123 456',
                'email': 'info@pritech.mw',
                'is_main': True
            }
        )
        self.stdout.write('  ✓ Company branches created')

        # ── Dashboard Widgets (Core) ──────────────────────────────────────
        # Create roles first (idempotent)
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

        # ── Announcements (Core) ─────────────────────────────────────────
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
            title='Scheduled Maintenance',
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

        # ── Staff users ──────────────────────────────────────────────────
        admin_user = self._create_user('admin@pritech.mw', 'Admin', 'User', 'admin123', 'staff', True)
        tech_user = self._create_user('tech@pritech.mw', 'John', 'Phiri', 'tech123', 'staff', False)
        fin_user = self._create_user('finance@pritech.mw', 'Mary', 'Banda', 'fin123', 'staff', False)

        for user, role_code in [(admin_user, 'ADMIN'), (tech_user, 'TECHNICIAN'), (fin_user, 'FINANCE')]:
            UserRole.objects.get_or_create(user=user, role=roles[role_code])

        # ── Client user + linked organization (using FK on User) ──────────
        client_user = self._create_user('client@acme.mw', 'James', 'Kalinda', 'client123', 'client', False, client_role='admin')
        UserRole.objects.get_or_create(user=client_user, role=roles['CLIENT'])

        client_org, created = ClientOrganization.objects.get_or_create(
            email='client@acme.mw',
            defaults={
                'name': 'Acme Corporation',
                'industry': 'other',
                'phone': '+265 999 888 777',
                'address': 'Area 4, Lilongwe',
                'status': 'active',
            }
        )
        # Link the organisation to the client user
        client_user.client_organization = client_org
        client_user.save(update_fields=['client_organization'])

        ClientContact.objects.get_or_create(
            client=client_org,
            email='client@acme.mw',
            defaults={
                'name': 'James Kalinda',
                'role': 'IT Manager',
                'is_primary': True,
                'phone': '+265 999 888 777',
            }
        )
        self.stdout.write('  ✓ Users created (including client org)')

        # ── User profiles for staff and client ────────────────────────────
        for u in [admin_user, tech_user, fin_user, client_user]:
            UserProfile.objects.get_or_create(user=u, defaults={
                'bio': f'Profile for {u.get_full_name()}',
                'gender': random.choice(['M', 'F', 'O']) if u != admin_user else 'M'
            })
        self.stdout.write('  ✓ User profiles created')

        # ── System Notifications (in‑app) for demo users ──────────────────
        for user in [admin_user, tech_user, fin_user, client_user]:
            SystemNotification.objects.get_or_create(
                user=user,
                title='Welcome to Pritech',
                defaults={
                    'message': 'Thank you for joining our platform. Explore the dashboard and real‑time features.',
                    'notification_type': 'success',
                    'is_read': False,
                }
            )
        SystemNotification.objects.get_or_create(
            user=admin_user,
            title='New client registered',
            defaults={
                'message': 'Acme Corporation has completed registration.',
                'notification_type': 'info',
                'is_read': False,
            }
        )
        self.stdout.write('  ✓ System notifications created')

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

        # ── Service categories + services ────────────────────────────────
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

        # ── Service Packages ─────────────────────────────────────────────
        packages_data = [
            ('Business Starter', [svcs['Network Installation'], svcs['IT Support – On-site']], 95000),
            ('Professional Suite', [svcs['Website Development'], svcs['CCTV Installation'], svcs['Firewall Setup']], 250000),
            ('Training Bundle', [svcs['Staff ICT Training'], svcs['Software Installation']], 60000),
        ]
        for name, svc_list, price in packages_data:
            pkg, created = ServicePackage.objects.get_or_create(
                name=name,
                defaults={'monthly_price': price, 'is_active': True}
            )
            if created:
                pkg.services.set(svc_list)
                pkg.save()
        self.stdout.write('  ✓ Service packages created')

        # ── Portfolio categories ─────────────────────────────────────────
        port_cats = {}
        for name, icon in [
            ('Web Development', 'fa-solid fa-globe'),
            ('Networking', 'fa-solid fa-network-wired'),
            ('Software Development', 'fa-solid fa-code'),
            ('Security Systems', 'fa-solid fa-shield-halved'),
            ('ICT Support', 'fa-solid fa-headset'),
        ]:
            cat, _ = PortfolioCategory.objects.get_or_create(
                name=name,
                defaults={'icon': icon, 'is_active': True}
            )
            port_cats[name] = cat
        self.stdout.write('  ✓ Portfolio categories created')

        # ── Portfolio technologies ───────────────────────────────────────
        tech_list = [
            ('Django', 'fa-brands fa-python'),
            ('React', 'fa-brands fa-react'),
            ('Python', 'fa-brands fa-python'),
            ('PostgreSQL', 'fa-solid fa-database'),
            ('Cisco', 'fa-solid fa-router'),
            ('Mikrotik', 'fa-solid fa-wifi'),
            ('Flutter', 'fa-solid fa-mobile-alt'),
        ]
        tech_objects = {}
        for name, icon in tech_list:
            t, _ = PortfolioTechnology.objects.get_or_create(name=name, defaults={'icon': icon, 'is_active': True})
            tech_objects[name] = t
        self.stdout.write('  ✓ Portfolio technologies created')

        # ── Portfolio projects (linked to services & technologies) ────────
        projects_data = [
            {
                'title': 'MUBAS Trade Hub Website',
                'client': 'Malawi University of Business and Applied Sciences',
                'category': 'Web Development',
                'services': ['Website Development', 'Software Installation'],
                'technologies': ['Django', 'React', 'PostgreSQL'],
                'description': 'Full‑featured e‑commerce platform for university trade hub.',
                'completion_date': date(2024, 5, 15),
                'is_featured': True,
                'order': 1,
            },
            {
                'title': 'National Bank Network Upgrade',
                'client': 'National Bank of Malawi',
                'category': 'Networking',
                'services': ['Network Installation', 'Firewall Setup'],
                'technologies': ['Cisco', 'Mikrotik'],
                'description': 'Complete network overhaul for 50+ branches.',
                'completion_date': date(2024, 2, 10),
                'is_featured': True,
                'order': 2,
            },
            {
                'title': 'School Management ERP',
                'client': 'St. Andrews International School',
                'category': 'Software Development',
                'services': ['Website Development', 'Software Installation', 'IT Support – On-site'],
                'technologies': ['Django', 'PostgreSQL', 'Flutter'],
                'description': 'Comprehensive ERP for student records, fees, and exams.',
                'completion_date': date(2024, 8, 20),
                'is_featured': True,
                'order': 3,
            },
            {
                'title': 'CCTV City Surveillance',
                'client': 'Lilongwe City Council',
                'category': 'Security Systems',
                'services': ['CCTV Installation', 'Network Installation'],
                'technologies': ['Cisco', 'Mikrotik'],
                'description': 'City‑wide CCTV installation and monitoring system.',
                'completion_date': date(2023, 11, 5),
                'is_featured': False,
                'order': 4,
            },
        ]

        projects = []
        for proj_data in projects_data:
            cat = port_cats[proj_data['category']]
            proj, created = PortfolioProject.objects.get_or_create(
                title=proj_data['title'],
                defaults={
                    'client_name': proj_data['client'],
                    'category': cat,
                    'description': to_quill_json(proj_data['description']),
                    'full_description': to_quill_json(proj_data['description'] + ' (detailed version)'),
                    'completion_date': proj_data['completion_date'],
                    'is_featured': proj_data['is_featured'],
                    'order': proj_data['order'],
                    'status': 'published',
                }
            )
            if created:
                svc_objs = [svcs[name] for name in proj_data['services'] if name in svcs]
                proj.services.set(svc_objs)
                tech_objs = [tech_objects[name] for name in proj_data['technologies'] if name in tech_objects]
                proj.technologies.set(tech_objs)
                if HAS_PIL and not proj.featured_image:
                    img_file = create_placeholder_image(text=proj.title[:20], bg_color=(14, 165, 233))
                    if img_file:
                        proj.featured_image.save(f"{proj.title.replace(' ', '_')}.jpg", img_file, save=True)
                proj.save()
            projects.append(proj)
        self.stdout.write('  ✓ Portfolio projects created')

        # ── Portfolio gallery images ─────────────────────────────────────
        for proj in projects:
            if proj.images.count() == 0 and HAS_PIL:
                for i in range(2):
                    img_file = create_placeholder_image(width=800, height=600, text=f"{proj.title} - image {i+1}")
                    if img_file:
                        PortfolioImage.objects.get_or_create(
                            project=proj,
                            order=i,
                            defaults={'image': img_file, 'caption': f"Screenshot {i+1}"}
                        )
        self.stdout.write('  ✓ Portfolio gallery images added')

        # ── Testimonials ────────────────────────────────────────────────
        testimonial_data = [
            (projects[0], "Dr. John Banda", "IT Director", "Exceptional work on our e‑commerce platform. The team was professional and delivered ahead of schedule.", 5),
            (projects[1], "Mary Phiri", "Head of IT", "The network upgrade transformed our operations. Zero downtime and excellent support.", 5),
            (projects[2], "Peter Mwale", "Principal", "The ERP system streamlined our school administration. Highly recommended.", 4),
        ]
        for proj, client_name, position, text, rating in testimonial_data:
            Testimonial.objects.get_or_create(
                project=proj,
                client_name=client_name,
                defaults={
                    'client_position': position,
                    'testimonial': text,
                    'rating': rating,
                    'is_approved': True,
                }
            )
        self.stdout.write('  ✓ Testimonials created')

        # ── Portfolio Settings ──────────────────────────────────────────
        ps, _ = PortfolioSettings.objects.get_or_create(pk=1)
        ps.hero_title = "Smart ICT Solutions for Modern Businesses"
        ps.hero_subtitle = "From managed IT support to custom software, we deliver technology that drives growth and keeps your business running 24/7."
        ps.about_title = "Your Trusted Technology Partner"
        ps.about_text = "We are a team of passionate engineers, developers, and support specialists dedicated to solving business problems with technology."
        ps.projects_count = PortfolioProject.objects.filter(status='published').count()
        ps.satisfaction_percent = 98
        ps.support_hours = 24
        ps.years_experience = 12
        ps.facebook_url = "https://facebook.com/pritech"
        ps.twitter_url = "https://twitter.com/pritech"
        ps.linkedin_url = "https://linkedin.com/company/pritech"
        ps.instagram_url = "https://instagram.com/pritech"
        ps.whatsapp_number = "265888123456"
        ps.meta_description = "Pritech ICT Solutions delivers managed IT, custom software, and digital transformation for modern businesses in Malawi."
        ps.meta_keywords = "ICT solutions Malawi, managed IT support, software development, digital transformation, Pritech"
        ps.footer_copyright = "All Rights Reserved."
        ps.save()
        self.stdout.write('  ✓ Portfolio settings configured')

        # ── Additional demo clients ─────────────────────────────────────
        clients_data = [
            ('Malawi Revenue Authority', 'government', 'info@mra.mw', '+265 1 822 588'),
            ('Standard Bank Malawi', 'finance', 'it@standardbank.mw', '+265 1 820 144'),
            ('Blantyre City Council', 'government', 'info@bcc.mw', '+265 1 872 011'),
            ('University of Malawi', 'education', 'ict@unima.mw', '+265 1 524 222'),
            ('Shoprite Malawi', 'retail', 'it@shoprite.mw', '+265 1 871 500'),
        ]
        clients = [client_org]
        for name, industry, email, phone in clients_data:
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
        self.stdout.write('  ✓ Additional clients created')

        # ── Assign subscriptions to clients ─────────────────────────────
        today = date.today()
        for client in clients:
            if ClientSubscription.objects.filter(client=client).exists():
                continue
            if client.name == 'Acme Corporation':
                plan = plan_objects['Pro']
            elif client.name in ['Malawi Revenue Authority', 'Standard Bank Malawi']:
                plan = plan_objects['Enterprise']
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

        # ── Canned responses ────────────────────────────────────────────
        canned_list = [
            ('Greeting', 'Thank you for contacting support. We are looking into your issue.'),
            ('Closing', 'We believe your issue has been resolved. Please reply if you need further assistance.'),
            ('Need more info', 'Could you please provide more details or screenshots?'),
            ('SLA reminder', 'This ticket is approaching its SLA deadline. Please provide an update.'),
        ]
        for title, content in canned_list:
            CannedResponse.objects.get_or_create(
                title=title,
                defaults={'content': content, 'created_by': admin_user, 'is_active': True}
            )
        self.stdout.write('  ✓ Canned responses created')

        # ── Tickets ─────────────────────────────────────────────────────
        from tickets.services import TicketService

        ticket_data = [
            ('Internet connection dropping', clients[0], 'Network Installation', 'high', 'in_progress'),
            ('Server room cooling failure', clients[1], 'IT Support – On-site', 'critical', 'assigned'),
            ('New workstations setup', clients[2], 'Computer Repair', 'medium', 'open'),
            ('Email server migration', clients[3], 'Website Development', 'high', 'resolved'),
            ('CCTV not recording', clients[4], 'CCTV Installation', 'medium', 'open'),
            ('VPN access for remote staff', clients[0], 'Firewall Setup', 'medium', 'closed'),
            ('Staff training – MS Office', clients[3], 'Staff ICT Training', 'low', 'open'),
        ]

        tickets = []
        for title, client, svc_name, priority, status in ticket_data:
            if Ticket.objects.filter(title=title, client=client).exists():
                t = Ticket.objects.get(title=title, client=client)
            else:
                desc_text = f'Client reported: {title}. Requires immediate attention.'
                desc_json = to_quill_json(desc_text)
                t = TicketService.create_ticket(
                    title=title,
                    description=desc_json,
                    client=client,
                    service=svcs.get(svc_name),
                    priority=priority,
                    created_by=admin_user
                )
                if status != 'open':
                    t.status = status
                    if status == 'assigned':
                        t.assigned_to = tech_user
                    elif status in ['in_progress', 'resolved', 'closed']:
                        t.assigned_to = tech_user
                        if status == 'resolved':
                            t.resolved_at = timezone.now()
                        elif status == 'closed':
                            t.resolved_at = timezone.now()
                    t.save()
                comment_json = to_quill_json("Ticket logged and reviewed. Assigned to technical team.")
                t.comments.create(author=admin_user, content=comment_json, is_internal=True)
            tickets.append(t)

        for t in tickets:
            if not hasattr(t, 'sla') and t.status not in ['closed', 'resolved']:
                TicketService.create_sla(t)
        self.stdout.write('  ✓ Tickets created with SLAs')

        # ── Quotations ──────────────────────────────────────────────────
        from finance.models import Quotation, QuotationItem
        from finance.services import QuotationService

        quote_data = [
            (clients[0], [('Network Infrastructure Upgrade', 1, 250000), ('24/7 Monitoring Service', 12, 15000)], 'sent'),
            (clients[1], [('CCTV System with 8 Cameras', 1, 380000), ('Installation & Configuration', 1, 80000)], 'approved'),
            (clients[2], [('Laptop Purchase x10', 10, 450000), ('Extended Warranty', 10, 25000)], 'sent'),
            (clients[3], [('University Website Redesign', 1, 1200000)], 'draft'),
            (clients[4], [('POS System Implementation', 1, 520000)], 'converted'),
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
                created_by=fin_user,
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
            if target_status == 'converted':
                quote.status = 'approved'
                quote.save()
                QuotationService.convert_to_invoice(quote, created_by=fin_user)
            else:
                quote.status = target_status
                quote.save()
        self.stdout.write('  ✓ Quotations created')

        # ── Invoices ────────────────────────────────────────────────────
        from finance.models import Invoice, InvoiceItem, Payment

        invoice_data = [
            (clients[0], [('Network Installation & Configuration', 1, 85000), ('Monthly Support Contract', 3, 15000)], 'paid'),
            (clients[1], [('Server Room Maintenance', 1, 120000), ('UPS Battery Replacement', 2, 35000)], 'paid'),
            (clients[2], [('Workstation Setup x5', 5, 45000), ('Software Licensing', 5, 8000)], 'issued'),
            (clients[3], [('University Portal Development', 1, 450000)], 'partial'),
            (clients[4], [('CCTV System Installation', 1, 120000), ('Annual Maintenance Contract', 1, 48000)], 'overdue'),
            (clients[0], [('Firewall Configuration', 1, 95000)], 'draft'),
        ]

        for client, items, status in invoice_data:
            if Invoice.objects.filter(client=client, status=status).exists():
                continue
            notes_json = to_quill_json("Standard payment terms apply.")
            invoice = Invoice.objects.create(
                client=client,
                issue_date=today - timedelta(days=random.randint(5, 60)),
                due_date=today + timedelta(days=random.randint(-10, 30)),
                status='draft',
                created_by=fin_user,
                notes=notes_json
            )
            subtotal = 0
            for desc, qty, price in items:
                total = qty * price
                InvoiceItem.objects.create(
                    invoice=invoice, description=desc,
                    quantity=qty, unit_price=price, total=total
                )
                subtotal += total
            invoice.subtotal = subtotal
            invoice.tax_amount = subtotal * float(cfg.vat_rate)
            invoice.total_amount = subtotal + invoice.tax_amount
            invoice.status = status
            if status == 'paid':
                invoice.amount_paid = invoice.total_amount
            elif status == 'partial':
                invoice.amount_paid = invoice.total_amount * 0.5
            invoice.save()

            if status == 'paid':
                Payment.objects.create(
                    invoice=invoice, amount=invoice.total_amount,
                    method='bank_transfer', date=today - timedelta(days=5),
                    recorded_by=fin_user
                )
            elif status == 'partial':
                Payment.objects.create(
                    invoice=invoice, amount=invoice.amount_paid,
                    method='mobile_money', date=today - timedelta(days=10),
                    recorded_by=fin_user
                )
        self.stdout.write('  ✓ Invoices & payments created')

        # ── Expenses ────────────────────────────────────────────────────
        from finance.models import Expense

        for cat, desc, amount in [
            ('salaries', 'Staff salaries – October', 850000),
            ('equipment', 'Network switches purchase', 320000),
            ('transport', 'Field visits – October', 45000),
            ('utilities', 'Office rent & utilities', 180000),
            ('marketing', 'Social media advertising', 35000),
        ]:
            Expense.objects.get_or_create(
                description=desc,
                defaults={'category': cat, 'amount': amount,
                          'date': today - timedelta(days=random.randint(1, 30)),
                          'recorded_by': fin_user}
            )
        self.stdout.write('  ✓ Expenses created')

        # ── Add simulated UserSession and LoginEvent data for analytics ───
        self.stdout.write('  Adding test session & login event data...')
        now = timezone.now()

        # Delete any existing test sessions and login events for these users (to avoid duplicates)
        UserSession.objects.filter(
            user__in=[admin_user, tech_user, fin_user, client_user],
            session_key__startswith='test_session_'
        ).delete()
        LoginEvent.objects.filter(
            user__in=[admin_user, tech_user, fin_user, client_user]
        ).delete()

        # Create new sessions
        for user in [admin_user, tech_user, fin_user, client_user]:
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

        # Create new login events
        for user in [admin_user, tech_user, fin_user, client_user]:
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

        # Recovery codes for client user
        if not RecoveryCode.objects.filter(user=client_user).exists():
            RecoveryCode.generate_for_user(client_user, num_codes=10)

        self.stdout.write('  ✓ Session, login events, and recovery codes added')

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Admin:   admin@pritech.mw / admin123')
        self.stdout.write('  Tech:    tech@pritech.mw  / tech123')
        self.stdout.write('  Finance: finance@pritech.mw / fin123')
        self.stdout.write('  Client:  client@acme.mw / client123 (client_role=admin, active)')

    def _create_user(self, email, first, last, password, user_type, is_superuser, client_role=None):
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
        u.set_password(password)
        u.save()
        return u