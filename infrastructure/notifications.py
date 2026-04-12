"""
Email notification service for PIMS.
Uses Django's built-in email framework.
Configure EMAIL_* settings in settings.py for production.
Development uses console backend — emails print to terminal.
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def _from_email():
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@pritech.mw')


def notify_ticket_created(ticket):
    """Notify assigned technician (if any) and log."""
    if not ticket.assigned_to or not ticket.assigned_to.email:
        return
    subject = f'[PIMS] New ticket assigned: #{ticket.pk} — {ticket.title}'
    body = (
        f'Hello {ticket.assigned_to.get_full_name()},\n\n'
        f'A new ticket has been assigned to you.\n\n'
        f'Ticket: #{ticket.pk} — {ticket.title}\n'
        f'Client: {ticket.client.name}\n'
        f'Priority: {ticket.get_priority_display()}\n\n'
        f'Please log in to view and update the ticket.\n\n'
        f'— {settings.SITE_NAME if hasattr(settings, "SITE_NAME") else "PIMS"}'
    )
    _safe_send(subject, body, [ticket.assigned_to.email])


def notify_ticket_status_changed(ticket, old_status, user):
    """Notify client when their ticket status changes."""
    # Try to find client user email
    recipients = []
    if ticket.client.email:
        recipients.append(ticket.client.email)
    if not recipients:
        return

    subject = f'[PIMS] Ticket #{ticket.pk} status update: {ticket.get_status_display()}'
    body = (
        f'Dear {ticket.client.name},\n\n'
        f'Your ticket has been updated.\n\n'
        f'Ticket: {ticket.title}\n'
        f'Status: {old_status.replace("_", " ").title()} → {ticket.get_status_display()}\n\n'
        f'If you have any questions, please contact us.\n\n'
        f'— Pritech Support Team'
    )
    _safe_send(subject, body, recipients)


def notify_invoice_issued(invoice):
    """Notify client when invoice is issued."""
    if not invoice.client.email:
        return
    from core.models import SiteConfig
    config = SiteConfig.get()

    subject = f'[{config.company_name}] Invoice {invoice.invoice_number} — {config.currency_symbol} {invoice.total_amount:,.2f}'
    body = (
        f'Dear {invoice.client.name},\n\n'
        f'Please find your invoice details below.\n\n'
        f'Invoice Number: {invoice.invoice_number}\n'
        f'Amount Due: {config.currency_symbol} {invoice.total_amount:,.2f}\n'
        f'Due Date: {invoice.due_date.strftime("%d %B %Y")}\n\n'
        f'Payment Methods:\n'
        f'  Bank Transfer: {config.bank_name or "—"} | A/C: {config.bank_account or "—"}\n'
        f'  Mobile Money: {config.mobile_money or "—"}\n\n'
        f'{config.invoice_footer or ""}\n\n'
        f'— {config.company_name}\n'
        f'  {config.phone or ""} | {config.email or ""}'
    )
    _safe_send(subject, body, [invoice.client.email])


def notify_payment_received(payment):
    """Notify client that payment was recorded."""
    invoice = payment.invoice
    if not invoice.client.email:
        return
    from core.models import SiteConfig
    config = SiteConfig.get()

    subject = f'[{config.company_name}] Payment received — {invoice.invoice_number}'
    body = (
        f'Dear {invoice.client.name},\n\n'
        f'We have received your payment. Thank you!\n\n'
        f'Invoice: {invoice.invoice_number}\n'
        f'Payment Amount: {config.currency_symbol} {payment.amount:,.2f}\n'
        f'Payment Method: {payment.get_method_display()}\n'
        f'Date: {payment.date.strftime("%d %B %Y")}\n'
        f'Balance Remaining: {config.currency_symbol} {invoice.balance_due:,.2f}\n\n'
        f'— {config.company_name}'
    )
    _safe_send(subject, body, [invoice.client.email])


def _safe_send(subject, body, recipients):
    """Send email, silently fail if misconfigured (dev mode)."""
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_email(),
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as e:
        import logging
        logging.getLogger('pritech.notifications').warning(
            f'Email send failed to {recipients}: {e}'
        )
