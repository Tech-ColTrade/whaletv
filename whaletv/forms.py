from django import forms

from .models import Factura, Televisor


class TelevisorForm(forms.ModelForm):
    class Meta:
        model = Televisor
        # lock_status NO se incluye: se calcula a partir de las facturas.
        fields = [
            'mac_address',
            'serial_number',
            'numero_cuotas',
            'correo_persona',
            'nombre_persona',
        ]
        widgets = {
            'mac_address': forms.TextInput(attrs={'placeholder': 'B4:04:29:7E:3A:ED'}),
            'serial_number': forms.TextInput(attrs={'placeholder': 'B4:04:29:7E:3A:ED'}),
            'numero_cuotas': forms.NumberInput(attrs={'min': 0, 'placeholder': '10'}),
            'correo_persona': forms.EmailInput(attrs={'placeholder': 'persona@correo.com'}),
            'nombre_persona': forms.TextInput(attrs={'placeholder': 'Nombre de la persona'}),
        }


class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = ['numero_factura', 'numero_cuota', 'fecha_vencimiento', 'pagada']
        widgets = {
            'numero_factura': forms.TextInput(attrs={'placeholder': 'F-2026-001'}),
            'numero_cuota': forms.NumberInput(attrs={'min': 1, 'placeholder': '1'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_vencimiento'].input_formats = ['%Y-%m-%d']
