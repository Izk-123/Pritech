from django.db import models


class ClientOrganization(models.Model):
    INDUSTRY_CHOICES = [
        ('technology', 'Technology'), ('finance', 'Finance & Banking'),
        ('healthcare', 'Healthcare'), ('education', 'Education'),
        ('government', 'Government'), ('ngo', 'NGO / Non-Profit'),
        ('retail', 'Retail & Commerce'), ('other', 'Other'),
    ]
    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, default='other')
    registration_number = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def open_tickets(self):
        return self.tickets.exclude(status='closed').count()

    @property
    def total_invoiced(self):
        from django.db.models import Sum
        return self.invoices.aggregate(t=Sum('total_amount'))['t'] or 0


class ClientContact(models.Model):
    client = models.ForeignKey(ClientOrganization, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.client})"
