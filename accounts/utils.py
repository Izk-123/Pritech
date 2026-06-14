# accounts/utils.py
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from .models import EmailVerificationToken


def send_verification_email(user, request):
    """Send email verification link to user."""
    token, _ = EmailVerificationToken.objects.get_or_create(user=user)
    verification_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': token.token})
    )
    subject = "Verify your email address"
    message = f"Hello {user.first_name},\n\nPlease click the link below to verify your email:\n\n{verification_url}\n\nThis link expires in 24 hours."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Return user agent string."""
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def parse_device(user_agent):
    """Simple device parser (Desktop/Mobile/Tablet)."""
    ua = user_agent.lower()
    if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
        return 'Mobile'
    elif 'tablet' in ua or 'ipad' in ua:
        return 'Tablet'
    else:
        return 'Desktop'