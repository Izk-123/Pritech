from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with demo data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # ── Site config
        from core.models import SiteConfig
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
        cfg.save()
        self.stdout.write('  ✓ Site config')

        # ── Roles
        from accounts.models import Role, Permission, RolePermission
        roles = {}
        for code, name in [('ADMIN', 'Administrator'), ('TECHNICIAN', 'Technician'),
                            ('FINANCE', 'Finance Officer'), ('CLIENT', 'Client')]:
            r, _ = Role.objects.get_or_create(code=code, defaults={'name': name})
            roles[code] = r

        perms = {}
        for code, desc in [('view_reports', 'View financial reports'),
                            ('manage_users', 'Manage users'),
                            ('manage_invoices', 'Manage invoices'),
                            ('manage_tickets', 'Manage tickets')]:
            p, _ = Permission.objects.get_or_create(code=code, defaults={'description': desc})
            perms[code] = p

        for perm in perms.values():
            RolePermission.objects.get_or_create(role=roles['ADMIN'], permission=perm)
        RolePermission.objects.get_or_create(role=roles['FINANCE'], permission=perms['manage_invoices'])
        RolePermission.objects.get_or_create(role=roles['FINANCE'], permission=perms['view_reports'])
        RolePermission.objects.get_or_create(role=roles['TECHNICIAN'], permission=perms['manage_tickets'])
        self.stdout.write('  ✓ Roles & permissions')

        # ── Staff users
        from accounts.models import UserRole
        admin_user = self._create_user('admin@pritech.mw', 'Admin', 'User', 'admin123', 'staff', True)
        tech_user  = self._create_user('tech@pritech.mw', 'John', 'Phiri', 'tech123', 'staff', False)
        fin_user   = self._create_user('finance@pritech.mw', 'Mary', 'Banda', 'fin123', 'staff', False)

        for user, role_code in [(admin_user, 'ADMIN'), (tech_user, 'TECHNICIAN'), (fin_user, 'FINANCE')]:
            UserRole.objects.get_or_create(user=user, role=roles[role_code])

        client_user = self._create_user('client@acme.mw', 'James', 'Kalinda', 'client123', 'client', False)
        UserRole.objects.get_or_create(user=client_user, role=roles['CLIENT'])
        self.stdout.write('  ✓ Users created')

        # ── Service categories + services
        from services.models import ServiceCategory, Service
        cats = {}
        for name, icon in [('Networking', '🌐'), ('Hardware', '🖥'), ('Software', '💻'),
                            ('Security', '🔒'), ('Training', '🎓')]:
            c, _ = ServiceCategory.objects.get_or_create(name=name, defaults={'icon': icon})
            cats[name] = c

        services_data = [
            ('Network Installation', 'Networking', 85000, 'job'),
            ('Wireless Setup', 'Networking', 45000, 'job'),
            ('IT Support – On-site', 'Hardware', 15000, 'visit'),
            ('Computer Repair', 'Hardware', 20000, 'job'),
            ('Website Development', 'Software', 250000, 'project'),
            ('Software Installation', 'Software', 8000, 'job'),
            ('CCTV Installation', 'Security', 120000, 'job'),
            ('Firewall Setup', 'Security', 95000, 'job'),
            ('Staff ICT Training', 'Training', 50000, 'day'),
        ]
        svcs = {}
        for name, cat, price, unit in services_data:
            s, _ = Service.objects.get_or_create(name=name, defaults={
                'category': cats[cat], 'base_price': price, 'unit': unit
            })
            svcs[name] = s
        self.stdout.write('  ✓ Services created')

        # ── Clients
        from clients.models import ClientOrganization, ClientContact
        clients_data = [
            ('Malawi Revenue Authority', 'government', 'info@mra.mw', '+265 1 822 588'),
            ('Standard Bank Malawi', 'finance', 'it@standardbank.mw', '+265 1 820 144'),
            ('Blantyre City Council', 'government', 'info@bcc.mw', '+265 1 872 011'),
            ('University of Malawi', 'education', 'ict@unima.mw', '+265 1 524 222'),
            ('Shoprite Malawi', 'retail', 'it@shoprite.mw', '+265 1 871 500'),
        ]
        clients = []
        for name, industry, email, phone in clients_data:
            c, _ = ClientOrganization.objects.get_or_create(name=name, defaults={
                'industry': industry, 'email': email, 'phone': phone,
                'address': 'Lilongwe, Malawi'
            })
            clients.append(c)
            ClientContact.objects.get_or_create(
                client=c, name=f'IT Manager', defaults={
                    'role': 'IT Manager', 'email': email, 'is_primary': True
                }
            )
        self.stdout.write('  ✓ Clients created')

        # ── Tickets
        from tickets.models import Ticket, TicketComment
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
            t, created = Ticket.objects.get_or_create(
                title=title, client=client,
                defaults={
                    'description': f'Client reported: {title}. Requires immediate attention.',
                    'service': svcs.get(svc_name),
                    'priority': priority, 'status': status,
                    'created_by': admin_user,
                    'assigned_to': tech_user if status != 'open' else None,
                }
            )
            if created:
                TicketComment.objects.create(
                    ticket=t, author=admin_user,
                    content='Ticket logged and reviewed. Assigned to technical team.',
                    is_internal=True
                )
            tickets.append(t)
        self.stdout.write('  ✓ Tickets created')

        # ── Invoices
        from finance.models import Invoice, InvoiceItem, Payment
        from finance.services import InvoiceService
        today = date.today()
        invoice_data = [
            (clients[0], [('Network Installation & Configuration', 1, 85000), ('Monthly Support Contract', 3, 15000)], 'paid'),
            (clients[1], [('Server Room Maintenance', 1, 120000), ('UPS Battery Replacement', 2, 35000)], 'paid'),
            (clients[2], [('Workstation Setup x5', 5, 45000), ('Software Licensing', 5, 8000)], 'issued'),
            (clients[3], [('University Portal Development', 1, 450000)], 'partial'),
            (clients[4], [('CCTV System Installation', 1, 120000), ('Annual Maintenance Contract', 1, 48000)], 'overdue'),
            (clients[0], [('Firewall Configuration', 1, 95000)], 'draft'),
        ]

        for i, (client, items, status) in enumerate(invoice_data):
            if Invoice.objects.filter(client=client, status=status).exists():
                continue
            invoice = Invoice.objects.create(
                client=client,
                issue_date=today - timedelta(days=random.randint(5, 60)),
                due_date=today + timedelta(days=random.randint(-10, 30)),
                status='draft', created_by=fin_user
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

        # ── Expenses
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

        self.stdout.write(self.style.SUCCESS('\n✅ Seeding complete!'))
        self.stdout.write('\nLogin credentials:')
        self.stdout.write('  Admin:   admin@pritech.mw / admin123')
        self.stdout.write('  Tech:    tech@pritech.mw  / tech123')
        self.stdout.write('  Finance: finance@pritech.mw / fin123')
        self.stdout.write('  Client:  client@acme.mw / client123')

    def _create_user(self, email, first, last, password, user_type, is_superuser):
        if User.objects.filter(email=email).exists():
            return User.objects.get(email=email)
        u = User(
            email=email, username=email,
            first_name=first, last_name=last,
            user_type=user_type, is_active=True,
            is_staff=is_superuser, is_superuser=is_superuser,
        )
        u.set_password(password)
        u.save()
        return u
