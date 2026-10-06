from django import forms
from django.core.validators import RegexValidator
from .models import Child, Delegate, SocialFile, WILAYAS, ROLES , Investigation
import re 
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from datetime import date
from django.core.exceptions import ValidationError
from .models import Investigation, InvestigationSummons, InvestigationVisit


class ChildForm(forms.ModelForm):

    uid = forms.CharField(
        label="المعرف الوحيد",
        required=False,
        disabled=True,          # 👈 للعرض فقط
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': True
        })
    )
   
    

    birth_date = forms.DateField(
        required=False,  # ✨ هنا نلغي required
        widget=forms.DateInput(
            attrs={
                'type': 'date',
                'max': date.today().strftime('%Y-%m-%d'),  # تمنع تواريخ مستقبلية
            }
        )
    )

    registration_date = forms.DateField(
        label="تاريخ الرسم",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )


    class Meta:
        model = Child
        exclude = ['delegate_ch']
        fields = [
            'first_name','last_name','gender','birth_date','birth_place',
            'birth_governorate','birth_department','foreign_country','birth_country',
            'registration_type','registration_number','registration_date',
            'nationality','birth_status','child_identity_type','identity_proof',
            'mother_age_at_birth','birth_place_detail','siblings_outside_marriage',
            'children_disposition','identity_documents_available',
            'foreign_family_status','siblings_outside', 'siblings_out', 
        ]

        widgets = {
            'uid': forms.TextInput(attrs={'readonly': True}),
            'birth_governorate': forms.Select(attrs={'class':'form-select'}),
            'birth_department': forms.Select(attrs={'class':'form-select'}),
            'birth_country': forms.Select(attrs={'class':'form-select'}),
            'foreign_country': forms.Select(attrs={'class':'form-select'}),
            
            'children_disposition': forms.Select(attrs={'class': 'form-select'}),
            'siblings_outside': forms.NumberInput(attrs={'class': 'form-control'}),
            'siblings_out': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')

        if birth_date:
            today = date.today()

            age = today.year - birth_date.year

            if (today.month, today.day) < (birth_date.month, birth_date.day):
                age -= 1
            
            if age > 18:
               raise forms.ValidationError(
               "لا يمكن تسجيل طفل تجاوز عمره 18 سنة."
               )

        return birth_date  

      
    def clean_registration_number(self):
        number = self.cleaned_data.get("registration_number")
        reg_type = self.cleaned_data.get("registration_type")

        # Seulement si l'enfant est "مرسم"
        if reg_type == "REGISTERED":
            if not number:
                raise forms.ValidationError("عدد الرسم إجباري.")

            if not number.isdigit():
                raise forms.ValidationError("عدد الرسم يجب أن يحتوي على أرقام فقط.")

            if len(number) != 7:
                raise forms.ValidationError("عدد الرسم يجب أن يتكون من 7 أرقام.")

        return number

  

from .models import Delegate

class DelegateForm(forms.ModelForm):
    class Meta:
        model = Delegate
        fields = [
            'wilaya', 'unique_id', 'first_name', 'last_name',
            'role', 'phone', 'email'
        ]


class LoginForm(forms.Form):
    unique_id = forms.CharField(
        label="المعرف الوحيد",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "أدخل المعرف الوحيد"
        })
    )
    password = forms.CharField(
        label="كلمة السر",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "أدخل كلمة السر"
        })
    )


  
    def clean_new_email(self):
        email = self.cleaned_data["new_email"]

        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مستعمل من قبل")

        return email

class ArabicPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="البريد الإلكتروني",
        max_length=254,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'form-control'})
    )


class RegisterForm(forms.Form):
    wilaya = forms.ChoiceField(choices=WILAYAS, required=True)
    delegate_code = forms.CharField(
        max_length=20, 
        required=True,
        validators=[RegexValidator(r'^\d{10}$', 'يجب إدخال 10 أرقام بالضبط')]
    )
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    role = forms.ChoiceField(choices=ROLES, required=True)
    phone = forms.CharField(required=False)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_delegate_code(self):
        delegate_code = self.cleaned_data["delegate_code"]
        if not delegate_code.isdigit() or len(delegate_code) != 10:
            raise forms.ValidationError("المعرف الوحيد يجب أن يحتوي على 10 أرقام بالضبط")
        
        # Vérifier si déjà utilisé
        if Delegate.objects.filter(delegate_code=delegate_code).exists():
            raise forms.ValidationError("هذا المعرف الوحيد مستخدم بالفعل")
        
        if User.objects.filter(username=delegate_code).exists():
            raise forms.ValidationError("هذا الحساب موجود بالفعل")
            
        return delegate_code

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if phone and (not phone.isdigit() or len(phone) != 8):
            raise forms.ValidationError("رقم الهاتف يجب أن يحتوي على 8 أرقام")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(username=email).exists():
            raise forms.ValidationError("هذا البريد الإلكتروني مستعمل من قبل")
        return email
    
