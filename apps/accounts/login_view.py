"""Login que exige email verificado (salvo staff) y, si el usuario activo la
verificacion en dos pasos (5.0-E), pide el codigo TOTP como segundo paso ANTES
de abrir la sesion."""
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect


class VerifiedLoginView(LoginView):
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        user = form.get_user()
        if not user.email_verified and not user.is_staff:
            messages.error(self.request, 'Debes verificar tu email antes de entrar. '
                                         '¿No te llegó? Reenvíalo abajo.')
            return self.form_invalid(form)
        from django_otp.plugins.otp_totp.models import TOTPDevice
        if TOTPDevice.objects.filter(user=user, confirmed=True).exists():
            # La contraseña es buena pero la sesion NO se abre todavia: el
            # segundo paso vive en otp_verify y la identidad viaja en sesion.
            self.request.session['otp_user_pk'] = user.pk
            self.request.session['otp_backend'] = user.backend
            self.request.session['otp_next'] = self.get_success_url()
            return redirect('otp_verify')
        return super().form_valid(form)
