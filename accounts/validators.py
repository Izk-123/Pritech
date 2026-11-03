# accounts/validators.py
"""
Email deliverability validation for production-grade signup.

Two layers of protection against fake / disposable email addresses:

  1. Block known disposable / temporary-mail domains
     (mailinator, 10minutemail, tempmail, yopmail, ...)

  2. Verify the domain has MX records (i.e. it can actually receive mail).
     Falls back to an A record check per RFC 5321 if no MX exists.

Both checks are fail-OPEN on infrastructure problems (our DNS being down
should not prevent every single user from signing up). They are fail-CLOSED
on the actual "this address is fake" signals.
"""

from __future__ import annotations

import dns.resolver
import dns.exception
from functools import lru_cache
from django.core.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Disposable-domain blocklist (optional dependency)
#   pip install disposable-email-domains
# If the package is missing we degrade gracefully to "no blocklist".
# ---------------------------------------------------------------------------
try:
    from disposable_email_domains import blocklist as _raw_blocklist
    DISPOSABLE_DOMAINS: frozenset[str] = frozenset(_raw_blocklist)
except ImportError:  # pragma: no cover – depends on deploy env
    DISPOSABLE_DOMAINS = frozenset()


# ---------------------------------------------------------------------------
# MX lookup, cached per-process
# ---------------------------------------------------------------------------
@lru_cache(maxsize=10_000)
def _domain_can_receive_mail(domain: str) -> bool:
    """
    Return True if `domain` can plausibly receive email.

    Logic (per RFC 5321 §5.1):
        - MX record present        → True
        - Domain exists, no MX     → check for A record (implicit MX)
        - Domain does not exist    → False   (NXDOMAIN)
        - Our DNS is broken/timeout → True    (fail open – do not block users)
    """
    try:
        mx_answers = dns.resolver.resolve(domain, "MX", lifetime=3)
        return len(mx_answers) > 0

    except dns.resolver.NXDOMAIN:
        # Domain genuinely does not exist.
        return False

    except dns.resolver.NoAnswer:
        # Domain exists but publishes no MX – RFC 5321 fallback to A record.
        try:
            a_answers = dns.resolver.resolve(domain, "A", lifetime=3)
            return len(a_answers) > 0
        except Exception:
            return False

    except (dns.resolver.NoNameservers, dns.exception.Timeout):
        # OUR resolver had a problem – do not punish the end user.
        return True

    except Exception:
        # Anything unexpected (bad IDN, malformed domain, ...).
        # Fail open to avoid blocking legitimate signups.
        return True


# ---------------------------------------------------------------------------
# Public validator
# ---------------------------------------------------------------------------
def validate_email_deliverable(value: str) -> None:
    """
    Django validator: raises ValidationError if the email address
    looks fake / disposable / cannot receive mail.

    Use it directly in a form's ``clean_email``:

        def clean_email(self):
            email = self.cleaned_data["email"].strip().lower()
            validate_email_deliverable(email)
            return email

    Or attach it to a field via ``validators=[validate_email_deliverable]``.
    """
    value = (value or "").strip().lower()
    if "@" not in value:
        raise ValidationError("Enter a valid email address.")

    domain = value.rsplit("@", 1)[-1]

    # --- Layer 1: disposable provider ------------------------------------
    if domain in DISPOSABLE_DOMAINS:
        raise ValidationError(
            "Temporary / disposable email addresses are not allowed. "
            "Please use a permanent address (Gmail, Outlook, or your company email)."
        )

    # --- Layer 2: MX / A record ------------------------------------------
    if not _domain_can_receive_mail(domain):
        raise ValidationError(
            "This email domain cannot receive mail. "
            "Please double-check the address or use a different one."
        )