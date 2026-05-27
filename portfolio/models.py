from django.db import models
from django_quill.fields import QuillField


class PortfolioProject(models.Model):
    title = models.CharField(max_length=200)
    description = QuillField()
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


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = 'Newsletter Subscriber'
        verbose_name_plural = 'Newsletter Subscribers'

    def __str__(self):
        return self.email


class PortfolioSettings(models.Model):
    """Singleton model for homepage content management."""
    # Hero section
    hero_title = models.CharField(max_length=200, blank=True,
        default="Smart ICT Solutions for Modern Businesses")
    hero_subtitle = models.TextField(blank=True,
        default="From managed IT support to custom software, we deliver technology that drives growth.")
    hero_image = models.ImageField(upload_to='hero/', null=True, blank=True)

    # About section
    about_title = models.CharField(max_length=200, blank=True,
        default="Your Trusted Technology Partner")
    about_text = models.TextField(blank=True,
        default="We are a team of passionate engineers, developers, and support specialists dedicated to solving business problems with technology. With over a decade of experience, we deliver reliable ICT infrastructure, software solutions, and round‑the‑clock support.")
    about_image = models.ImageField(upload_to='about/', null=True, blank=True)

    # Achievements counters
    projects_count = models.PositiveIntegerField(default=150)
    satisfaction_percent = models.PositiveIntegerField(default=98)
    support_hours = models.PositiveIntegerField(default=24)
    years_experience = models.PositiveIntegerField(default=12)

    # Social links
    facebook_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True, default="265888888888",
                                       help_text="International format without '+' or with '+', e.g., 265888888888 or +265888888888")

    # SEO
    meta_description = models.CharField(max_length=300, blank=True)
    meta_keywords = models.CharField(max_length=200, blank=True)

    # Footer
    footer_copyright = models.CharField(max_length=200, blank=True,
        default="All Right Reserved.")

    class Meta:
        verbose_name = "Portfolio Settings"
        verbose_name_plural = "Portfolio Settings"

    def __str__(self):
        return "Portfolio Settings"

    @classmethod
    def get(cls):
        """Get or create the singleton instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj