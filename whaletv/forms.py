from django import forms

from .models import Bloqueo, Televisor


class TelevisorForm(forms.ModelForm):
    class Meta:
        model = Televisor
        # lock_status NO se incluye: se calcula a partir de los bloqueos.
        fields = [
            'mac_address',
            'serial_number',
            'numero_credito',
        ]
        widgets = {
            'mac_address': forms.TextInput(attrs={'placeholder': 'B4:04:29:7E:3A:ED'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'B4:04:29:7E:3A:ED'}),
            'numero_credito': forms.TextInput(attrs={
                'placeholder': '1234567890',
                'inputmode': 'numeric',
                'pattern': r'\d*',
                'maxlength': 60,
            }),
        }


class BloqueoForm(forms.ModelForm):
    """Registrar manualmente un estado de bloqueo para un televisor."""

    class Meta:
        model = Bloqueo
        fields = ['estado']
        widgets = {
            'estado': forms.Select(
                choices=((True, 'Bloqueado'), (False, 'Desbloqueado')),
            ),
        }
