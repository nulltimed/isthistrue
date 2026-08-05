"""Login que exige email verificado (salvo staff)."""
from django.contrib import messages
from django.contrib.auth.views import LoginView


class VerifiedLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        user = form.get_user()
        if not user.email_verified and not user.is_staff:
            messages.error(self.request, 'Debes verificar tu email antes de entrar. '
                                         '¿No te llegó? Reenvíalo abajo.')
            return self.form_invalid(form)
        return super().form_valid(form)
