from django.db import models


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, default='🔧')
    description = models.TextField(blank=True)  # new

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Service categories'


class Service(models.Model):
    BILLING_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
    ]

    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='services'
    )
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit = models.CharField(
        max_length=50,
        default='job',
        help_text='e.g. job, hour, month'
    )
    billing_type = models.CharField(
        max_length=20,
        choices=BILLING_TYPE_CHOICES,
        default='one_time'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ServicePackage(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    services = models.ManyToManyField(Service, related_name='packages')
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name