class DelegateLoginForm(forms.Form):
    unique_id = forms.CharField(
        label="المعرف الوحيد",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل المعرف الوحيد',
            'inputmode': 'numeric',
            'maxlength': '10',
            'oninput': "this.value=this.value.replace(/\D/g,'').slice(0,10)"
        })
    )
    password = forms.CharField(
        label="كلمة السر",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'أدخل كلمة السر'
        })
    )

    def clean_unique_id(self):
        value = self.cleaned_data.get('unique_id')
        if not re.fullmatch(r'\d{10}', value):
            raise ValidationError("يجب أن يكون المعرف الوحيد مكوّنًا من 10 أرقام.")
        return value



class SocialFileForm(forms.ModelForm):
    class Meta:
        model = SocialFile
        exclude = ['enfant']  # سيتم ربط الطفل في view مباشرة
        widgets = {
            # نصوص كبيرة
            'adresse_enfant': forms.Textarea(attrs={'rows':3, 'class':'form-control'}),
            'nationalite_pere': forms.Textarea(attrs={'rows':2, 'class':'form-control'}),
            'nationalite_mere': forms.Textarea(attrs={'rows':2, 'class':'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إضافة class bootstrap لجميع الحقول
        for field_name, field in self.fields.items():
            if not hasattr(field.widget, 'attrs'):
                field.widget.attrs = {}
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'





from django import forms
from .models import Investigation, InvestigationSummons, InvestigationVisit, InvestigationSocialReport


class InvestigationForm(forms.ModelForm):
    """Formulaire pour les champs simples de Investigation"""
    class Meta:
        model = Investigation
        fields = [
            'court_request_date',
            'investigation_start',
            'psychological_request',
            'psychological_result',
            'medical_psych_request',
            'medical_psych_result',
            # ❌ SUPPRIMÉ: 'report_request',
            # ❌ SUPPRIMÉ: 'report_receive',
            'investigation_end',
        ]
        widgets = {
            'court_request_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'investigation_start': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'psychological_request': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'psychological_result': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'medical_psych_request': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'medical_psych_result': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            # ❌ SUPPRIMÉ: widgets pour report_request et report_receive
            'investigation_end': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
        }


class SummonsForm(forms.ModelForm):
    """Formulaire pour UN SEUL استدعاء (InvestigationSummons)"""
    class Meta:
        model = InvestigationSummons
        fields = ['summons_date', 'summons_method', 'attendance_date']
        widgets = {
            'summons_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'summons_method': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
            'attendance_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
        }


class VisitForm(forms.ModelForm):
    """Formulaire pour UNE SEULE زيارة (InvestigationVisit)"""
    class Meta:
        model = InvestigationVisit
        fields = ['visit_date', 'visit_place']
        widgets = {
            'visit_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'visit_place': forms.Select(attrs={
                'class': 'form-select form-select-sm'
            }),
        }


# ✅ NOUVEAU: Formulaire pour les rapports sociaux
class SocialReportForm(forms.ModelForm):
    """Formulaire pour UN SEUL تقرير اجتماعي (InvestigationSocialReport)"""
    class Meta:
        model = InvestigationSocialReport
        fields = ['report_request', 'report_receive']
        widgets = {
            'report_request': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
            'report_receive': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control form-control-sm'
            }),
           
        }

from django import forms
from .models import ThreatAssessment

class ThreatAssessmentForm(forms.ModelForm):
    THREAT_LEVELS = [
        ('low', 'منخفض الخطورة'),
        ('medium', 'متوسط الخطورة'),
        ('high', 'خطير جداً'),
    ]
    
    threat_level = forms.ChoiceField(
        choices=THREAT_LEVELS,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='مستوى الخطورة'
    )
    
    assessment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='تاريخ التقدير',
        required=False
    )
    
    assessor_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='القائم بالتقدير',
        required=False
    )
    
    assessing_body = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='الجهة المُقيّمة',
        required=False
    )
    
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4
        }),
        label='وصف الحالة',
        required=False
    )
    
    recommended_measures = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4
        }),
        label='التوصيات والإجراءات',
        required=False
    )
    
    class Meta:
        model = ThreatAssessment
        fields = [
            'threat_level',
            'assessment_date',
            'assessor_name',
            'assessing_body',
            'description',
            'recommended_measures'
        ]        



