from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailOrPhoneBackend(ModelBackend):
    """Allow login with email OR phone number + password."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            user = User.objects.get(
                Q(email__iexact=username) | Q(phone_number=username)
            )
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(
                Q(email__iexact=username) | Q(phone_number=username)
            ).order_by('id').first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
