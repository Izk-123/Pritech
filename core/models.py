from django.db import models


class SiteConfig(models.Model):
    company_name = models.CharField(max_length=200, default='Pritech ICT Solutions')
    tagline = models.CharField(max_length=300, blank=True)
    logo = models.ImageField(upload_to='logo/', null=True, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.165)
    currency = models.CharField(max_length=10, default='MWK')
    currency_symbol = models.CharField(max_length=5, default='K')
    bank_name = models.CharField(max_length=100, blank=True)
    bank_account = models.CharField(max_length=50, blank=True)
    mobile_money = models.CharField(max_length=50, blank=True)
    invoice_footer = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Site Configuration'

    def __str__(self):
        return self.company_name

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
