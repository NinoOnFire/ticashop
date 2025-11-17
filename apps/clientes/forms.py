from django import forms
from .models import Proveedor, Cliente

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['rut', 'razon_social', 'email_contacto', 'telefono']
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contacto': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ClienteForm(forms.ModelForm):
    """
    Formulario para crear un Cliente desde el modal.
    No pedimos el campo 'user' porque lo crea un vendedor, no un cliente.
    """
    class Meta:
        model = Cliente
        fields = ['rut', 'razon_social', 'giro', 'direccion', 'email_facturacion']
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'email_facturacion': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CompletarPerfilForm(forms.ModelForm):
    """
    Formulario para que el CLIENTE complete su perfil por primera vez.
    """
    class Meta:
        model = Cliente
        # Excluimos 'user' porque se asignará en la vista
        fields = ['razon_social', 'rut', 'giro', 'direccion', 'email_facturacion']
        widgets = {
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tu nombre completo o razón social'}),
            'rut': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 12.345.678-9'}),
            'giro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Venta de productos...'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tu dirección completa'}),
            'email_facturacion': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@facturacion.cl'}),
        }
        labels = {
            'razon_social': 'Nombre Completo o Razón Social',
            'rut': 'RUT',
            'giro': 'Giro (Opcional)',
            'direccion': 'Dirección de Despacho/Facturación',
            'email_facturacion': 'Email para Facturación',
        }

    def __init__(self, *args, **kwargs):
        """Hacer campos obligatorios"""
        super().__init__(*args, **kwargs)
        self.fields['razon_social'].required = True
        self.fields['rut'].required = True
        self.fields['direccion'].required = True
        self.fields['email_facturacion'].required = True