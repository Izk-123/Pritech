# accounts/management/commands/resend_verification.py
# mkdir -p accounts/management/commands && touch accounts/management/__init__.py
# touch accounts/management/commands/__init__.py

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.contrib.auth import get_user_model

from accounts.utils import send_verification_email


class Command(BaseCommand):
    help = "Re-send verification emails to inactive users."

    def add_arguments(self, parser):
        parser.add_argument("--email", help="Only this specific address")
        parser.add_argument("--dry-run", action="store_true",
                            help="List but do not send")
        parser.add_argument("--base-url", default=None,
                            help="Required when running outside a request, "
                                 "e.g. https://pritech.mw")

    def handle(self, *args, **opts):
        qs = get_user_model().objects.filter(is_active=False, email__isnull=False)
        if opts["email"]:
            qs = qs.filter(email__iexact=opts["email"])

        sent = 0
        for user in qs:
            if opts["dry_run"]:
                self.stdout.write(f"[dry-run] would resend to {user.email}")
                continue
            try:
                url = send_verification_email(
                    user,
                    request=None,
                    resend=True,
                    base_url=opts.get("base_url"),
                )
                sent += 1
                self.stdout.write(self.style.SUCCESS(
                    f"sent  {user.email}  →  {url}"
                ))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(
                    f"FAIL  {user.email}  →  {exc}"
                ))

        if not opts["dry_run"]:
            self.stdout.write(f"Done — sent {sent} verification email(s).")