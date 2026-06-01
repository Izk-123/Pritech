# accounts/views_2fa.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_otp.plugins.otp_totp.models import TOTPDevice
import qrcode
from io import BytesIO
import base64
from .forms import TOTPTokenForm


@login_required
def two_factor_setup(request):
    # Get or create an unconfirmed TOTP device
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if not device:
        device = TOTPDevice.objects.create(user=request.user, confirmed=False)

    if request.method == 'POST':
        form = TOTPTokenForm(request.POST)
        if form.is_valid():
            token = form.cleaned_data['token']
            if device.verify_token(token):
                device.confirmed = True
                device.save()
                request.user.is_2fa_enabled = True
                request.user.save(update_fields=['is_2fa_enabled'])
                messages.success(request, 'Two‑factor authentication has been enabled.')
                return redirect('profile')
            else:
                messages.error(request, 'Invalid verification code. Please try again.')
    else:
        form = TOTPTokenForm()

    # Generate QR code URI
    totp_uri = device.config_url  # e.g., otpauth://totp/...
    # Create QR code image
    qr = qrcode.make(totp_uri)
    buffer = BytesIO()
    qr.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    context = {
        'form': form,
        'qr_code': qr_base64,
        'secret_key': device.key,
    }
    return render(request, 'accounts/two_factor_setup.html', context)


@login_required
def two_factor_disable(request):
    if request.method == 'POST':
        # Delete all TOTP devices for this user
        TOTPDevice.objects.filter(user=request.user).delete()
        request.user.is_2fa_enabled = False
        request.user.save(update_fields=['is_2fa_enabled'])
        messages.success(request, 'Two‑factor authentication has been disabled.')
        return redirect('profile')
    return render(request, 'accounts/two_factor_disable.html')