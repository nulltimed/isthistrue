"""Formulario DSA de reclamaciones sobre contenido (quiz 4A): acuse + registro."""
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ContentComplaint


def complaint_form(request):
    if request.method == 'POST':
        c = ContentComplaint.objects.create(
            email=request.POST.get('email', ''),
            content_url=request.POST.get('content_url', ''),
            reason=request.POST.get('reason', 'OTHER'),
            body=request.POST.get('body', ''))
        if c.email:
            send_mail('isthistrue: reclamación recibida',
                      f'Hemos recibido tu reclamación (ref. #{c.pk}). '
                      'La revisaremos y te responderemos a este correo.',
                      settings.DEFAULT_FROM_EMAIL, [c.email], fail_silently=True)
        messages.success(request, f'Reclamación registrada (ref. #{c.pk}). '
                                  'Recibirás acuse de recibo por email.')
        return redirect('complaint_form')
    return render(request, 'panel/complaint_form.html')
