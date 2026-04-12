from django.db import models


class PortfolioProject(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='portfolio/', null=True, blank=True)
    client_name = models.CharField(max_length=200, blank=True)
    technologies = models.CharField(max_length=300, blank=True)
    is_featured = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', '-pk']

    def __str__(self):
        return self.title


class Inquiry(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Inquiries'

    def __str__(self):
        return f"{self.name} – {self.subject}"
