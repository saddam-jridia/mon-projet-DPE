from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User

class ArabicPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="البريد الإلكتروني",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "أدخل بريدك"})
    )

class LoginForm(forms.Form):
    email = forms.EmailField(
        label="البريد الإلكتروني",
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "أدخل بريدك"})
    )
    password = forms.CharField(
        label="كلمة السر",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "أدخل كلمة السر"})
    )

class RegisterForm(forms.Form):
    wilaya = forms.CharField(max_length=2)
    unique_number = forms.CharField(max_length=12)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    role = forms.CharField(max_length=100)
    phone = forms.CharField(required=False)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_unique_number(self):
        num = self.cleaned_data["unique_number"]
        if not num.isdigit() or len(num) != 12:
            raise forms.ValidationError("Le numéro doit contenir exactement 12 chiffres")
        return num

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone and (not phone.isdigit() or len(phone) != 8):
            raise forms.ValidationError("Le numéro de téléphone doit contenir exactement 8 chiffres")
        return phone

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Cet email est déjà utilisé")
        return email
