from django.contrib.auth.backends import ModelBackend

from .models import Role, User


class EmailOrUsernameBackend(ModelBackend):
    """One login box: teachers type their email, students their username (ADR-0004)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        identifier = username.strip()
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier, role=Role.TEACHER).first()
        else:
            user = User.objects.filter(username__iexact=identifier).first()
        if user is None:
            User().set_password(password)  # same work as the found-user path (timing)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