from .models import SocialDossierEnfant


class SocialDossierEnfantForm(forms.ModelForm):
    """
    Form for Social Dossier with sections for:
    - Child data (existing)
    - Mother data
    - Father data
    - Family data
    """
    
    class Meta:
        model = SocialDossierEnfant
        fields = [
            # Child data (existing)
            'current_address', 'governorate', 'delegation',
            'educational_status', 'health_status', 'social_allowance', 'academic_results',
            # Mother data
            'mother_first_name', 'mother_last_name',
            'mother_nationality_1', 'mother_nationality_2',
            'mother_residence_location', 'mother_governorate', 'mother_delegation', 'mother_country_abroad',
            'mother_education_level', 'mother_job_status',
            # Father data
            'father_first_name', 'father_last_name',
            'father_nationality_1', 'father_nationality_2',
            'father_residence_location', 'father_governorate', 'father_delegation', 'father_country_abroad',
            'father_education_level', 'father_job_status',
            # Family data
            'family_type', 'parents_relationship',
        ]
        
        widgets = {
            # Child data
            'current_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'عنوان الإقامة الحالية/ التواجد',
                'dir': 'rtl'
            }),
            'governorate': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'delegation': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'educational_status': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'health_status': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'social_allowance': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'academic_results': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            
            # Mother data
            'mother_first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'الاسم',
                'dir': 'rtl'
            }),
            'mother_last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اللقب',
                'dir': 'rtl'
            }),
            'mother_nationality_1': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'mother_nationality_2': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'mother_residence_location': forms.Select(attrs={
                'class': 'form-select mother-residence-trigger',
                'dir': 'rtl'
            }),
            'mother_governorate': forms.Select(attrs={
                'class': 'form-select mother-gov-select',
                'dir': 'rtl'
            }),
            'mother_delegation': forms.Select(attrs={
                'class': 'form-select mother-del-select',
                'dir': 'rtl'
            }),
            'mother_country_abroad': forms.Select(attrs={
                'class': 'form-select mother-country-select',
                'dir': 'rtl'
            }),
            'mother_education_level': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'mother_job_status': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            
            # Father data
            'father_first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'الاسم',
                'dir': 'rtl'
            }),
            'father_last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'اللقب',
                'dir': 'rtl'
            }),
            'father_nationality_1': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'father_nationality_2': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'father_residence_location': forms.Select(attrs={
                'class': 'form-select father-residence-trigger',
                'dir': 'rtl'
            }),
            'father_governorate': forms.Select(attrs={
                'class': 'form-select father-gov-select',
                'dir': 'rtl'
            }),
            'father_delegation': forms.Select(attrs={
                'class': 'form-select father-del-select',
                'dir': 'rtl'
            }),
            'father_country_abroad': forms.Select(attrs={
                'class': 'form-select father-country-select',
                'dir': 'rtl'
            }),
            'father_education_level': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'father_job_status': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            
            # Family data
            'family_type': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
            'parents_relationship': forms.Select(attrs={
                'class': 'form-select',
                'dir': 'rtl'
            }),
        }




from .models import SuiviEnfant


class SuiviEnfantForm(forms.ModelForm):

    class Meta:
        model = SuiviEnfant

        fields = [
            'avec_enfant',
            'avec_mere',
            'avec_pere',
            'avec_famille_etendue',
            'avec_tuteur_legal',
            'avec_membre_famille',
            'avec_cadre_medical',
            'avec_cadre_educatif',

            'appel_enfant',
            'appel_mere',
            'appel_pere',
            'appel_famille_etendue',
            'appel_tuteur_legal',
            'appel_membre_famille',
            'appel_cadre_medical',
            'appel_cadre_educatif',

            'nb_visites',

            'visite_institution_educative',
            'visite_institution_hospitaliere',
            'visite_institution_depot',
            'visite_centre_reforme',
            'visite_maison',
            'visite_autre',
            'autre_lieu_visite',

            'evaluation',
            'observations',
        ]

        widgets = {

            'nb_visites': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': '0'
                }
            ),

            'observations': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4
                }
            ),

            'evaluation': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
        }