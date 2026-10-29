from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrRegistrationNumberBackend(ModelBackend):
    """Wireframe 1: sign in with email, registration number or employee email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        User = get_user_model()
        identifier = username.strip()
        user = (
            User.objects.filter(
                Q(email__iexact=identifier)
                | Q(registration_number__iexact=identifier)
                | Q(username__iexact=identifier)
            )
            .order_by("pk")
            .first()
        )
        if user is None:
            # Run the hasher anyway so a missing account takes as long as a wrong password.
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
