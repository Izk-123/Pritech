from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from .models import EmailVerificationToken

def send_verification_email(user, request):
    token, created = EmailVerificationToken.objects.get_or_create(user=user)
    verification_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': token.token})
    )
    subject = "Verify your email address"
    message = f"Hello {user.first_name},\n\nPlease click the link below to verify your email and activate your account:\n\n{verification_url}\n\nThis link expires in 24 hours."
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)