"""Login con email O nickname, indistintamente (decision de David)."""
from django.contrib.auth.backends import ModelBackend
from .models import User


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username:
            return None
        user = User.objects.filter(email__iexact=username).first() or \
               User.objects.filter(username__iexact=username).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
