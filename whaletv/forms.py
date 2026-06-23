from django import forms

from .models import Inhabilitacion, Televisor


class TelevisorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # mac_address y serial_number son obligatorios al crear/editar.
        self.fields['mac_address'].required = True
        self.fields['serial_number'].required = True

    class Meta:
        model = Televisor
        # inhabilitado NO se incluye: se calcula a partir de las inhabilitaciones.
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


class InhabilitacionForm(forms.ModelForm):
    """Registrar manualmente un estado de inhabilitación para un televisor."""

    class Meta:
        model = Inhabilitacion
        fields = ['estado']
        widgets = {
            'estado': forms.Select(
                choices=((True, 'Inhabilitado'), (False, 'Habilitado')),
            ),
        }
