
import json
import re
import traceback
from datetime import datetime, timedelta, date
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.db import transaction, models
from django.db.models import Q, Count, Max, Exists, OuterRef
from django.db.models.functions import TruncMonth, TruncYear
from django.template.loader import render_to_string, get_template
from django.utils import timezone
from django.views.decorators.http import require_POST

from projet_Dpe import settings
from .forms import ChildForm, DelegateForm, RegisterForm, LoginForm, DelegateLoginForm, InvestigationForm, ThreatAssessmentForm
from .models import (
    WILAYAS, ROLES, Child, Delegate, EnfantDelinquant,
    NouveauNotification, Investigation, InvestigationSummons,
    InvestigationVisit, SocialFile, Intervention, ThreatAssessment,
    MesureConvenue, MesureUrgente, SocialDossierEnfant,
    TraffickingNotification, Production, ProductionRequest,
    ResultatProductionRequest
)
from .models import InvestigationSocialReport
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side


# ==================== DECORATEURS ====================

def safe_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None

def admin_required(view_func):
    """
    Décorateur pour vérifier que l'utilisateur est un administrateur (chef de bureau ou central)
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login_delegate')

        allowed_roles = ['chef de bureau', 'central']
        # Vérifier si l'utilisateur a un rôle autorisé
        if hasattr(request.user, 'delegate_profile'):
            if request.user.delegate_profile.role in allowed_roles:
                return view_func(request, *args, **kwargs)

        # Si l'utilisateur est superuser Django
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        messages.error(request, "❌ Vous n'avez pas les droits pour accéder à cette page.")
        return redirect('index2')

    return wrapper

# ==================== CONSTANTES ====================  

THREATS_LABELS = {
    "loss": {
        "parents_dead": "وفاة الأبوين",
        "absence_parent": "غياب أحد الأبوين",
        "no_civil_registration": "عدم التسجيل بالحالة المدنية",
    },
    "neglect": {
        "hygiene_food": "سوء النظافة أو التغذية",
        "homeless": "التشرد",
    },
    "care": {
        "no_school": "عدم التمدرس",
        "violence": "العنف داخل الأسرة",
    },
    "guardian": {
        "begging": "التسول",
        "runaway": "الهروب من المنزل",
        "dangerous_behavior": "سلوك خطير",
    }
}


# ==================== VUES PRINCIPALES ====================

def header(request):
 
    return render(request , 'account/Header.html')


def index(request):
 
    return render(request , 'dashboard/admin_dashboard.html')
    


def index1(request):
    return render(request, 'index1.html')

# ==================== UID GENERATION ====================

from django.utils import timezone

def get_next_uid():
    
    year = timezone.now().year % 100
    year_str = f"{year:02d}"
    
    # Récupérer le dernier UID des enfants menacés
    last_menaced = Child.objects.filter(
        uid__endswith=year_str
    ).order_by('-uid').first()
    
    # Récupérer le dernier UID des enfants délinquants
    last_delinquent = EnfantDelinquant.objects.filter(
        uid__endswith=year_str
    ).order_by('-uid').first()
    
    # Initialiser le plus grand numéro
    max_number = 0
    
    # Vérifier le dernier enfant menacé
    if last_menaced and last_menaced.uid:
        try:
            # Extraire les 6 premiers chiffres de l'UID
            num = int(last_menaced.uid[:6])
            if num > max_number:
                max_number = num
        except (ValueError, IndexError):
            pass
    
    # Vérifier le dernier enfant délinquant
    if last_delinquent and last_delinquent.uid:
        try:
            # Extraire les 6 premiers chiffres de l'UID
            num = int(last_delinquent.uid[:6])
            if num > max_number:
                max_number = num
        except (ValueError, IndexError):
            pass
    
    # Générer le prochain numéro
    next_number = max_number + 1
    
    # Formater avec 6 chiffres + année
    return f"{next_number:06d}{year_str}"


# ==================== ENFANT MENACE (CRUD) ====================

def child_create(request):
    persons = ['الأم', 'الأب', 'العائلة الموسعة']
    zip_values = [
        ('accompany', 'اصطحاب'),
        ('temp_abandon', 'تخلي مؤقت'),
        ('final_abandon', 'تخلي نهائي'),
    ]

    if request.method == 'POST':
        form = ChildForm(request.POST)

        if form.is_valid():
            child_data = form.cleaned_data

            # 🔵 وضعية أولية
            initial = {}
            for p in persons:
                value = request.POST.get(f'initial_{p}')
                if value:
                    initial[p] = value
            child_data['initial_status_at_birth'] = initial

            # 🔵 Si utilisateur connecté, on sauvegarde directement dans la DB
            if request.user.is_authenticated:
                child = form.save(commit=False)
                child.initial_status_at_birth = initial

                if hasattr(request.user, "delegate_profile"):
                    delegate = request.user.delegate_profile
                    child.delegate_ch = delegate
                    child.delegate_unique_id = delegate.unique_id
                    # ✅ CORRECTION : utiliser delegate_code au lieu de unique_number
                    child.delegate_unique_number = delegate.delegate_code

                child.save()
                form = ChildForm(initial={'uid': get_next_uid()})
                

            else:
                # 🔵 Si utilisateur déconnecté, on stocke dans la session
                children = request.session.get('unsaved_children', [])
                children.append({
                    **child_data,
                    'initial_status_at_birth': initial
                })
                request.session['unsaved_children'] = children
                form = ChildForm(initial={'uid': get_next_uid()})
                

            return render(request, 'account/child_form.html', {
                'form': form,
                'child': child,
                'persons': persons,
                'zip_values': zip_values,
                'DEPARTMENTS': Child.DEPARTMENTS,
                'initial_status': initial,
                'show_success_modal': True,
            })

    else:
        form = ChildForm(initial={'uid': get_next_uid()})

    return render(request, 'account/child_form.html', {
        'form': form,
        'persons': persons,
        'zip_values': zip_values,
        'initial_status': {},
        'DEPARTMENTS': Child.DEPARTMENTS
    })


def set_child_status(request, child_id):
    child = Child.objects.get(id=child_id)

    if request.method == "POST":
        status = request.POST.get("status")

        if status in ["THREATENED", "DELINQUENT"]:
            child.status = status
            child.save()

            if status == "THREATENED":
                return redirect("child_list_institutions")
            else:
                return redirect("enfant_list")

    return redirect("child_create")
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

@receiver(user_logged_in)
def save_session_children(sender, user, request, **kwargs):
    if hasattr(user, 'delegate_profile'):
        delegate = user.delegate_profile
        unsaved = request.session.get('unsaved_children', [])

        for data in unsaved:
            initial = data.pop('initial_status_at_birth', {})
            child = Child.objects.create(
                delegate_ch=delegate,
                delegate_unique_id=delegate.unique_id,
                delegate_unique_number=delegate.unique_number,
                **data
            )
            child.initial_status_at_birth = initial
            child.save()

        # vider la session
        request.session['unsaved_children'] = []


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

@login_required
def child_update(request, pk):

    child = get_object_or_404(Child, pk=pk)

    persons = ['الأم', 'الأب', 'العائلة الموسعة']
    zip_values = [
        ('accompany', 'اصطحاب'),
        ('temp_abandon', 'تخلي مؤقت'),
        ('final_abandon', 'تخلي نهائي'),
    ]

    initial_status = child.initial_status_at_birth or {}

    if request.method == "POST":
        print("Avant formulaire :", child.status)
        form = ChildForm(request.POST, instance=child)
        

        if form.is_valid():
            child = form.save(commit=False)
            print("Après form.save :", child.status)

            # champs supplémentaires
            child.health_status = request.POST.get("health_status")
            child.disability_type = request.POST.get("disability_type")
            child.disability_degree = request.POST.get("disability_degree")

            # JSON initial_status_at_birth
            new_initial = {}
            for p in persons:
                value = request.POST.get(f"initial_{p}")
                if value:
                    new_initial[p] = value

            child.initial_status_at_birth = new_initial

            

            child.save()
            print("Child ID:", child.id)
            print("Status:", child.status)
            print("Delegate child:", child.delegate_ch)
            print("Current delegate:", request.user.delegate_profile)

            print("Tous les enfants:", Child.objects.count())

            print("Même delegate:", Child.objects.filter(delegate_ch=request.user.delegate_profile).count())

            print("Même status:", Child.objects.filter(status="THREATENED").count())

            print("Delegate + status:", Child.objects.filter( delegate_ch=request.user.delegate_profile,status="THREATENED").count())
            # -----------------------------
            # Recharger les données de la liste
            # -----------------------------
            governorates = Child.TUNISIA_GOVERNORATES
            selected_governorate = request.GET.get("governorate", "")
            selected_gender = request.GET.get("gender", "")

            delegates = Delegate.objects.exclude(
                user=request.user
            ).exclude(
                email__isnull=True
            ).exclude(
                email=""
            )

            if hasattr(request.user, "delegate_profile"):
                children = Child.objects.filter(
                    delegate_ch=request.user.delegate_profile,
                    status="THREATENED"
                ).order_by("created_at")
            else:
                children = Child.objects.none()

            if selected_governorate:
                children = children.filter(
                    birth_governorate=selected_governorate
                )

            if selected_gender:
                children = children.filter(
                    gender=selected_gender
                )

            return render(request, "account/child_list_institutions.html", {
                "children": children,
                "child": child,
                "form": form,
                "governorates": governorates,
                "selected_governorate": selected_governorate,
                "selected_gender": selected_gender,
                "DEPARTMENTS": Child.DEPARTMENTS,
                "total_children": children.count(),
                "persons": persons,
                "zip_values": zip_values,
                "delegates": delegates,
                "initial_status": new_initial,
                "show_success_modal": True,
            })

    else:
        form = ChildForm(instance=child)

    return render(request, "account/child_list_institutions.html", {
        "form": form,
        "child": child,
        "persons": persons,
        "zip_values": zip_values,
        "initial_status": initial_status,
        "DEPARTMENTS": Child.DEPARTMENTS,
    })  

from django.contrib.auth.decorators import login_required

@login_required
def child_list_institutions(request):
    governorates = Child.TUNISIA_GOVERNORATES
    selected_governorate = request.GET.get('governorate', '')
    selected_gender = request.GET.get('gender', '')
    DEPARTMENTS = Child.DEPARTMENTS
    delegates = Delegate.objects.exclude(
        user=request.user
    ).exclude(
        email__isnull=True
    ).exclude(
        email=""
    )

    persons = ["الأم", "الأب", "العائلة الموسعة"]
    zip_values = [
        ('accompany', 'اصطحاب'),
        ('temp_abandon', 'تخلي مؤقت'),
        ('final_abandon', 'تخلي نهائي'),
    ]
    
    # ✅ Initialiser children
    children = Child.objects.none()
    
    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        # ✅ CORRECTION : Utiliser 'notifications' au lieu de 'nouveaunotification'
        children = Child.objects.filter(
            Q(delegate_ch=delegate) |
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct().order_by('-created_at')
        
        for child in children:
            print(f"   - {child.first_name} {child.last_name} (status: {child.status})")
    
    # 🔍 Filtres
    if selected_governorate:
        children = children.filter(birth_governorate=selected_governorate)
    if selected_gender:
        children = children.filter(gender=selected_gender)

    context = {
        'children': children,
        'governorates': governorates,
        'selected_governorate': selected_governorate,
        'selected_gender': selected_gender,
        "DEPARTMENTS": DEPARTMENTS,
        'total_children': children.count(),
        'persons': persons,
        'zip_values': zip_values,
        'delegates': delegates,
    }

    return render(request, 'account/child_list_institutions.html', context)


@login_required
def child_delete(request, pk):
    child = get_object_or_404(Child, pk=pk)
    
    allowed_roles = ['chef de bureau', 'central']
    can_delete = False
    
    if request.user.is_superuser:
        can_delete = True
    elif hasattr(request.user, 'delegate_profile'):
        user_role = request.user.delegate_profile.role
        if user_role in allowed_roles:
            can_delete = True
        elif child.delegate_ch == request.user.delegate_profile:
            can_delete = True
    
    if not can_delete:
       
        return redirect('child_list_institutions')
    
    if request.method == "POST":
        child.delete()
        
        return redirect('child_list_institutions')
    
    return render(request, 'child_confirm_delete.html', {'child': child})

def export_children_excel_institution(request):
    selected_gender = request.GET.get('gender', '')

    # Queryset
    children = Child.objects.all()

    # تصفية حسب الجنس
    if selected_gender:
        children = children.filter(gender=selected_gender)

    # اسم الولاية
    wilaya_label = (
        request.user.delegate_profile.get_wilaya_display()
        if hasattr(request.user, 'delegate_profile')
        else ""
    )

    # عنوان Excel
    title_text = (
        f"قائمة الأطفال المهددين بولاية {wilaya_label}"
        if wilaya_label
        else "قائمة الأطفال المهددين (كل الولايات)"
    )

    # إنشاء ملف Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "الأطفال"

    # RTL
    ws.sheet_view.rightToLeft = True
    center_align = Alignment(horizontal="center", vertical="center")

    # عنوان في الصف الأول
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=29)
    ws["A1"] = title_text
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = center_align

    # العناوين
    headers = [
        "تاريخ الإنشاء",
        "المعرف الوحيد",
        "رقم الملف",
        "الاسم",
        "اللقب",
        "الجنس",
        "تاريخ الميلاد",
        "مكان الولادة",
        "الولاية",
        "المعتمدية",
        "الدولة (في حالة الولادة خارج البلاد)",
        "الترسيم بدفاتر الحالة المدنية",
        "عدد الرسم",
        "تاريخ الرسم",
        "جنسية الطفل",
        "الدولة (للطفل الأجنبي)",
        "الولادة",
        "هوية الطفل",
        "إثبات الهوية",
        "سن الأم عند الولادة",
        "مكان الانجاب",
        "عدد الإخوة خارج إطار الزواج",
        "عدد الإخوة في صحبة الام",
        "عدد الإخوة المتخلي عنهم",
        "وثائق الهوية",
        "الوضعية العائلية للطفل الأجنبي",
        "الوضعية القانونية للطفل الأجنبي",
        "الموقف الأولي من الطفل عند الولادة",
    ]

    # صف فارغ ثم الرؤوس
    ws.append([])
    ws.append(headers)

    # تنسيق الرؤوس
    for cell in ws[3]:
        cell.font = Font(bold=True)
        cell.alignment = center_align

    # إضافة البيانات
    for child in children:
        # تحويل initial_status_at_birth إلى نص عربي
        if child.initial_status_at_birth:
            status_texts = []
            for person, status in child.initial_status_at_birth.items():
                if status == "accompany":
                    status_label = "اصطحاب"
                elif status == "temp_abandon":
                    status_label = "تخلي مؤقت"
                elif status == "final_abandon":
                    status_label = "تخلي نهائي"
                else:
                    status_label = "-"
                status_texts.append(f"{person} : {status_label}")
            initial_status_str = "، ".join(status_texts)
        else:
            initial_status_str = "-"

        ws.append([
            child.created_at.strftime("%d/%m/%Y") if child.created_at else "",
            child.uid or "",
            child.numero_dossier or "",
            child.first_name or "",
            child.last_name or "",
            child.get_gender_display() if child.gender else "",
            child.birth_date.strftime("%d/%m/%Y") if child.birth_date else "",
            child.get_birth_place_display() if child.birth_place else "",
            child.get_birth_governorate_display() if child.birth_governorate else "",
            child.birth_department or "",
            str(child.birth_country) if child.birth_country else "",
            child.get_registration_type_display() if child.registration_type else "",
            child.registration_number or "",
            child.registration_date.strftime("%d/%m/%Y") if child.registration_date else "",
            child.get_nationality_display() if child.nationality else "",
            str(child.foreign_country) if child.foreign_country else "",
            child.get_birth_status_display() if child.birth_status else "",
            child.get_child_identity_type_display() if child.child_identity_type else "",
            child.get_identity_proof_display() if child.identity_proof else "",
            child.get_mother_age_at_birth_display() if child.mother_age_at_birth else "",
            child.get_birth_place_detail_display() if child.birth_place_detail else "",
            child.siblings_outside_marriage if child.siblings_outside_marriage is not None else "",
            child.siblings_out if child.siblings_out is not None else "",
            child.siblings_out if child.siblings_out is not None else "",
            "متوفرة" if child.identity_documents_available else "غير متوفرة",
            child.get_foreign_family_status_display() if child.foreign_family_status else "",
             initial_status_str,
        ])

    # محاذاة كل الخلايا
    for row in ws.iter_rows(min_row=4):
        for cell in row:
            cell.alignment = center_align

    # إعداد الاستجابة
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename*=UTF-8''قائمة_الأطفال_المهددين.xlsx"

    wb.save(response)
    return response

# ==================== NOTIFICATIONS ====================

def _can_delegate_notify(current_user, child, is_delegate):
    """
    Retourne True si le délégateur peut ajouter un signalement pour cet enfant.
    ✅ RÈGLE : Tout délégué authentifié peut ajouter un notification
    """
    return is_delegate


def _can_delegate_notify_delinquant(current_user, enfant, is_delegate):
    """
    Retourne True si le délégateur peut ajouter un signalement pour un enfant délinquant.
    ✅ RÈGLE : Tout délégué authentifié peut ajouter un notification
    """
    return is_delegate


@login_required
def new_notification(request, child_id):
    """
    Vue pour créer une nouvelle notification pour un enfant.
    ✅ Tout délégué authentifié peut ajouter une notification.
    ✅ La notification appartient au délégué qui l'a créée (created_by).
    """
    child = get_object_or_404(Child, id=child_id)
    
    # ✅ VÉRIFICATION : Seul un délégué authentifié peut ajouter
    if not hasattr(request.user, 'delegate_profile'):
        messages.error(request, "❌ Vous n'êtes pas autorisé à ajouter une notification.")
        return redirect('child_list_institutions')

    delegate = request.user.delegate_profile

    # ✅ Calcul du numéro par délégué (pas global)
    last_number = (
        NouveauNotification.objects
        .filter(child=child, created_by=delegate)
        .aggregate(Max('notifier_number'))['notifier_number__max']
        or 0
    )
    next_number = last_number + 1

    today = timezone.now().date().isoformat()

    if request.method == "POST":
        threats = {}
        categories = {
            "loss": ("threats_loss", "threats_loss_other"),
            "neglect": ("threats_neglect", "threats_neglect_other"),
            "care": ("threats_care", "threats_care_other"),
            "guardian": ("threats_guardian", "threats_guardian_other"),
            "suicide_methods": ("suicide_methods", "suicide_methods_other"),
            "suicide_reasons": ("suicide_reasons", "suicide_reasons_other"),
            "suicide_place": ("suicide_place", "suicide_place_other"),
            "abuse_types": ("abuse_types", "abuse_types_other"),
            "sexual_exploitation": ("sexual_exploitation", "sexual_exploitation_other"),
            "organized_crime": ("organized_crime", "organized_crime_other"),
            "economic_exploitation": ("economic_exploitation", "economic_exploitation_other"),
        }

        for category, (field_list, field_other) in categories.items():

            selected = request.POST.getlist(field_list)

            other = request.POST.get(field_other, "").strip()

            # إزالة "other"
            selected = [item for item in selected if item != "other"]

    # إضافة النص المكتوب في حقل أخرى
            if other:
                 selected.append(other)

            if selected:
                threats[category] = selected

        notifier_source = request.POST.get('notifier_source')
        notifier_source_other = request.POST.get('notifier_source_other')        

        # ✅ Données avec created_by
        notification_data = {
            "notifier_number": next_number,
            "notification_date": request.POST.get('notification_date'),
            "notifier_source": notifier_source,
            "notifier_source_other": notifier_source_other if notifier_source == "other" else None,
            "notification_method": request.POST.get('notification_method'),
            "threat_source": request.POST.get('threat_source'),
            "threat_location": request.POST.get('threat_location'),
            "threats": threats,
            "created_by": delegate,  # ✅ AJOUT
        }

        NouveauNotification.objects.create(
            child=child,
            **notification_data
        )

# Afficher le modal de succès
        return render(request, "account/notification_new.html", {
            "child": child,
            "show_success_modal": True,
            "next_notifier_number": next_number,
            "notifier_source_choices": NouveauNotification.NOTIFIER_SOURCE_CHOICES,
            "notification_method_choices": NouveauNotification.METHOD_CHOICES,
            "threat_source_choices": NouveauNotification.THREAT_SOURCE_CHOICES,
            "threat_location_choices": NouveauNotification.THREAT_PLACE_CHOICES,
            "today": today,
        })

    # GET
    return render(request, "account/notification_new.html", {
        "child": child,
        "show_success_modal": False,
        "next_notifier_number": next_number,
        "notifier_source_choices": NouveauNotification.NOTIFIER_SOURCE_CHOICES,
        "notification_method_choices": NouveauNotification.METHOD_CHOICES,
        "threat_source_choices": NouveauNotification.THREAT_SOURCE_CHOICES,
        "threat_location_choices": NouveauNotification.THREAT_PLACE_CHOICES,
        "today": today,
    })

def list_notification(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    if hasattr(request.user, 'delegate_profile'):
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=request.user.delegate_profile  # ✅ FILTRE par créateur
        ).order_by("notifier_number")
    else:
        notifications = NouveauNotification.objects.none()

    # Préparer les choix pour les menaces (pour ton formulaire)
    THREATS_CHOICES = {

    "loss": [
        ("parents_dead", "وفاة الأبوين وبقاء الطفل دون سند عائلي"),
        ("parents_hospitalized", "وجود الأبوين بمؤسسة استشفائية وبقاء الطفل دون سند عائلي"),
        ("natural_disaster", "بسبب الكوارث الطبيعية"),
        ("adoptive_parent_dead", "بقاء الطفل المتبنى دون رعاية بموجب وفاة المتبني"),
        ("divorce_refusal", "طلاق الوالدين ورفض كليهما حضانة الطفل"),
        ("parent_absence_unknown", "غياب الأم أو الأب بمغادرة محل الزوجية إلى وجهة غير معلومة"),
        ("step_parent_refusal", "زواج المطلق(ة) أو الأرمل(ة) ورفض حضانة الربيـب من الزوج(ة)"),
        ("chronic_mental_illness", "إصابة الأبوين بمرض عقلي مزمن وبقاء الطفل دون سند عائلي"),
        ("parents_unknown_location", "تواجد الأبوين بوجهة غير معلومة وبقاء الطفل دون سند عائلي"),
        ("parents_imprisoned", "تواجد الأبوين أو أحدهما في السجن وبقاء الطفل دون سند عائلي"),
        ("conflict_zones", "تواجد الأبوين في مناطق النزاع وبقاء الطفل دون سند عائلي"),
    ],

    "neglect": [
        ("hygiene_food", "إهمال العناية بغذاء الطفل ونظافته ولباسه"),
        ("abandonment", "التخلي عن الطفل بمؤسسة عمومية أو خاصة أو بفضاء عام بدون موجب"),
        ("school_absence", "عدم الحضور لتسلم الطفل المقيم بمؤسسة عمومية أو خاصة"),
        ("medical_refusal", "تكرار غياب الطفل عن المدرسة"),
        ("disabled_child", "الامتناع عن مداواته والسهر على علاجه"),
        ("medical", "اعتياد ترك الطفل المعوق داخل البيت مخفيا عن الأنظار"),
        ("medical_re", "التسكع في الشوارع ودون وجهة معلومة"),
        ("medical_ref", "رفض قبول الطفل من كلا الابوين عند صدور قرار في الحضانة"),
        ("medical_refuse", "تعود هجر الابوين لمحل الاسرة لمدة طويلة دون توفير المرافق اللازمة للطفل"),
    ],

    "care": [
        ("no_civil_registration", "عدم ترسيم الطفل بدفاتر الحالة المدنية وحرمانه من الهوية"),
        ("no_school", "عدم الحاق الطفل بمقاعد الدراسة رغم بلوغه سن التمدرس"),
        ("prevent_study", "منع الطفل (ة) من مواصلة دراسته"),
        ("no_supervision", "اعتياد الغياب المدرسي للطفل لإخلال الولي بدوره"),
        ("no_vaccines", "عدم إيلاء الوالدين للطفل أي اهتمام بلفت الانتباه لسلوكه"),
        ("digital_risks", "اعتياد ترك الطفل دون رقابة"),
        ("dig", "ارتداء الطفل للباس غير الملائم للمناخ والمحيط الاجتماعي"),
        ("digi", "تعريض الطفل لحوادث متكررة بسبب التقصير"),
        ("digit", "عدم استيفاء التلاقيح اللازمة"),
        ("digital", "تعرض الطفل لمخاطر وسائل الاتصال الحديثة"),
        ("digital_ri", "عدم زيارة الطفل المريض والمقيم بالمستشفى"),
        ("digital_ris", "عدم الحرص على تلقي الطفل الرعاية الصحية"),
        ("digital_risk", "التعريض لمخاطر الخلافات العائلية"),
    ],

    "guardian": [
        ("dangerous_behavior", "إتيان الطفل لسلوكيات محفوفة بالمخاطر"),
        ("poverty_illness", "عجز عن الإحاطة بالطفل بسبب إصابة الولي بالإعاقة أو مرض أو تقدم في السن"),
        ("school_dropout", "افلات الطفل بصفة بينة عن أية مراقبة من قبل والديه أو الحاضن أو المتعهد به"),
        ("begging", "التسرب والتغيب المدرسي"),
        ("runaway", "تسول الطفل تلقائيا وبإرادته"),
        ("behavior_disorder", "نقص أو انعدام الموارد المادية للأسرة"),
        ("beh", "هروب الطفل من المنزل أو من المؤسسة والمبيت خارجها"),
        ("beha", "عدم زيارة الطفل المريض والمقيم بالمستشفى"),
        ("behavi", "استهلاك المواد السمية المصنفة وغير المصنفة"),
        ("behavior", "ممارسة الطفل التهديد اللفظي والمادي ضد المشرفين على رعايته"),
        ("behavior_d", "اعتداء الطفل على ذاته"),
        ("behavior_dis", "ميل الطفل الى الممارسات الجنسية المثلية"),
        ("behavior_diso", "تعود عدم مراقبة الطفل بتركه يهجر محل الأسرة"),
        ("behavior_disor", "التخلي عن طفل مولود خارج اطار الزواج"),
        ("behavior_disord", "اضطرابات سلوكية"),
        ("behavior_disordd", "ايذاء النفس "),
  
    ],

    # ---------------------------------------------------------
    # محاولة الانتحار – الوسيلة
    # ---------------------------------------------------------
    "suicide_methods": [
        ("dangerous_liquids", "محاولة انتحار الطفل بمواد خطرة أو أدوية"),
        ("burning", "محاولة انتحار الطفل بسكب مواد قابلة للاحتراق على جسده"),
        ("hanging", "محاولة انتحار الطفل شنقًا"),
        ("cutting", "محاولة الانتحار بقطع الشرايين"),
        ("jumping", "محاولة الانتحار بإلقاء نفسه من مكان مرتفع أو أمام وسائل النقل"),
        ("overdose", "محاولة الانتحار بشرب جرعة مفرطة من المواد المخدرة"),
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # محاولة الانتحار – الأسباب
    # ---------------------------------------------------------
    "suicide_reasons": [
        ("cyber_blackmail", "محاولة انتحار الطفل بسبب الابتزاز الإلكتروني"),
        ("social_injustice", "محاولة انتحار الطفل بسبب إحساسه بالغبن نتيجة الظروف الاجتماعية"),
        ("family_conflicts", "محاولة انتحار الطفل بسبب الخلافات العائلية"),
        ("accident", "محاولة انتحار الطفل بسبب حادث عرضي"),
        ("school_failure", "محاولة انتحار الطفل بسبب فشل مدرسي"),
        ("emotional_shock", "محاولة الانتحار بسبب الصدمات العاطفية"),
         ("emotional", "محاولة الانتحار بسبب الالعاب و التحديات  الالكترونية "),
       
        ("shock","محاولة الانتحار بسبب التنمر"),
       
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # محاولة الانتحار – المكان
    # ---------------------------------------------------------
    "suicide_place": [
        ("home", "المنزل"),
        ("school", "مؤسسة تربوية"),
        ("public_space", "فضاء عام"),
        ("care_center", "مؤسسة رعاية"),
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # اعتياد سوء معاملة الطفل
    # ---------------------------------------------------------
    "abuse_types": [
        ("detention", "احتجاز الطفل"),
        ("public_violence", "تعنيف الطفل بالفضاء العام"),
        ("institutional_physical", "تعنيف الطفل جسديًا داخل الإطار المؤسساتي"),
        ("institutional_verbal", "تعنيف الطفل لفظيًا أو معنويًا داخل الإطار المؤسساتي"),
        ("family_physical", "تعنيف الطفل جسديًا من قبل افراد العائلة"),
        ("family_moral", "تعنيف الطفل معنويًا من قبل افراد العائلة"),
        
        ("physical", "تعنيف الطفل جسديًا من قبل شخص من خارج  العائلة"),
        ("moral", "تعنيف الطفل معنويًا من قبل شخص من خارج العائلة"),
       
        ("witness_violence", "تعريض الطفل لمشاهدة الخلافات العنيفة داخل الأسرة"),
        ("discrimination", "تعريض الطفل للتمييز"),
        ("hard_work", "تكليف الطفل بأعمال مرهقة"),
        ("food_deprivation", "عقاب الطفل باعتياد حرمانه من الطعام"),
        ("step_parent_abuse", "سوء معاملة الطفل من قبل زوج الأم / زوجة الأب"),
        ("media_defamation", "التشهير الإعلامي بالحياة الخاصة للطفل"),
        ("torture", "تعريض الطفل للتعذيب"),
        ("disability_abuse", "سوء معاملة الطفل بسبب الإعاقة"),
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # استغلال الطفل جنسيًا
    # ---------------------------------------------------------
    "sexual_exploitation": [
        ("incest", "زنا المحارم"),
        ("family_exploitation", "الاستغلال الجنسي للطفل في المحيط الأسري"),
        ("child_on_child", "الاستغلال الجنسي / اعتداء على طفل من قبل طفل آخر داخل مؤسسة"),
        ("staff_exploitation", "الاستغلال الجنسي للطفل من قبل إطار أو عون مباشر للطفل داخل مؤسسة"),
        ("with_partner", "ممارسة الطفل للجنس مع صديق / صديقة"),
        ("casual_person", "ممارسة الطفل للجنس مع شخص عرضي"),
        ("homosexual_relations", "الاستغلال الجنسي للطفل في العلاقات الجنسية المثلية"),
        ("online_exploitation", "الاستغلال الجنسي عبر وسائل الاتصال الحديثة"),
        ("brothels_service", "خدمة القائمين على بيوت الدعارة من طرف الأطفال"),
        ("sexual_materials", "عرض وتداول مصنفات مطبوعة أو مرئية تخاطب غرائز الطفل الجنسية"),
        ("prostitution", "استغلال الطفل في بغاء الغير ودعارته"),
        ("pornography", "استغلال الطفل في المواد الإباحية و المحامل و الوسائط"),
        ("prostitution_networks", "استغلال الطفل في شبكات الدعارة"),
        ("sex_by_exploiter", "ممارسة الجنس مع الطفل من قبل المستغل"),
        ("sex_in_presence", "ممارسة الجنس بحضور الطفل"),
         ("illegal_adoption", "تبني طفل بغاية استغلاله"),
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # استغلال الطفل في الإجرام المنظم
    # ---------------------------------------------------------
    "organized_crime": [
        ("illegal_border", "محاولة اجتياز الحدود خلسة في اطار جريمة منظمة"),
        ("smuggling", "استغلال الطفل في بيع السلع المهربة والتهريب"),
        ("violence_incitation", "تحريض الطفل على القيام بأعمال العنف والترويع"),
        ("hate_ideas", "استغلال الطفل في زرع أفكار التعصب والكراهية"),
        ("hate_recruitment", "استقطاب الطفل في زرع أفكار التعصب والكراهية"),
        ("online_violence", "تحريض الطفل على العنف عبر وسائل الاتصال الحديثة"),
        ("drug_distribution", "استغلال الطفل في ترويج المواد المخدرة أو الكحولية"),
        ("theft", "استغلال الطفل في عمليات السرقة والنشل"),
        ("alcohol_sales", "استغلال الطفل في بيع المواد الكحولية وترويجها"),
        ("stolen_goods", "ترويج المواد المسروقة"),
        ("public_property", "إشراك الطفل في الاعتداء على المرافق العمومية والممتلكات"),
        ("organized_begging", "استغلال الطفل في التسول في إطار جريمة منظمة"),
        ("armed_conflict", "استغلال الطفل في النزاع المسلح"),
        ("trafficking", "التسفير إلى الخارج بغاية الاستغلال"),
        ("illegal_adoption", "تبني طفل بغاية استغلاله"),
        ("selling_child", "بيع طفل"),
        ("organ_trafficking", "نزع الأعضاء أو الأنسجة أو الخلايا أو الأمشاج أو الأجنة أو جزء منها"),
        ("other", "أخرى"),
    ],

    # ---------------------------------------------------------
    # تعريض الطفل للتسول أو استغلاله اقتصاديًا
    # ---------------------------------------------------------
    "economic_exploitation": [
        ("early_work", "حمل الطفل على العمل في سن مبكر واستغلاله خارج الأطر القانونية"),
        ("public_shows", "استغلال الطفل في عروض جماهيرية غير مرخص فيها"),
        ("marginal_activities", "تعاطي الطفل للأنشطة الهامشية"),
        ("begging", "تعريض الطفل للتسول"),
        ("domestic_work", "استغلال الطفل في العمل المنزلي"),
        ("agriculture", "استغلال الطفل في العمل الفلاحي"),
        ("industry", "استغلال الطفل في العمل الصناعي"),
        ("illegal_adoption", "تبني طفل بغاية استغلاله"),
        ("other", "أخرى"),
    ],
    }

    THREATS_LABELS = {cat: dict(choices) for cat, choices in THREATS_CHOICES.items()}
    THREATS_CATEGORY_LABELS = {
        "loss": "فقدان الطفل لوالديه وبقاؤه دون سند عائلي",
        "neglect": "تعريض الطفل للإهمال والتشرد",
        "care": "التقصير البيّن والمتواصل في التربية والرعاية",
        "guardian": "عجز الأبوين أو من يسهر على رعاية الطفل",

        "suicide_methods": "محاولة الانتحار – الوسيلة",
        "suicide_reasons": "محاولة الانتحار – الأسباب",
        "suicide_place": "محاولة الانتحار – المكان",

        "abuse_types": "اعتياد سوء معاملة الطفل",
        "sexual_exploitation": "استغلال الطفل جنسيًا",
        "organized_crime": "استغلال الطفل في الإجرام المنظم",
        "economic_exploitation": "تعريض الطفل للتسول أو استغلاله اقتصاديًا",
    }

    for notification in notifications:

        threats_display = {}

        for category, values in (notification.threats or {}).items():

            labels = THREATS_LABELS.get(category, {})

            display_values = []

            for value in values:

            # Anciennes données contenant "other"
                if value == "other":
                    continue

            # Valeur connue → traduction arabe
            # Valeur inconnue → texte personnalisé écrit par l'utilisateur
                display_values.append(
                    labels.get(value, value)
                )

            threats_display[category] = display_values

        notification.threats_display = threats_display
       # Récupérer les choices directement depuis le modèle
    notifier_source_choices = NouveauNotification._meta.get_field('notifier_source').choices
    notification_method_choices = NouveauNotification._meta.get_field('notification_method').choices
    threat_source_choices = NouveauNotification._meta.get_field('threat_source').choices
    threat_location_choices = NouveauNotification._meta.get_field('threat_location').choices

    # Catégories de menaces (juste les clés pour loop)
    categories = {k: [v[0] for v in THREATS_CHOICES[k]] for k in THREATS_CHOICES}

    context = {
        "child": child,
        "notifications": notifications,
        "THREATS_LABELS": THREATS_LABELS,
        "THREATS_CHOICES": THREATS_CHOICES,
        "notifier_source_choices": notifier_source_choices,
        "notification_method_choices": notification_method_choices,
        "threat_source_choices": threat_source_choices,
        "threat_location_choices": threat_location_choices,
        "categories": categories,
        "THREATS_CATEGORY_LABELS": THREATS_CATEGORY_LABELS,
    }

    return render(request, "account/listenotification.html", context)

def update_notification(request, notif_id):
    notification = get_object_or_404(NouveauNotification, id=notif_id)
    child = notification.child

    if request.method == "POST":
        # Mettre à jour les champs
        notification.notification_date = request.POST.get('notification_date')
        notification.threat_date = request.POST.get('threat_date')
        notification.notifier_source = request.POST.get('notifier_source')
        notification.notification_method = request.POST.get('notification_method')
        notification.threat_source = request.POST.get('threat_source')
        notification.threat_location = request.POST.get('threat_location')

        # Reconstituer le dictionnaire des menaces
        categories = {
            "loss": ("threats_loss", "threats_loss_other"),
            "neglect": ("threats_neglect", "threats_neglect_other"),
            "care": ("threats_care", "threats_care_other"),
            "guardian": ("threats_guardian", "threats_guardian_other"),
        }

        threats = {}
        for category, (field_list, field_other) in categories.items():
            selected = request.POST.getlist(field_list)
            other = request.POST.get(field_other)
            if other and other.strip():
                selected.append(other.strip())
            if selected:
                threats[category] = selected

        notification.threats = threats
        notification.save()

        notifications = NouveauNotification.objects.filter(child=child).order_by("-notif_at")
        
        return render(
           request,
           "account/listenotification.html",
           {
              "child": child,
              "notifications": notifications,
              "notification_method_choices": NouveauNotification.METHOD_CHOICES,
              "notifier_source_choices": NouveauNotification.NOTIFIER_SOURCE_CHOICES,
              "threat_source_choices": NouveauNotification.THREAT_SOURCE_CHOICES,
              "threat_location_choices": NouveauNotification.THREAT_PLACE_CHOICES,
              "THREATS_CHOICES":  NouveauNotification.threats,
              "show_success_modal": True,
            }
        )

    


# ==================== RECHERCHE ====================

def recherche_child_list(request):
    children = Child.objects.all()
    uid_query = request.GET.get('uid')

    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        if not children.exists():
            return render(request, 'account/child_list_institutions.html', {
                'children': [],
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })

    return render(request, 'account/child_list_institutions.html', {
        'children': children,
        'uid_query': uid_query,
    })


# ==================== IMPORTS ====================

from datetime import datetime

from django.db.models import Q
from django.shortcuts import render

from .models import Child, EnfantDelinquant


# ==================== RECHERCHE ====================

def recherche_enfants(request):

    # ============================================================
    # 1. RÉCUPÉRATION DES PARAMÈTRES DE RECHERCHE
    # ============================================================

    prenom = request.GET.get('prenom', '').strip()
    nom = request.GET.get('nom', '').strip()
    wilaya = request.GET.get('wilaya', '').strip()
    uid = request.GET.get('uid', '').strip()
    date_naissance = request.GET.get('date_naissance', '').strip()

    # ============================================================
    # 2. VARIABLES INITIALES
    # ============================================================

    menaced = Child.objects.none()

    delinquants = []

    transitioned_children = []

    search_attempted = False

    # ============================================================
    # 3. UTILISATEUR CONNECTÉ
    # ============================================================

    current_user = request.user

    is_delegate = (
        hasattr(current_user, 'delegate_profile')
        or hasattr(current_user, 'delegue_profile')
    )

    # ============================================================
    # DEBUG
    # ============================================================

    print("==============================================")
    print("=== APPEL DE recherche_enfants ===")
    print("==============================================")

    print(f"GET parameters      : {request.GET}")
    print(f"Recherche prénom    : '{prenom}'")
    print(f"Recherche nom       : '{nom}'")
    print(f"Recherche wilaya    : '{wilaya}'")
    print(f"Recherche UID       : '{uid}'")
    print(f"Recherche naissance : '{date_naissance}'")
    print(f"is_delegate         : {is_delegate}")

    # ============================================================
    # 4. VÉRIFIER SI UNE RECHERCHE A ÉTÉ EFFECTUÉE
    # ============================================================

    if any([
        prenom,
        nom,
        wilaya,
        uid,
        date_naissance
    ]):

        search_attempted = True

        # ========================================================
        # DATE DE NAISSANCE
        # ========================================================

        date_obj = None

        if date_naissance:

            try:
                date_obj = datetime.strptime(
                    date_naissance,
                    '%Y-%m-%d'
                ).date()

                print(
                    f"Date de naissance convertie : {date_obj}"
                )

            except ValueError:

                print(
                    "⚠️ Date de naissance invalide"
                )

        # ========================================================
        # ========================================================
        # 5. ENFANTS MENACÉS
        #    Child.status = THREATENED
        # ========================================================
        # ========================================================

        filters_m = Q()

        if prenom:

            filters_m &= Q(
                first_name__icontains=prenom
            )

            print(
                f"🔍 Filtre prénom menacé : '{prenom}'"
            )

        if nom:

            filters_m &= Q(
                last_name__icontains=nom
            )

            print(
                f"🔍 Filtre nom menacé : '{nom}'"
            )

        if uid:

            filters_m &= Q(
                uid__icontains=uid
            )

            print(
                f"🔍 Filtre UID menacé : '{uid}'"
            )

        if date_obj:

            filters_m &= Q(
                birth_date=date_obj
            )

            print(
                f"🔍 Filtre date menacé : {date_obj}"
            )

        if wilaya:

            filters_m &= Q(
                birth_governorate=wilaya
            )

            print(
                f"🔍 Filtre wilaya menacé : '{wilaya}'"
            )

        # --------------------------------------------------------
        # REQUÊTE
        # --------------------------------------------------------

        menaced = (
            Child.objects
            .filter(
                filters_m,
                status='THREATENED'
            )
            .select_related('delegate_ch')
        )

        print(
            f"✅ Enfants THREATENED trouvés : "
            f"{menaced.count()}"
        )

        # --------------------------------------------------------
        # INFORMATIONS POUR LE TEMPLATE
        # --------------------------------------------------------

        for child in menaced:

            # Tous les délégués authentifiés peuvent notifier
            child.can_notify = is_delegate

            # Nom du délégué ayant créé l'enfant
            if child.delegate_ch:

                child.delegate_full_name = (
                    f"{child.delegate_ch.first_name} "
                    f"{child.delegate_ch.last_name}"
                )

            else:

                child.delegate_full_name = "غير معروف"

        # ========================================================
        # ========================================================
        # 6. ENFANTS DU MODÈLE EnfantDelinquant
        # ========================================================
        # ========================================================

        filters_d = Q()

        if prenom:

            filters_d &= Q(
                prenom__icontains=prenom
            )

            print(
                f"🔍 Filtre prénom EnfantDelinquant : "
                f"'{prenom}'"
            )

        if nom:

            filters_d &= Q(
                nom__icontains=nom
            )

            print(
                f"🔍 Filtre nom EnfantDelinquant : "
                f"'{nom}'"
            )

        if uid:

            filters_d &= Q(
                num_extrait_naissance__icontains=uid
            )

            print(
                f"🔍 Filtre UID EnfantDelinquant : "
                f"'{uid}'"
            )

        if date_obj:

            filters_d &= Q(
                date_naissance=date_obj
            )

            print(
                f"🔍 Filtre date EnfantDelinquant : "
                f"{date_obj}"
            )

        if wilaya:

            filters_d &= Q(
                delegue__wilaya=wilaya
            )

            print(
                f"🔍 Filtre wilaya EnfantDelinquant : "
                f"'{wilaya}'"
            )

        # --------------------------------------------------------
        # REQUÊTE EnfantDelinquant
        # --------------------------------------------------------

        delinquants_from_model = (
            EnfantDelinquant.objects
            .filter(filters_d)
            .select_related('delegue')
        )

        print(
            "✅ EnfantDelinquant trouvés : "
            f"{delinquants_from_model.count()}"
        )

        # --------------------------------------------------------
        # PRÉPARER LES OBJETS EnfantDelinquant
        # --------------------------------------------------------

        for enfant in delinquants_from_model:

            enfant.can_notify = is_delegate

            if enfant.delegue:

                enfant.delegate_full_name = (
                    f"{enfant.delegue.first_name} "
                    f"{enfant.delegue.last_name}"
                )

            else:

                enfant.delegate_full_name = "غير معروف"

            delinquants.append(enfant)

        # ========================================================
        # ========================================================
        # 7. ENFANTS Child DONT LE STATUT EST DEVENUE
        #    DELINQUENT
        # ========================================================
        #
        # THREATENED
        #      ↓
        # actualisation de situation
        #      ↓
        # DELINQUENT
        #
        # Ces enfants restent des objets Child.
        # ========================================================
        # ========================================================

        filters_child_delinquent = Q()

        if prenom:

            filters_child_delinquent &= Q(
                first_name__icontains=prenom
            )

            print(
                f"🔍 Filtre prénom Child DELINQUENT : "
                f"'{prenom}'"
            )

        if nom:

            filters_child_delinquent &= Q(
                last_name__icontains=nom
            )

            print(
                f"🔍 Filtre nom Child DELINQUENT : "
                f"'{nom}'"
            )

        if uid:

            filters_child_delinquent &= Q(
                uid__icontains=uid
            )

            print(
                f"🔍 Filtre UID Child DELINQUENT : "
                f"'{uid}'"
            )

        if date_obj:

            filters_child_delinquent &= Q(
                birth_date=date_obj
            )

            print(
                f"🔍 Filtre date Child DELINQUENT : "
                f"{date_obj}"
            )

        if wilaya:

            filters_child_delinquent &= Q(
                birth_governorate=wilaya
            )

            print(
                f"🔍 Filtre wilaya Child DELINQUENT : "
                f"'{wilaya}'"
            )

        # --------------------------------------------------------
        # REQUÊTE CHILD DELINQUENT
        # --------------------------------------------------------

        delinquents_from_child = (
            Child.objects
            .filter(
                filters_child_delinquent,
                status='DELINQUENT'
            )
            .select_related('delegate_ch')
        )

        print(
            "✅ Child avec status='DELINQUENT' : "
            f"{delinquents_from_child.count()}"
        )

        # ========================================================
        # ========================================================
        # 8. ENFANTS TRANSITIONNÉS
        # ========================================================
        #
        # IMPORTANT :
        #
        # transitioned_children contient directement les objets
        # Child.
        #
        # Donc :
        #
        # child.id
        #
        # est le ID du modèle Child.
        #
        # Il ne faut PAS supposer qu'il correspond au ID de
        # EnfantDelinquant.
        # ========================================================
        # ========================================================

        for child in delinquents_from_child:

            child.can_notify = is_delegate

            if child.delegate_ch:

                child.delegate_full_name = (
                    f"{child.delegate_ch.first_name} "
                    f"{child.delegate_ch.last_name}"
                )

            else:

                child.delegate_full_name = "غير معروف"

            # ----------------------------------------------------
            # Ajouter à la liste des enfants transitionnés
            # ----------------------------------------------------

            transitioned_children.append(child)

            # ----------------------------------------------------
            # Ajouter aussi à la liste générale des délinquants
            # ----------------------------------------------------

            class DelinquentWrapper:
                pass

            wrapper = DelinquentWrapper()

            wrapper.id = child.id

            wrapper.prenom = child.first_name

            wrapper.nom = child.last_name

            wrapper.sexe = child.gender

            wrapper.date_naissance = child.birth_date

            wrapper.num_extrait_naissance = child.uid

            wrapper.delegue = child.delegate_ch

            wrapper.uid = child.uid

            wrapper.can_notify = is_delegate

            wrapper.child_id = child.id

            wrapper.source = "Child"

            wrapper.status = child.status

            if child.delegate_ch:

                wrapper.delegate_full_name = (
                    f"{child.delegate_ch.first_name} "
                    f"{child.delegate_ch.last_name}"
                )

            else:

                wrapper.delegate_full_name = "غير معروف"

            delinquants.append(wrapper)

        # ========================================================
        # DEBUG FINAL
        # ========================================================

        print("----------------------------------------------")

        print(
            f"✅ Total EnfantDelinquant : "
            f"{len(delinquants_from_model)}"
        )

        print(
            f"✅ Total Child DELINQUENT : "
            f"{len(transitioned_children)}"
        )

        print(
            f"✅ Total liste délinquants : "
            f"{len(delinquants)}"
        )

        print("----------------------------------------------")

        for enfant in delinquants:

            print(
                "  - Délinquant : "
                f"{getattr(enfant, 'prenom', '?')} "
                f"{getattr(enfant, 'nom', '?')}"
            )

            print(
                "    ID : "
                f"{getattr(enfant, 'id', '?')}"
            )

            print(
                "    Child ID : "
                f"{getattr(enfant, 'child_id', 'N/A')}"
            )

            print(
                "    can_notify : "
                f"{getattr(enfant, 'can_notify', False)}"
            )

            print(
                "    delegate_full_name : "
                f"{getattr(enfant, 'delegate_full_name', 'Non défini')}"
            )

    # ============================================================
    # 9. CONTEXT
    # ============================================================

    context = {

        # Enfants actuellement menacés
        'menaced': menaced,

        # Liste générale des délinquants
        'delinquants': delinquants,

        # Child ayant status = DELINQUENT
        #
        # IMPORTANT :
        # ce sont de vrais objets Child
        'transitioned_children': transitioned_children,

        # Liste des wilayas
        'WILAYAS': WILAYAS,

        # Une recherche a-t-elle été effectuée ?
        'search_attempted': search_attempted,

        # Utilisateur délégué ?
        'is_delegate': is_delegate,
    }

    # ============================================================
    # 10. RENDU DU TEMPLATE
    # ============================================================

    return render(
        request,
        'account/recherche_enfants.html',
        context
    )




# ==================== EMAIL ====================

@login_required
def send_child_by_email(request, child_id):
    child = get_object_or_404(Child, id=child_id)

    if request.method == "POST":
        email = request.POST.get("email")
        if not email:
            return JsonResponse({"success": False, "message": "الرجاء اختيار مندوب"})

        sender_delegate = request.user.delegate_profile
        html_content = render_to_string(
            "account/child_details_email.html",
            {"child": child, "sender": sender_delegate}
        )

        email_message = EmailMessage(
           subject=f"بيانات الطفل {child.first_name} {child.last_name}",
           body=html_content,
           from_email=settings.DEFAULT_FROM_EMAIL,
           to=[email],
           reply_to=[sender_delegate.email],  # 👈 هنا المهم
        )
        email_message.content_subtype = "html"
        email_message.send()


        # الرد JSON للنجاح
        return JsonResponse({"success": True, "message": "تم إرسال بيانات الطفل بنجاح"})


# ==================== ENFANTS HORS MARIAGE ====================

def children_abandoned_outside_marriage(request):

    notifications = NouveauNotification.objects.filter(
        threats__guardian__contains=["behavior_disor"]
    ).select_related("child")

    children = Child.objects.filter(
        id__in=notifications.values_list("child_id", flat=True)
    ).distinct()

    context = {
        "children": children,
        "children_count": children.count(),
    }

    return render(
        request,
        "account/children_abandoned_outside_marriage.html",
        context
    )


# ==================== INVESTIGATION ====================
@login_required
def child_list_Investigation(request):
    governorates = Child.TUNISIA_GOVERNORATES
    selected_governorate = request.GET.get('governorate', '')
    selected_gender = request.GET.get('gender', '')
    uid_query = request.GET.get('uid', '')

    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        # ✅ Enfants créés par le délégué OU notifiés par le délégué
        children = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct().order_by('created_at')
    else:
        children = Child.objects.none()

    # 🔍 Filtre UID
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            return render(request, 'account/child_list_Investigation.html', {
                'children_with_notifications': [],
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })

    # 🔍 filtres
    if selected_governorate:
        children = children.filter(birth_governorate=selected_governorate)
    if selected_gender:
        children = children.filter(gender=selected_gender)

    # 🔵 IMPORTANT : ajouter SEULEMENT les notifications du délégué pour chaque enfant
    children_with_notifications = []
    for child in children:
        # ✅ Filtrer par created_by
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        )
        children_with_notifications.append({
            'child': child,
            'notifications': notifications
        })

    context = {
        'children_with_notifications': children_with_notifications,
        'total_children': children.count(),
        'governorates': governorates,
        'selected_governorate': selected_governorate,
        'selected_gender': selected_gender,
        'uid_query': uid_query,
    }

    return render(request, 'account/child_list_Investigation.html', context)



@login_required
def recherche_investigation_list(request):
    """
    Vue recherche : même logique que recherche_child_list.
    Filtre par UID et retourne children_with_notifications avec modal erreur.
    """
    uid_query = request.GET.get('uid', '')
    
    # ✅ Mêmes filtres que child_list_Investigation
    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        children = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct()
    else:
        children = Child.objects.none()

    # 🔍 Recherche par UID
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            # ✅ Aucun enfant trouvé → modal erreur
            return render(request, 'account/child_list_Investigation.html', {
                'children_with_notifications': [],
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })

    # Construction de la liste avec notifications
    children_with_notifications = []
    for child in children:
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        )
        children_with_notifications.append({
            'child': child,
            'notifications': notifications
        })

    return render(request, 'account/child_list_Investigation.html', {
        'children_with_notifications': children_with_notifications,
        'uid_query': uid_query,
    }) 

from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_date
import traceback
from datetime import datetime 

def create_investigation(request, notif_id):
    notification = get_object_or_404(NouveauNotification, id=notif_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                investigation, created = Investigation.objects.get_or_create(
                    notification=notification,
                    defaults={'child': notification.child}
                )
                
                def parse_date_or_none(date_str):
                    if not date_str or str(date_str).strip() == '':
                        return None
                    date_str = str(date_str).strip()
                    parsed = parse_date(date_str)
                    if parsed:
                        return parsed
                    try:
                        return datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                        return None
                
                # Champs simples
                investigation.court_request_date = parse_date_or_none(request.POST.get('court_request_date'))
                investigation.investigation_start = parse_date_or_none(request.POST.get('investigation_start'))
                investigation.psychological_request = parse_date_or_none(request.POST.get('psychological_request'))
                investigation.psychological_result = parse_date_or_none(request.POST.get('psychological_result'))
                investigation.medical_psych_request = parse_date_or_none(request.POST.get('medical_psych_request'))
                investigation.medical_psych_result = parse_date_or_none(request.POST.get('medical_psych_result'))
                investigation.investigation_end = parse_date_or_none(request.POST.get('investigation_end'))
                investigation.save()
                
                # استدعاءات - delete & recreate
                investigation.summons_list.all().delete()
                summons_data = []
                index = 0
                while f'summons_date_{index}' in request.POST:
                    s_date = parse_date_or_none(request.POST.get(f'summons_date_{index}'))
                    s_method = request.POST.get(f'summons_method_{index}', '').strip()
                    a_date = parse_date_or_none(request.POST.get(f'attendance_date_{index}'))
                    
                    if any([s_date, s_method, a_date]):
                        obj = InvestigationSummons.objects.create(
                            investigation=investigation,
                            summons_date=s_date,
                            summons_method=s_method if s_method else None,
                            attendance_date=a_date
                        )
                        summons_data.append({
                            'summons_date': obj.summons_date.strftime('%Y-%m-%d') if obj.summons_date else '',
                            'summons_method': obj.summons_method or '',
                            'attendance_date': obj.attendance_date.strftime('%Y-%m-%d') if obj.attendance_date else '',
                        })
                    index += 1
                
                # زيارات - delete & recreate
                investigation.visit_list.all().delete()
                visit_data = []
                index = 0
                while f'visit_date_{index}' in request.POST:
                    v_date = parse_date_or_none(request.POST.get(f'visit_date_{index}'))
                    v_place = request.POST.get(f'visit_place_{index}', '').strip()
                    
                    if any([v_date, v_place]):
                        obj = InvestigationVisit.objects.create(
                            investigation=investigation,
                            visit_date=v_date,
                            visit_place=v_place if v_place else None
                        )
                        visit_data.append({
                            'visit_date': obj.visit_date.strftime('%Y-%m-%d') if obj.visit_date else '',
                            'visit_place': obj.visit_place or '',
                        })
                    index += 1
                
                # ✅ تقارير اجتماعية - delete & recreate
                investigation.social_report_list.all().delete()
                social_report_data = []
                index = 0
                
                # ✅ Dans la boucle des rapports sociaux :
                while f'social_report_date_{index}' in request.POST:
                    r_request = parse_date_or_none(request.POST.get(f'social_report_request_{index}'))
                    r_receive = parse_date_or_none(request.POST.get(f'social_report_receive_{index}'))
                    r_date = parse_date_or_none(request.POST.get(f'social_report_date_{index}'))
                    r_content = request.POST.get(f'social_report_content_{index}', '').strip()
    
                    if any([r_request, r_receive, r_date, r_content]):
                       obj = InvestigationSocialReport.objects.create(
                           investigation=investigation,
                           report_request=r_request,
                           report_receive=r_receive,
                           report_date=r_date,
                           report_content=r_content if r_content else None
                        )
                    social_report_data.append({
                            'report_request': obj.report_request.strftime('%Y-%m-%d') if obj.report_request else '',
                            'report_receive': obj.report_receive.strftime('%Y-%m-%d') if obj.report_receive else '',
                            'report_date': obj.report_date.strftime('%Y-%m-%d') if obj.report_date else '',
                            'report_content': obj.report_content or '',
                        })
                    index += 1    

                # ✅ تقارير اجتماعية - delete & recreate
                investigation.social_report_list.all().delete()
                social_report_data = []
                index = 0
                while f'social_report_request_{index}' in request.POST:
                    r_request = parse_date_or_none(request.POST.get(f'social_report_request_{index}'))
                    r_receive = parse_date_or_none(request.POST.get(f'social_report_receive_{index}'))
    
                    if any([r_request, r_receive]):
                       obj = InvestigationSocialReport.objects.create(
                           investigation=investigation,
                           report_request=r_request,
                           report_receive=r_receive,
                        )
                    social_report_data.append({
                            'report_request': obj.report_request.strftime('%Y-%m-%d') if obj.report_request else '',
                            'report_receive': obj.report_receive.strftime('%Y-%m-%d') if obj.report_receive else '',
                        })
                    index += 1    
            
            return JsonResponse({
                'success': True,
                'data': {
                    'court_request_date': investigation.court_request_date.strftime('%Y-%m-%d') if investigation.court_request_date else '',
                    'investigation_start': investigation.investigation_start.strftime('%Y-%m-%d') if investigation.investigation_start else '',
                    'psychological_request': investigation.psychological_request.strftime('%Y-%m-%d') if investigation.psychological_request else '',
                    'psychological_result': investigation.psychological_result.strftime('%Y-%m-%d') if investigation.psychological_result else '',
                    'medical_psych_request': investigation.medical_psych_request.strftime('%Y-%m-%d') if investigation.medical_psych_request else '',
                    'medical_psych_result': investigation.medical_psych_result.strftime('%Y-%m-%d') if investigation.medical_psych_result else '',
                    'investigation_end': investigation.investigation_end.strftime('%Y-%m-%d') if investigation.investigation_end else '',
                    'summons_list': summons_data,
                    'visit_list': visit_data,
                    'social_report_list': social_report_data,  # ✅ Ajouté
                }
            })
            
        except Exception as e:
            print("=" * 50)
            print("ERREUR create_investigation:", str(e))
            print(traceback.format_exc())
            print("=" * 50)
            
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return redirect('child_list_Investigation')


from .forms import InvestigationForm  # Créez ce formulaire
from django.forms import modelformset_factory

@login_required
def investigation_list(request, child_id):
    """
    Affiche la liste des investigations pour un enfant sous forme de cartes
    avec édition inline via HTMX
    """
    child = get_object_or_404(Child, id=child_id)
    
    investigations = Investigation.objects.select_related(
        'notification', 
        'notification__child'
    ).filter(notification__child=child).order_by('-created_at')
    
    # Formset pour édition multiple (si besoin bulk edit)
    InvestigationFormSet = modelformset_factory(
        Investigation, 
        form=InvestigationForm,
        extra=0,
        can_delete=False
    )
    
    if request.method == 'POST' and request.headers.get('HX-Request'):
        # Gestion HTMX - mise à jour d'une investigation spécifique
        inv_id = request.POST.get('investigation_id')
        investigation = get_object_or_404(Investigation, id=inv_id, notification__child=child)
        form = InvestigationForm(request.POST, instance=investigation)
        
        if form.is_valid():
            form.save()
            # Retourne la carte en mode lecture
            return render(request, 'account/partials/investigation_card.html', {
                'inv': investigation,
                'child': child
            })
        else:
            # Retourne le formulaire avec erreurs
            return render(request, 'account/partials/investigation_form.html', {
                'form': form,
                'inv': investigation,
                'child': child
            })
    
    context = {
        'child': child,
        'investigations': investigations,
        'page_title': f'إجراءات التقصي - {child.first_name} {child.last_name}'
    }
    return render(request, 'account/investigations.html', context)


@login_required
def investigation_edit_form(request, investigation_id):
    """
    Retourne le formulaire d'édition HTMX pour une investigation
    """
    investigation = get_object_or_404(Investigation, id=investigation_id)
    form = InvestigationForm(instance=investigation)
    
    return render(request, 'account/partials/investigation_form.html', {
        'form': form,
        'inv': investigation,
        'child': investigation.notification.child
    })


@login_required
def child_list_threat_assessment(request):
    """
    Vue principale : affiche tous les enfants menacés avec leurs notifications pour تقدير جدية الإشعار.
    """
    governorates = Child.TUNISIA_GOVERNORATES
    selected_governorate = request.GET.get('governorate', '')
    selected_gender = request.GET.get('gender', '')
    uid_query = request.GET.get('uid', '')

    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        # ✅ CORRECTION : enfants créés par le délégué OU notifiés par le délégué
        children = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct().order_by('created_at')
    else:
        children = Child.objects.none()

    # 🔍 Filtre UID
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            return render(request, 'account/child_list_threat_assessment.html', {
                'children_with_notifications': [],
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
                'governorates': governorates,
                'selected_governorate': selected_governorate,
                'selected_gender': selected_gender,
            })

    # 🔍 Filtres
    if selected_governorate:
        children = children.filter(birth_governorate=selected_governorate)
    if selected_gender:
        children = children.filter(gender=selected_gender)

    # Construction de la liste avec SEULEMENT les notifications du délégué
    children_with_notifications = []
    for child in children:
        # ✅ Filtrer par created_by
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        )
        children_with_notifications.append({
            'child': child,
            'notifications': notifications
        })

    context = {
        'children_with_notifications': children_with_notifications,
        'total_children': children.count(),
        'governorates': governorates,
        'selected_governorate': selected_governorate,
        'selected_gender': selected_gender,
        'uid_query': uid_query,
    }

    return render(request, 'account/child_list_threat_assessment.html', context)


@login_required
def recherche_threat_assessment_list(request):
    """
    Vue recherche : même logique que recherche_child_list.
    Filtre par UID et retourne children_with_notifications.
    """
    uid_query = request.GET.get('uid', '')
    
    # ✅ Mêmes filtres que child_list_threat_assessment
    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        children = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct()
    else:
        children = Child.objects.none()

    # 🔍 Recherche par UID
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            # Aucun enfant trouvé → modal erreur
            return render(request, 'account/child_list_threat_assessment.html', {
                'children_with_notifications': [],
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })

    # Construction de la liste avec notifications
    children_with_notifications = []
    for child in children:
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        )
        children_with_notifications.append({
            'child': child,
            'notifications': notifications
        })

    return render(request, 'account/child_list_threat_assessment.html', {
        'children_with_notifications': children_with_notifications,
        'uid_query': uid_query,
    })


from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_date
import traceback
from datetime import datetime 

def create_threat_assessment(request, notif_id):
    notification = get_object_or_404(NouveauNotification, id=notif_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                threat_assessment, created = ThreatAssessment.objects.get_or_create(
                    notification=notification,
                    defaults={'child': notification.child}
                )
                
                def parse_date_or_none(date_str):
                    if not date_str or str(date_str).strip() == '':
                        return None
                    date_str = str(date_str).strip()
                    parsed = parse_date(date_str)
                    if parsed:
                        return parsed
                    try:
                        return datetime.strptime(date_str, '%d/%m/%Y').date()
                    except ValueError:
                        return None
                
                # Champ date
                threat_assessment.assessment_date = parse_date_or_none(request.POST.get('assessment_date'))
                decision_type = request.POST.get('decision_type')


                # Décisions - التعهد بوضعية الطفل
                threat_assessment.decision_type = request.POST.get('decision_type')
                threat_assessment.decision_social_protection = request.POST.get('decision_social_protection') == 'on'
                threat_assessment.decision_family_judge = request.POST.get('decision_family_judge') == 'on'
                threat_assessment.decision_public_prosecutor = request.POST.get('decision_public_prosecutor') == 'on'
                threat_assessment.decision_violence_unit = request.POST.get('decision_violence_unit') == 'on'
                threat_assessment.decision_relevant_services = request.POST.get('decision_relevant_services') == 'on'
                threat_assessment.decision_trafficking_committee = request.POST.get('decision_trafficking_committee') == 'on'

                threat_assessment.decision_family_referral = (request.POST.get('decision_family_referral') == 'on')
                # Décisions - عدم التعهد بوضعية الطفل
                threat_assessment.reason_not_serious = request.POST.get('reason_not_serious') == 'on'
                threat_assessment.reason_not_professional = request.POST.get('reason_not_professional') == 'on'
                threat_assessment.reason_not_territorial = request.POST.get('reason_not_territorial') == 'on'
                threat_assessment.reason_age_18 = request.POST.get('reason_age_18') == 'on'
                threat_assessment.reason_address_inaccurate = request.POST.get('reason_address_inaccurate') == 'on'
                threat_assessment.reason_threat_removed = request.POST.get('reason_threat_removed') == 'on'
                threat_assessment.reason_child_death = request.POST.get('reason_child_death') == 'on'
                # ⬇️ NOUVEAUX CHAMPS AJOUTÉS
                threat_assessment.reason_no_agreement_20_days = request.POST.get('reason_no_agreement_20_days') == 'on'
                threat_assessment.reason_agreement_breached = request.POST.get('reason_agreement_breached') == 'on'
                
                # Notes
                threat_assessment.notes = request.POST.get('notes', '').strip()
                
                threat_assessment.save()
                # Sauvegarde de l'évaluation
                threat_assessment.save()

# ==================== Création automatique de la notification de traite ====================
                if threat_assessment.decision_trafficking_committee:

                    trafficking_notification, created = TraffickingNotification.objects.get_or_create(
                        threat_assessment=threat_assessment,
                        defaults={
                            "child": threat_assessment.child,
                            "delegate_ch": request.user.delegate_profile,
                            "notifier_number": notification.notifier_number,
                        }
                    )

                    # Mise à jour si la notification existe déjà
                    trafficking_notification.child = threat_assessment.child
                    trafficking_notification.delegate_ch = request.user.delegate_profile
                    trafficking_notification.notifier_number = notification.notifier_number
                    trafficking_notification.save()

                else:
                    # Si la décision est décochée, supprimer la notification
                    TraffickingNotification.objects.filter(
                        threat_assessment=threat_assessment
                    ).delete()
            return JsonResponse({
                'success': True,
                'data': {
                    
                    'assessment_date': threat_assessment.assessment_date.strftime('%Y-%m-%d') if threat_assessment.assessment_date else '',
                    'decision_social_protection': threat_assessment.decision_social_protection,
                    'decision_family_judge': threat_assessment.decision_family_judge,
                    'decision_public_prosecutor': threat_assessment.decision_public_prosecutor,
                    'decision_violence_unit': threat_assessment.decision_violence_unit,
                    'decision_relevant_services': threat_assessment.decision_relevant_services,
                    'decision_trafficking_committee': threat_assessment.decision_trafficking_committee,
                    'reason_not_serious': threat_assessment.reason_not_serious,
                    'reason_not_professional': threat_assessment.reason_not_professional,
                    'reason_not_territorial': threat_assessment.reason_not_territorial,
                    'reason_age_18': threat_assessment.reason_age_18,
                    'reason_address_inaccurate': threat_assessment.reason_address_inaccurate,
                    'reason_threat_removed': threat_assessment.reason_threat_removed,
                    'reason_child_death': threat_assessment.reason_child_death,
                    # ⬇️ NOUVEAUX CHAMPS AJOUTÉS
                    'reason_no_agreement_20_days': threat_assessment.reason_no_agreement_20_days,
                    'reason_agreement_breached': threat_assessment.reason_agreement_breached,
                    'notes': threat_assessment.notes,
                    'decision_family_referral': threat_assessment.decision_family_referral,
                }
            })
            
        except Exception as e:
            print("=" * 50)
            print("ERREUR create_threat_assessment:", str(e))
            print(traceback.format_exc())
            print("=" * 50)
            
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return redirect('child_list_threat_assessment')


from .forms import ThreatAssessmentForm  # Créez ce formulaire
from django.forms import modelformset_factory
@login_required
def threat_assessment_list(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
    # DEBUG
    all_threats = ThreatAssessment.objects.all()
    print(f"=== TOTAL ThreatAssessment: {all_threats.count()} ===")
    for t in all_threats:
        print(f"  ID={t.id}, child_id={t.child_id}, notif_child_id={t.notification.child_id if t.notification else None}")
    
    assessments = ThreatAssessment.objects.select_related('child', 'notification').filter(
        models.Q(child=child) | models.Q(notification__child=child)
    ).order_by('-assessment_date', '-created_at')
    
    print(f"=== Filtered for child {child_id}: {assessments.count()} ===")
    
    # Formset pour édition multiple (si besoin bulk edit)
    ThreatAssessmentFormSet = modelformset_factory(
        ThreatAssessment, 
        form=ThreatAssessmentForm,
        extra=0,
        can_delete=False
    )
    
    if request.method == 'POST' and request.headers.get('HX-Request'):
        # Gestion HTMX - mise à jour d'une évaluation spécifique
        assessment_id = request.POST.get('assessment_id')
        assessment = get_object_or_404(ThreatAssessment, id=assessment_id, child=child)
        form = ThreatAssessmentForm(request.POST, instance=assessment)
        
        if form.is_valid():
            form.save()
            # Retourne la carte en mode lecture
            return render(request, 'account/threat_assessment_card.html', {
                'assessment': assessment,
                'child': child
            })
        else:
            # Retourne le formulaire avec erreurs
            return render(request, 'account/threat_assessment_form.html', {
                'form': form,
                'assessment': assessment,
                'child': child
            })
    
    context = {
        'child': child,
        'assessments': assessments,
        'page_title': f'تقدير جدية الإشعار - {child.first_name} {child.last_name}'
    }
    return render(request, 'account/threat_assessments.html', context)

@login_required
def threat_assessment_edit_form(request, assessment_id):
    """
    Retourne le formulaire d'édition HTMX pour une évaluation de menace
    """
    assessment = get_object_or_404(ThreatAssessment, id=assessment_id)
    form = ThreatAssessmentForm(instance=assessment)
    
    return render(request, 'account/threat_assessment_form.html', {
        'form': form,
        'assessment': assessment,
        'child': assessment.child
    })



# ==================== SOCIAL FILE ====================

from .models import SocialDossierEnfant

@login_required
def child_list_social_file(request):
    """Vue liste des enfants avec leurs notifications pour créer des dossiers sociaux"""
    governorates = Child.TUNISIA_GOVERNORATES
    selected_governorate = request.GET.get('governorate', '')
    selected_gender = request.GET.get('gender', '')
    uid_query = request.GET.get('uid', '')

    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        children = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct().order_by('created_at')
    else:
        children = Child.objects.none()

    # 🔍 Recherche par UID
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            return render(request, 'account/child_list_social_file.html', {
                'children_with_notifications': [],
                'total_children': 0,
                'governorates': governorates,
                'selected_governorate': selected_governorate,
                'selected_gender': selected_gender,
                'uid_query': uid_query,
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })

    # Filtres
    if selected_governorate:
        children = children.filter(birth_governorate=selected_governorate)
    if selected_gender:
        children = children.filter(gender=selected_gender)

    # Ajouter SEULEMENT les notifications du délégué pour chaque enfant
    children_with_notifications = []
    for child in children:
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        )
        children_with_notifications.append({
            'child': child,
            'notifications': notifications
        })

    context = {
        'children_with_notifications': children_with_notifications,
        'total_children': children.count(),
        'governorates': governorates,
        'selected_governorate': selected_governorate,
        'selected_gender': selected_gender,
        'uid_query': uid_query,
    }

    return render(request, 'account/child_list_social_file.html', context)

@require_POST
def create_social_file(request, notif_id):
    """Vue AJAX pour créer/mettre à jour le dossier social"""
    notification = get_object_or_404(NouveauNotification, id=notif_id)
    
    try:
        with transaction.atomic():
            social_file, created = SocialDossierEnfant.objects.get_or_create(
                notification=notification,
                defaults={'child': notification.child}
            )
            
            # ==================== بيانات الطفل ====================
            social_file.current_address = request.POST.get('current_address', '').strip()
            social_file.governorate = request.POST.get('governorate', '').strip()
            social_file.delegation = request.POST.get('delegation', '').strip()
            social_file.educational_status = request.POST.get('educational_status', '').strip()
            social_file.health_status = request.POST.get('health_status', '').strip()
            social_file.social_allowance = request.POST.get('social_allowance', '').strip()
            social_file.academic_results = request.POST.get('academic_results', '').strip()
            social_file.is_disabled = request.POST.get('is_disabled', 'no')
            social_file.disability_type = request.POST.get('disability_type', '')
            social_file.disability_degree = request.POST.get('disability_degree', '')
            
            # ==================== بيانات العائلة ====================
            social_file.family_type = request.POST.get('family_type', '').strip()
            social_file.parents_relationship = request.POST.get('parents_relationship', '').strip()
            social_file.family_income_source = request.POST.get('family_income_source', '').strip()
            social_file.family_social_status = request.POST.get('family_social_status', '').strip()
            social_file.health_access = request.POST.get('health_access', '').strip()
            
            # ==================== بيانات الأب ====================
            social_file.father_first_name = request.POST.get('father_first_name', '').strip()
            social_file.father_last_name = request.POST.get('father_last_name', '').strip()
            social_file.father_nationality_1 = request.POST.get('father_nationality_1', '').strip()
            social_file.father_nationality_2 = request.POST.get('father_nationality_2', '').strip()
            social_file.father_residence_location = request.POST.get('father_residence_type', '').strip()
            social_file.father_governorate = request.POST.get('father_governorate', '').strip()
            social_file.father_delegation = request.POST.get('father_delegation', '').strip()
            social_file.father_country_abroad = request.POST.get('father_country_abroad', '').strip()
            social_file.father_education_level = request.POST.get('father_education', '').strip()
            social_file.father_job_status = request.POST.get('father_profession', '').strip()
            social_file.father_job_status = request.POST.get('father_profession', '').strip()
            social_file.father_health_status = request.POST.get('father_health_status', '').strip() 
            
            # ==================== بيانات الأم ====================
            social_file.mother_first_name = request.POST.get('mother_first_name', '').strip()
            social_file.mother_last_name = request.POST.get('mother_last_name', '').strip()
            social_file.mother_nationality_1 = request.POST.get('mother_nationality_1', '').strip()
            social_file.mother_nationality_2 = request.POST.get('mother_nationality_2', '').strip()
            social_file.mother_residence_location = request.POST.get('mother_residence_type', '').strip()
            social_file.mother_governorate = request.POST.get('mother_governorate', '').strip()
            social_file.mother_delegation = request.POST.get('mother_delegation', '').strip()
            social_file.mother_country_abroad = request.POST.get('mother_country_abroad', '').strip()
            social_file.mother_education_level = request.POST.get('mother_education', '').strip()
            social_file.mother_job_status = request.POST.get('mother_profession', '').strip()
            social_file.mother_job_status = request.POST.get('mother_profession', '').strip()
            social_file.mother_health_status = request.POST.get('mother_health_status', '').strip()
            
            social_file.save()
        
        return JsonResponse({
            'success': True,
            'data': {
                # بيانات الطفل
                'current_address': social_file.current_address,
                'governorate': social_file.governorate,
                'delegation': social_file.delegation,
                'educational_status': social_file.educational_status,
                'health_status': social_file.health_status,
                'social_allowance': social_file.social_allowance,
                'academic_results': social_file.academic_results,
                'is_disabled': social_file.is_disabled,
                'disability_type': social_file.disability_type,
            'disability_degree': social_file.disability_degree,
       
                # بيانات العائلة
                'family_type': social_file.family_type,
                'parents_relationship': social_file.parents_relationship,
                'family_income_source': social_file.family_income_source,
                'family_social_status': social_file.family_social_status,  # ✅ CORRIGÉ
                'health_access': social_file.health_access,
                # بيانات الأب
                'father_first_name': social_file.father_first_name,
                'father_last_name': social_file.father_last_name,
                'father_nationality_1': social_file.father_nationality_1,
                'father_nationality_2': social_file.father_nationality_2,
                'father_residence_location': social_file.father_residence_location,
                'father_governorate': social_file.father_governorate,
                'father_delegation': social_file.father_delegation,
                'father_country_abroad': social_file.father_country_abroad,
                'father_education_level': social_file.father_education_level,
                'father_job_status': social_file.father_job_status,
                'father_job_status': social_file.father_job_status,
                'father_health_status': social_file.father_health_status,
                # بيانات الأم
                'mother_first_name': social_file.mother_first_name,
                'mother_last_name': social_file.mother_last_name,
                'mother_nationality_1': social_file.mother_nationality_1,
                'mother_nationality_2': social_file.mother_nationality_2,
                'mother_residence_location': social_file.mother_residence_location,
                'mother_governorate': social_file.mother_governorate,
                'mother_delegation': social_file.mother_delegation,
                'mother_country_abroad': social_file.mother_country_abroad,
                'mother_education_level': social_file.mother_education_level,
                'mother_job_status': social_file.mother_job_status,
                'mother_job_status': social_file.mother_job_status,
                'mother_health_status': social_file.mother_health_status,
            }
        })
        
    except Exception as e:
        import traceback
        print("=" * 50)
        print("ERREUR create_social_file:", str(e))
        print(traceback.format_exc())
        print("=" * 50)
        
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .models import Child, SocialDossierEnfant  # Importez le bon modèle

@login_required
def social_file_list(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
    # Un seul fichier : le plus récent pour cet enfant
    latest_file = SocialDossierEnfant.objects.filter(
        child=child
    ).select_related('notification').order_by('-created_at').first()
    
    context = {
        'child': child,
        'social_file': latest_file,  # Notez le singulier
    }
    return render(request, 'account/social_file_list.html', context)


# ==================== DASHBOARDS ====================

from django.db.models import Count, Q
from datetime import datetime

def home_tableauboardstatistique(request):
    all_children = Child.objects.all()
    children = Child.objects.filter(
        delegate_ch=request.user.delegate_profile,
        status='THREATENED'
    )

    # Cartes
    registered_children_count = children.count()
    unmarried_children_count = children.filter(birth_status='UNMARRIED').count()
    foreign_children_count = children.filter(nationality='FOREIGN').count()
    foreign_unmarried_illegal_count = children.filter(
        nationality='FOREIGN',
        birth_status='UNMARRIED',
       
    ).count()
    
    notifications = NouveauNotification.objects.filter(
        threats__guardian__contains=["behavior_disor"]
    ).select_related("child")

    children = Child.objects.filter(
        id__in=notifications.values_list("child_id", flat=True)
    ).distinct()

    # 📊 إحصاء سنوي حسب created_at
    current_year = datetime.now().year
    years = []
    yearly_registration = []

    for year in range(2025, current_year + 1):
        count = all_children.filter(created_at__year=year).count()
        years.append(year)
        yearly_registration.append(count)

    # 🔴 إحصاء الإشعارات الخاصة بالمندوب في السنة الحالية
    current_year_notifications = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).count()

    # 🔴 إحصاء الإشعارات حسب الشهر في السنة الحالية (للرسم البياني)
    monthly_notifications = []
    for month in range(1, 13):
        count = NouveauNotification.objects.filter(
            child__delegate_ch=request.user.delegate_profile,
            notification_date__year=current_year,
            notification_date__month=month
        ).count()
        monthly_notifications.append(count)

    context = {
        'registered_children_count': registered_children_count,
        'unmarried_children_count': unmarried_children_count,
        'foreign_children_count': foreign_children_count,
        'foreign_unmarried_illegal_count': foreign_unmarried_illegal_count,
        'years': years,
        'yearly_registration': yearly_registration,
        'children': children,
        "children_count": children.count(),
        # ✅ إضافة الإحصائيات الجديدة
        'current_year_notifications': current_year_notifications,
        'monthly_notifications': monthly_notifications,
        'current_year': current_year,
    }

    return render(request, 'statistiques/tableauboardstatistique.html', context)



from django.db.models import Count, Case, When, Value, IntegerField, Q
from django.utils import timezone
from datetime import datetime
from django.db.models.functions import ExtractYear
from collections import defaultdict

def notifications_tableauboardstatistique(request):
    all_children = Child.objects.all()
    current_year = timezone.now().year
    
    # ✅ CORRIGÉ : enlever __year
    queryset = NouveauNotification.objects.annotate(
        age=current_year - ExtractYear("child__birth_date")
    )
    
    notifications = NouveauNotification.objects.filter(
        threats__guardian__contains=["behavior_disor"]
    ).select_related("child")

    children = Child.objects.filter(
        id__in=notifications.values_list("child_id", flat=True)
    ).distinct()

    # 📊 إحصاء سنوي حسب created_at
    current_year = datetime.now().year
    years = []
    yearly_registration = []

    for year in range(2025, current_year + 1):
        count = all_children.filter(created_at__year=year).count()
        years.append(year)
        yearly_registration.append(count)

    # 🔴 إحصاء الإشعارات الخاصة بالمندوب في السنة الحالية
    current_year_notifications = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).count()

    # 🔴 إحصاء الإشعارات حسب الشهر في السنة الحالية
    monthly_notifications = []
    for month in range(1, 13):
        count = NouveauNotification.objects.filter(
            child__delegate_ch=request.user.delegate_profile,
            notification_date__year=current_year,
            notification_date__month=month
        ).count()
        monthly_notifications.append(count)

    # 📊 إحصاء الإشعارات حسب الفئة العمرية
    today = timezone.now().date()
    
    age_categories = [
    {"label": "0-5 سنوات", "min": 0, "max": 5},
    {"label": "06-12 سنة", "min": 6, "max": 12},
    {"label": "13-17 سنة", "min": 13, "max": 17},
      ]
    
    notifications_by_age = []
    age_labels = []
    
    for category in age_categories:
        count = NouveauNotification.objects.filter(
            child__delegate_ch=request.user.delegate_profile,
            notification_date__year=current_year,
            child__birth_date__isnull=False
        ).annotate(
            age=current_year - ExtractYear("child__birth_date")
        ).filter(
            age__gte=category["min"],
            age__lte=category["max"]
        ).count()
        
        notifications_by_age.append(count)
        age_labels.append(category["label"])

    # ✅ إصلاح: إحصاء الإشعارات حسب الجنس (قيم 'M' و 'F')
    notifications_by_gender = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year,
        child__gender__isnull=False  # ✅ استبعاد الأطفال بدون جنس
    ).values('child__gender').annotate(
        count=Count('id')
    )

    # تحويل إلى قاموس سهل الاستخدام (قيم 'M' و 'F')
    gender_counts = {'M': 0, 'F': 0}
    for item in notifications_by_gender:
        gender_value = item['child__gender']
        if gender_value in gender_counts:
            gender_counts[gender_value] = item['count']
    
    male_count = gender_counts['M']
    female_count = gender_counts['F']
    total_gender = male_count + female_count
    male_percentage = round((male_count / total_gender * 100), 1) if total_gender > 0 else 0
    female_percentage = round((female_count / total_gender * 100), 1) if total_gender > 0 else 0


    # 📊 إحصاء الإشعارات حسب مصدر الإشعار (جديد)
    NOTIFIER_SOURCE_CHOICES = [
       ('child', 'الطفل نفسه'),
       ('father', 'الأب'),
       ('mother', 'الأم'),
       ('relative', 'أحد الأقارب'),
       ('neighbor', 'أحد الجيران'),
       ('judicial', 'جهة قضائية'),
       ('jud', 'سلطة مركزية، جهوية أو محلية '),
       ('judcentrale', ' مصلحة مركزية '),
       ('social', 'مؤسسة اجتماعية'),
       ('health', 'مؤسسة صحية'),
       ('education', 'مؤسسة تربوية'),
       ('security', 'جهة أمنية'),
       ('cial','منظمة وطنية'),
       ('authority', 'منظمة دولية'),
       ('ngo', ' جمعية'),
       ('ngoter', 'هيئة وطنية'),
       ('unknown', 'شخص مجهول'),
       ('delegate', 'مندوب حماية الطفولة'),
       ('other', 'مصدر آخر'),
    ]

# الحصول على الإحصائيات من قاعدة البيانات
    source_stats = NouveauNotification.objects.filter(
       child__delegate_ch=request.user.delegate_profile,
       notification_date__year=current_year
    ).values('notifier_source').annotate(
       count=Count('id')
    ).order_by('-count')

# تحويل إلى قاموس للوصول السريع
    source_counts = {item['notifier_source']: item['count'] for item in source_stats}

# ترتيب البيانات للعرض
    source_labels = []
    source_data = []
    source_colors = [
        '#b8860b', '#ffd966', '#cd853f', '#daa520', '#f0e68c',
        '#4dabf7', '#ff6b9d', '#51cf66', '#ff922b', '#845ef7',
        '#339af0', '#e64980', '#22b8cf', '#fcc419', '#94d82d',
        '#ff8787', '#9775fa', '#74c0fc'
    ]

    for i, (value, label) in enumerate(NOTIFIER_SOURCE_CHOICES):
        count = source_counts.get(value, 0)
        if count > 0:  # عرض فقط المصادر التي لديها إشعارات
            source_labels.append(label)
            source_data.append(count)
    
              

    age_table = list(zip(age_labels, notifications_by_age))
    total_notifications = sum(notifications_by_age)

    age_table.append(("المجموع", total_notifications))


    # 📊 إحصاء الإشعارات حسب مكان التهديد

    place_stats = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).values('threat_location').annotate(
        count=Count('id')
    )

    place_counts = {
        item['threat_location']: item['count']
        for item in place_stats
    }

    place_labels = []
    place_data = []

    for value, label in NouveauNotification.THREAT_PLACE_CHOICES:
        count = place_counts.get(value, 0)

        if count > 0:
            place_labels.append(label.strip())
            place_data.append(count)

    place_table = list(zip(place_labels, place_data))
    place_table.append(("المجموع", sum(place_data)))

    month_labels = [
    "جانفي",
    "فيفري",
    "مارس",
    "أفريل",
    "ماي",
    "جوان",
    "جويلية",
    "أوت",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
    ]

    month_table = list(zip(month_labels, monthly_notifications))
    month_table.append(("المجموع", sum(monthly_notifications)))

    source_table = list(zip(source_labels, source_data))
    source_total = sum(source_data)


   

    educational_stats = SocialDossierEnfant.objects.values(
        'educational_status'
    ).annotate(
        count=Count('id')
    )

    edu_counts = {
        item['educational_status']: item['count']
        for item in educational_stats
    }

    

    edu_choices = [
        ("under_school_age", "دون سن التمدرس"),
        ("enrolled", "متمدرس"),
        ("vocational_training", "مرسم بإحدى مسارات مراكز التكوين المهني/تدريب مهني"),
        ("dropped_out", "منقطع عن الدراسة"),
        ("not_enrolled", "لم يلتحق بأي مؤسسة تربوية  بتاتا"),
        ("notauther", "غير محدد"),
    ]

    edu_labels = []
    edu_data = []

    for value, label in edu_choices:
        edu_labels.append(label)
        edu_data.append(edu_counts.get(value, 0))
    edu_table = [
    {
        "label": label,
        "value": edu_counts.get(value, 0)
    }
    for value, label in edu_choices
    ]
    total_edu = sum(edu_data)



    threat_stats = {
    "loss": {"male": 0, "female": 0},
    "neglect": {"male": 0, "female": 0},
    "care": {"male": 0, "female": 0},
    "guardian": {"male": 0, "female": 0},
    "abuse_types": {"male": 0, "female": 0},
    "sexual_exploitation": {"male": 0, "female": 0},
    "organized_crime": {"male": 0, "female": 0},
    "economic_exploitation": {"male": 0, "female": 0},
    }
    notifications = NouveauNotification.objects.select_related("child").all()
    for notif in notifications:
        gender = notif.child.gender  # supposition: 'male' / 'female'
        threats = notif.threats or {}

    for category in threat_stats.keys():
        if category in threats:
            if gender == "male":
                threat_stats[category]["male"] += 1
            elif gender == "female":
                threat_stats[category]["female"] += 1

    for category in threat_stats:
        threat_stats[category]["total"] = (
            threat_stats[category]["male"] +
            threat_stats[category]["female"]
    )   

    threat_table = [
    {
        "label": "فقدان الطفل لوالديه وبقاؤه دون سند عائلي",
        "male": threat_stats["loss"]["male"],
        "female": threat_stats["loss"]["female"],
        "total": threat_stats["loss"]["total"],
    },
    {
        "label": "تعريض الطفل للإهمال والتشرد",
        "male": threat_stats["neglect"]["male"],
        "female": threat_stats["neglect"]["female"],
        "total": threat_stats["neglect"]["total"],
    },
    {
        "label": "التقصير البيّن والمتواصل في التربية والرعاية",
        "male": threat_stats["care"]["male"],
        "female": threat_stats["care"]["female"],
        "total": threat_stats["care"]["total"],
    },
    {
        "label": "عجز الأبوين أو من يسهر على رعاية الطفل عن الإحاطة والتربية",
        "male": threat_stats["guardian"]["male"],
        "female": threat_stats["guardian"]["female"],
        "total": threat_stats["guardian"]["total"],
    },
    {
        "label": "اعتياد سوء معاملة الطفل",
        "male": threat_stats["abuse_types"]["male"],
        "female": threat_stats["abuse_types"]["female"],
        "total": threat_stats["abuse_types"]["total"],
    },
    {
        "label": "استغلال الطفل ذكرا كان أو أنثى جنسيًا",
        "male": threat_stats["sexual_exploitation"]["male"],
        "female": threat_stats["sexual_exploitation"]["female"],
        "total": threat_stats["sexual_exploitation"]["total"],
    },
    {
        "label": "استغلال الطفل في الإجرام المنظم",
        "male": threat_stats["organized_crime"]["male"],
        "female": threat_stats["organized_crime"]["female"],
        "total": threat_stats["organized_crime"]["total"],
    },
    {
        "label": "تعريض الطفل للتسول أو استغلاله اقتصاديًا",
        "male": threat_stats["economic_exploitation"]["male"],
        "female": threat_stats["economic_exploitation"]["female"],
        "total": threat_stats["economic_exploitation"]["total"],
    },
    ]  

    total_female = sum(r["female"] for r in threat_table)
    total_male = sum(r["male"] for r in threat_table)
    total_all = sum(r["total"] for r in threat_table)           

        # ---------------------------------------------------------
    # 📊 محاولات انتحار الأطفال حسب الجنس
    # ---------------------------------------------------------

    suicide_female = 0
    suicide_male = 0


    suicide_notifications = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).select_related("child")


    for notif in suicide_notifications:

        threats = notif.threats or {}

        # التحقق هل الإشعار يحتوي على محاولة انتحار
        has_suicide = (
            threats.get("suicide_methods") or
            threats.get("suicide_reasons") or
            threats.get("suicide_place")
        )


        if has_suicide:

            if notif.child.gender == "F":
                suicide_female += 1

            elif notif.child.gender == "M":
                suicide_male += 1



    suicide_total = suicide_female + suicide_male


    suicide_table = [
        {
            "wilaya": request.user.delegate_profile.get_wilaya_display(),
            "female": suicide_female,
            "male": suicide_male,
            "total": suicide_total,
        }
    ]

        # ---------------------------------------------------------
    # 📊 محاولات الانتحار حسب الوسيلة والجنس
    # ---------------------------------------------------------

    suicide_method_choices = [
        ("dangerous_liquids", "مواد خطرة أو أدوية"),
        ("burning", "مواد قابلة للاحتراق"),
        ("hanging", "شنقاً"),
        ("cutting", "قطع الشرايين"),
        ("jumping", "إلقاء نفسه من مكان مرتفع أو أمام وسائل النقل"),
        ("overdose", "جرعة مفرطة"),
        ("other", "أخرى"),
    ]


    suicide_method_stats = {}


    for key, label in suicide_method_choices:
        suicide_method_stats[key] = {
            "label": label,
            "female": 0,
            "male": 0,
            "total": 0,
        }



    for notif in suicide_notifications:

        threats = notif.threats or {}

        methods = threats.get("suicide_methods", [])

        gender = notif.child.gender


        for method in methods:

            if method in suicide_method_stats:

                if gender == "F":
                    suicide_method_stats[method]["female"] += 1

                elif gender == "M":
                    suicide_method_stats[method]["male"] += 1



    for method in suicide_method_stats:

        suicide_method_stats[method]["total"] = (
            suicide_method_stats[method]["female"]
            +
            suicide_method_stats[method]["male"]
        )



    suicide_method_table = list(
        suicide_method_stats.values()
    )


    total_suicide_method_female = sum(
        row["female"] for row in suicide_method_table
    )

    total_suicide_method_male = sum(
        row["male"] for row in suicide_method_table
    )

    total_suicide_method = (
        total_suicide_method_female
        +
        total_suicide_method_male
    )

        # ---------------------------------------------------------
    # 📊 الولادات خارج إطار الزواج للولاية الحالية فقط
    # ---------------------------------------------------------

    unmarried_births = Child.objects.filter(
        delegate_ch=request.user.delegate_profile,
        birth_status='UNMARRIED',
        created_at__year=current_year
    ).values(
        'gender'
    ).annotate(
        count=Count('id')
    )


    unmarried_female = 0
    unmarried_male = 0

    for item in unmarried_births:
        if item['gender'] == 'F':
            unmarried_female = item['count']

        elif item['gender'] == 'M':
            unmarried_male = item['count']


    unmarried_total = unmarried_female + unmarried_male


    # اسم الولاية الحالية
    delegate_wilaya = request.user.delegate_profile.wilaya

    wilaya_label = dict(
        Child.TUNISIA_GOVERNORATES
    ).get(delegate_wilaya, delegate_wilaya)


    unmarried_birth_table = [
        {
            "wilaya": wilaya_label,
            "female": unmarried_female,
            "male": unmarried_male,
            "total": unmarried_total
        }
    ]


    total_unmarried_female = unmarried_female
    total_unmarried_male = unmarried_male
    total_unmarried_all = unmarried_total   
        

    context = {
        'years': years,
        'yearly_registration': yearly_registration,
        'children': children,
        "children_count": children.count(),
        'current_year_notifications': current_year_notifications,
        'monthly_notifications': monthly_notifications,
        'current_year': current_year,
        'age_labels': age_labels,
        'notifications_by_age': notifications_by_age,
        # ✅ إصلاح: استخدام القيم الصحيحة
        'male_count': male_count,
        'female_count': female_count,
        'male_percentage': male_percentage,
        'female_percentage': female_percentage,
        'source_labels': source_labels,
        'source_data': source_data,
        'source_colors': source_colors[:len(source_labels)],
        'age_table': age_table,
        'place_labels': place_labels,
        'place_data': place_data,
        'place_table': place_table,
        'month_labels': month_labels,
        'month_table': month_table,
        'source_table': source_table,
        'source_total': source_total,
        "edu_choices": edu_choices,
        "edu_labels": edu_labels,
        "edu_data": edu_data,
        "edu_table": edu_table,
        "total_edu": total_edu,
        "threat_table": threat_table,
        'total_female': total_female,
        'total_male': total_male,
        'total_all': total_all,
        'suicide_table': suicide_table,
        'suicide_female': suicide_female,
        'suicide_male': suicide_male,
        'suicide_total': suicide_total,
        "suicide_method_table": suicide_method_table,

        "total_suicide_method_female": total_suicide_method_female,

        "total_suicide_method_male": total_suicide_method_male,

        "total_suicide_method": total_suicide_method,
        "suicide_method_labels": [
        row["label"] for row in suicide_method_table
        ],

        "suicide_method_data": [
            row["total"] for row in suicide_method_table
        ],
        'unmarried_birth_table': unmarried_birth_table,
        'total_unmarried_female': total_unmarried_female,
        'total_unmarried_male': total_unmarried_male,
        'total_unmarried_all': total_unmarried_all,
                
    }

    context = get_statistics_context(request)

    return render(
        request,
        'statistiques/notifications_tableauboardstatistique.html',
        context
    )


def get_statistics_context(request):

    all_children = Child.objects.all()
    current_year = timezone.now().year
    
    # ✅ CORRIGÉ : enlever __year
    queryset = NouveauNotification.objects.annotate(
        age=current_year - ExtractYear("child__birth_date")
    )
    
    notifications = NouveauNotification.objects.filter(
        threats__guardian__contains=["behavior_disor"]
    ).select_related("child")

    children = Child.objects.filter(
        id__in=notifications.values_list("child_id", flat=True)
    ).distinct()

    # 📊 إحصاء سنوي حسب created_at
    current_year = datetime.now().year
    years = []
    yearly_registration = []

    for year in range(2025, current_year + 1):
        count = all_children.filter(created_at__year=year).count()
        years.append(year)
        yearly_registration.append(count)

    # 🔴 إحصاء الإشعارات الخاصة بالمندوب في السنة الحالية
    current_year_notifications = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).count()

    # 🔴 إحصاء الإشعارات حسب الشهر في السنة الحالية
    monthly_notifications = []
    for month in range(1, 13):
        count = NouveauNotification.objects.filter(
            child__delegate_ch=request.user.delegate_profile,
            notification_date__year=current_year,
            notification_date__month=month
        ).count()
        monthly_notifications.append(count)

    # 📊 إحصاء الإشعارات حسب الفئة العمرية
    today = timezone.now().date()
    
    age_categories = [
    {"label": "0-5 سنوات", "min": 0, "max": 5},
    {"label": "06-12 سنة", "min": 6, "max": 12},
    {"label": "13-17 سنة", "min": 13, "max": 17},
      ]
    
    notifications_by_age = []
    age_labels = []
    
    for category in age_categories:
        count = NouveauNotification.objects.filter(
            child__delegate_ch=request.user.delegate_profile,
            notification_date__year=current_year,
            child__birth_date__isnull=False
        ).annotate(
            age=current_year - ExtractYear("child__birth_date")
        ).filter(
            age__gte=category["min"],
            age__lte=category["max"]
        ).count()
        
        notifications_by_age.append(count)
        age_labels.append(category["label"])

    # ✅ إصلاح: إحصاء الإشعارات حسب الجنس (قيم 'M' و 'F')
    notifications_by_gender = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year,
        child__gender__isnull=False  # ✅ استبعاد الأطفال بدون جنس
    ).values('child__gender').annotate(
        count=Count('id')
    )

    # تحويل إلى قاموس سهل الاستخدام (قيم 'M' و 'F')
    gender_counts = {'M': 0, 'F': 0}
    for item in notifications_by_gender:
        gender_value = item['child__gender']
        if gender_value in gender_counts:
            gender_counts[gender_value] = item['count']
    
    male_count = gender_counts['M']
    female_count = gender_counts['F']
    total_gender = male_count + female_count
    male_percentage = round((male_count / total_gender * 100), 1) if total_gender > 0 else 0
    female_percentage = round((female_count / total_gender * 100), 1) if total_gender > 0 else 0


    # 📊 إحصاء الإشعارات حسب مصدر الإشعار (جديد)
    NOTIFIER_SOURCE_CHOICES = [
       ('child', 'الطفل نفسه'),
       ('father', 'الأب'),
       ('mother', 'الأم'),
       ('relative', 'أحد الأقارب'),
       ('neighbor', 'أحد الجيران'),
       ('judicial', 'جهة قضائية'),
       ('jud', 'سلطة مركزية، جهوية أو محلية '),
       ('judcentrale', ' مصلحة مركزية '),
       ('social', 'مؤسسة اجتماعية'),
       ('health', 'مؤسسة صحية'),
       ('education', 'مؤسسة تربوية'),
       ('security', 'جهة أمنية'),
       ('cial','منظمة وطنية'),
       ('authority', 'منظمة دولية'),
       ('ngo', ' جمعية'),
       ('ngoter', 'هيئة وطنية'),
       ('unknown', 'شخص مجهول'),
       ('delegate', 'مندوب حماية الطفولة'),
       ('other', 'مصدر آخر'),
    ]

# الحصول على الإحصائيات من قاعدة البيانات
    source_stats = NouveauNotification.objects.filter(
       child__delegate_ch=request.user.delegate_profile,
       notification_date__year=current_year
    ).values('notifier_source').annotate(
       count=Count('id')
    ).order_by('-count')

# تحويل إلى قاموس للوصول السريع
    source_counts = {item['notifier_source']: item['count'] for item in source_stats}

# ترتيب البيانات للعرض
    source_labels = []
    source_data = []
    source_colors = [
        '#b8860b', '#ffd966', '#cd853f', '#daa520', '#f0e68c',
        '#4dabf7', '#ff6b9d', '#51cf66', '#ff922b', '#845ef7',
        '#339af0', '#e64980', '#22b8cf', '#fcc419', '#94d82d',
        '#ff8787', '#9775fa', '#74c0fc'
    ]

    for i, (value, label) in enumerate(NOTIFIER_SOURCE_CHOICES):
        count = source_counts.get(value, 0)
        if count > 0:  # عرض فقط المصادر التي لديها إشعارات
            source_labels.append(label)
            source_data.append(count)
    
              

    age_table = list(zip(age_labels, notifications_by_age))
    total_notifications = sum(notifications_by_age)

    age_table.append(("المجموع", total_notifications))


    # 📊 إحصاء الإشعارات حسب مكان التهديد

    place_stats = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).values('threat_location').annotate(
        count=Count('id')
    )

    place_counts = {
        item['threat_location']: item['count']
        for item in place_stats
    }

    place_labels = []
    place_data = []

    for value, label in NouveauNotification.THREAT_PLACE_CHOICES:
        count = place_counts.get(value, 0)

        if count > 0:
            place_labels.append(label.strip())
            place_data.append(count)

    place_table = list(zip(place_labels, place_data))
    place_table.append(("المجموع", sum(place_data)))

    month_labels = [
    "جانفي",
    "فيفري",
    "مارس",
    "أفريل",
    "ماي",
    "جوان",
    "جويلية",
    "أوت",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
    ]

    month_table = list(zip(month_labels, monthly_notifications))
    month_table.append(("المجموع", sum(monthly_notifications)))

    source_table = list(zip(source_labels, source_data))
    source_total = sum(source_data)


   

    educational_stats = SocialDossierEnfant.objects.values(
        'educational_status'
    ).annotate(
        count=Count('id')
    )

    edu_counts = {
        item['educational_status']: item['count']
        for item in educational_stats
    }

    

    edu_choices = [
        ("under_school_age", "دون سن التمدرس"),
        ("enrolled", "متمدرس"),
        ("vocational_training", "مرسم بإحدى مسارات مراكز التكوين المهني/تدريب مهني"),
        ("dropped_out", "منقطع عن الدراسة"),
        ("not_enrolled", "لم يلتحق بأي مؤسسة تربوية  بتاتا"),
        ("notauther", "غير محدد"),
    ]

    edu_labels = []
    edu_data = []

    for value, label in edu_choices:
        edu_labels.append(label)
        edu_data.append(edu_counts.get(value, 0))
    edu_table = [
    {
        "label": label,
        "value": edu_counts.get(value, 0)
    }
    for value, label in edu_choices
    ]
    total_edu = sum(edu_data)



    threat_stats = {
    "loss": {"male": 0, "female": 0},
    "neglect": {"male": 0, "female": 0},
    "care": {"male": 0, "female": 0},
    "guardian": {"male": 0, "female": 0},
    "abuse_types": {"male": 0, "female": 0},
    "sexual_exploitation": {"male": 0, "female": 0},
    "organized_crime": {"male": 0, "female": 0},
    "economic_exploitation": {"male": 0, "female": 0},
    }
    notifications = NouveauNotification.objects.select_related("child").all()
    for notif in notifications:
        gender = notif.child.gender  # supposition: 'male' / 'female'
        threats = notif.threats or {}

    for category in threat_stats.keys():
        if category in threats:
            if gender == "male":
                threat_stats[category]["male"] += 1
            elif gender == "female":
                threat_stats[category]["female"] += 1

    for category in threat_stats:
        threat_stats[category]["total"] = (
            threat_stats[category]["male"] +
            threat_stats[category]["female"]
    )   

    threat_table = [
    {
        "label": "فقدان الطفل لوالديه وبقاؤه دون سند عائلي",
        "male": threat_stats["loss"]["male"],
        "female": threat_stats["loss"]["female"],
        "total": threat_stats["loss"]["total"],
    },
    {
        "label": "تعريض الطفل للإهمال والتشرد",
        "male": threat_stats["neglect"]["male"],
        "female": threat_stats["neglect"]["female"],
        "total": threat_stats["neglect"]["total"],
    },
    {
        "label": "التقصير البيّن والمتواصل في التربية والرعاية",
        "male": threat_stats["care"]["male"],
        "female": threat_stats["care"]["female"],
        "total": threat_stats["care"]["total"],
    },
    {
        "label": "عجز الأبوين أو من يسهر على رعاية الطفل عن الإحاطة والتربية",
        "male": threat_stats["guardian"]["male"],
        "female": threat_stats["guardian"]["female"],
        "total": threat_stats["guardian"]["total"],
    },
    {
        "label": "اعتياد سوء معاملة الطفل",
        "male": threat_stats["abuse_types"]["male"],
        "female": threat_stats["abuse_types"]["female"],
        "total": threat_stats["abuse_types"]["total"],
    },
    {
        "label": "استغلال الطفل ذكرا كان أو أنثى جنسيًا",
        "male": threat_stats["sexual_exploitation"]["male"],
        "female": threat_stats["sexual_exploitation"]["female"],
        "total": threat_stats["sexual_exploitation"]["total"],
    },
    {
        "label": "استغلال الطفل في الإجرام المنظم",
        "male": threat_stats["organized_crime"]["male"],
        "female": threat_stats["organized_crime"]["female"],
        "total": threat_stats["organized_crime"]["total"],
    },
    {
        "label": "تعريض الطفل للتسول أو استغلاله اقتصاديًا",
        "male": threat_stats["economic_exploitation"]["male"],
        "female": threat_stats["economic_exploitation"]["female"],
        "total": threat_stats["economic_exploitation"]["total"],
    },
    ]  

    total_female = sum(r["female"] for r in threat_table)
    total_male = sum(r["male"] for r in threat_table)
    total_all = sum(r["total"] for r in threat_table)           

        # ---------------------------------------------------------
    # 📊 محاولات انتحار الأطفال حسب الجنس
    # ---------------------------------------------------------

    suicide_female = 0
    suicide_male = 0


    suicide_notifications = NouveauNotification.objects.filter(
        child__delegate_ch=request.user.delegate_profile,
        notification_date__year=current_year
    ).select_related("child")


    for notif in suicide_notifications:

        threats = notif.threats or {}

        # التحقق هل الإشعار يحتوي على محاولة انتحار
        has_suicide = (
            threats.get("suicide_methods") or
            threats.get("suicide_reasons") or
            threats.get("suicide_place")
        )


        if has_suicide:

            if notif.child.gender == "F":
                suicide_female += 1

            elif notif.child.gender == "M":
                suicide_male += 1



    suicide_total = suicide_female + suicide_male


    suicide_table = [
        {
            "wilaya": request.user.delegate_profile.get_wilaya_display(),
            "female": suicide_female,
            "male": suicide_male,
            "total": suicide_total,
        }
    ]

        # ---------------------------------------------------------
    # 📊 محاولات الانتحار حسب الوسيلة والجنس
    # ---------------------------------------------------------

    suicide_method_choices = [
        ("dangerous_liquids", "مواد خطرة أو أدوية"),
        ("burning", "مواد قابلة للاحتراق"),
        ("hanging", "شنقاً"),
        ("cutting", "قطع الشرايين"),
        ("jumping", "إلقاء نفسه من مكان مرتفع أو أمام وسائل النقل"),
        ("overdose", "جرعة مفرطة"),
        ("other", "أخرى"),
    ]


    suicide_method_stats = {}


    for key, label in suicide_method_choices:
        suicide_method_stats[key] = {
            "label": label,
            "female": 0,
            "male": 0,
            "total": 0,
        }



    for notif in suicide_notifications:

        threats = notif.threats or {}

        methods = threats.get("suicide_methods", [])

        gender = notif.child.gender


        for method in methods:

            if method in suicide_method_stats:

                if gender == "F":
                    suicide_method_stats[method]["female"] += 1

                elif gender == "M":
                    suicide_method_stats[method]["male"] += 1



    for method in suicide_method_stats:

        suicide_method_stats[method]["total"] = (
            suicide_method_stats[method]["female"]
            +
            suicide_method_stats[method]["male"]
        )



    suicide_method_table = list(
        suicide_method_stats.values()
    )


    total_suicide_method_female = sum(
        row["female"] for row in suicide_method_table
    )

    total_suicide_method_male = sum(
        row["male"] for row in suicide_method_table
    )

    total_suicide_method = (
        total_suicide_method_female
        +
        total_suicide_method_male
    )

        # ---------------------------------------------------------
    # 📊 الولادات خارج إطار الزواج للولاية الحالية فقط
    # ---------------------------------------------------------

    unmarried_births = Child.objects.filter(
        delegate_ch=request.user.delegate_profile,
        birth_status='UNMARRIED',
        created_at__year=current_year
    ).values(
        'gender'
    ).annotate(
        count=Count('id')
    )


    unmarried_female = 0
    unmarried_male = 0

    for item in unmarried_births:
        if item['gender'] == 'F':
            unmarried_female = item['count']

        elif item['gender'] == 'M':
            unmarried_male = item['count']


    unmarried_total = unmarried_female + unmarried_male


    # اسم الولاية الحالية
    delegate_wilaya = request.user.delegate_profile.wilaya

    wilaya_label = dict(
        Child.TUNISIA_GOVERNORATES
    ).get(delegate_wilaya, delegate_wilaya)


    unmarried_birth_table = [
        {
            "wilaya": wilaya_label,
            "female": unmarried_female,
            "male": unmarried_male,
            "total": unmarried_total
        }
    ]


    total_unmarried_female = unmarried_female
    total_unmarried_male = unmarried_male
    total_unmarried_all = unmarried_total   
        

    context = {
        'years': years,
        'yearly_registration': yearly_registration,
        'children': children,
        "children_count": children.count(),
        'current_year_notifications': current_year_notifications,
        'monthly_notifications': monthly_notifications,
        'current_year': current_year,
        'age_labels': age_labels,
        'notifications_by_age': notifications_by_age,
        # ✅ إصلاح: استخدام القيم الصحيحة
        'male_count': male_count,
        'female_count': female_count,
        'male_percentage': male_percentage,
        'female_percentage': female_percentage,
        'source_labels': source_labels,
        'source_data': source_data,
        'source_colors': source_colors[:len(source_labels)],
        'age_table': age_table,
        'place_labels': place_labels,
        'place_data': place_data,
        'place_table': place_table,
        'month_labels': month_labels,
        'month_table': month_table,
        'source_table': source_table,
        'source_total': source_total,
        "edu_choices": edu_choices,
        "edu_labels": edu_labels,
        "edu_data": edu_data,
        "edu_table": edu_table,
        "total_edu": total_edu,
        "threat_table": threat_table,
        'total_female': total_female,
        'total_male': total_male,
        'total_all': total_all,
        'suicide_table': suicide_table,
        'suicide_female': suicide_female,
        'suicide_male': suicide_male,
        'suicide_total': suicide_total,
        "suicide_method_table": suicide_method_table,

        "total_suicide_method_female": total_suicide_method_female,

        "total_suicide_method_male": total_suicide_method_male,

        "total_suicide_method": total_suicide_method,
        "suicide_method_labels": [
        row["label"] for row in suicide_method_table
        ],

        "suicide_method_data": [
            row["total"] for row in suicide_method_table
        ],
        'unmarried_birth_table': unmarried_birth_table,
        'total_unmarried_female': total_unmarried_female,
        'total_unmarried_male': total_unmarried_male,
        'total_unmarried_all': total_unmarried_all,
                
    }

    return context



from django.http import HttpResponse
from docx import Document
from docx.shared import Inches
from datetime import datetime
import matplotlib.pyplot as plt
import os

from .models import NouveauNotification


# =====================================================
# Fonction création tableau Word
# =====================================================

def add_word_table(document, title, headers, data):

    document.add_heading(title, level=2)

    table = document.add_table(
        rows=1,
        cols=len(headers)
    )

    table.style = "Table Grid"


    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = str(h)


    for row_data in data:

        row = table.add_row().cells

        for i, value in enumerate(row_data):
            row[i].text = str(value)



# =====================================================
# Fonction création graphique
# =====================================================

def create_chart(title, labels, values, filename):

    os.makedirs(
        "media/charts",
        exist_ok=True
    )


    path = (
        f"media/charts/{filename}.png"
    )


    plt.figure(figsize=(7,4))


    plt.bar(
        labels,
        values
    )


    plt.title(title)


    plt.xticks(
        rotation=45,
        ha="right"
    )


    plt.tight_layout()


    plt.savefig(
        path,
        dpi=300
    )


    plt.close()


    return path



# =====================================================
# EXPORT WORD
# =====================================================
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


def set_rtl(paragraph):
    p = paragraph._p
    pPr = p.get_or_add_pPr()
    bidi = OxmlElement('w:bidi')
    bidi.set(qn('w:val'), '1')
    pPr.append(bidi)


def set_table_rtl(table):
    tblPr = table._tbl.tblPr
    bidi = OxmlElement('w:bidiVisual')
    tblPr.append(bidi)


from django.http import HttpResponse
from io import BytesIO
import json
import base64

from docx import Document
from docx.shared import Inches
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def export_word(request):

    # جلب نفس بيانات Dashboard
    context = get_statistics_context(request)


    # استقبال صور الرسوم من Javascript
    body = json.loads(request.body)

    charts = body.get("charts", {})



    document = Document()



    # ==========================
    # العنوان
    # ==========================

    document.add_heading(
        "الإحصائيات الجهوية للإشعارات",
        level=1
    )


    document.add_paragraph(
        f"الولاية : {request.user.delegate_profile.get_wilaya_display()}"
    )


    document.add_paragraph(
        f"السنة : {context['current_year']}"
    )



    # ==========================
    # دالة إضافة جدول
    # ==========================

    def add_table(title, headers, rows):

        document.add_heading(
            title,
            level=2
        )


        table = document.add_table(
            rows=1,
            cols=len(headers)
        )


        table.style = "Table Grid"


        for i,h in enumerate(headers):

            table.rows[0].cells[i].text = str(h)



        for row in rows:

            cells = table.add_row().cells


            for i,value in enumerate(row):

                cells[i].text = str(value)



        set_table_rtl(table)
    # ==========================
    # دالة إضافة الرسم
    # ==========================


    def add_chart(chart_id, title):

        if chart_id in charts:


            document.add_heading(
                title,
                level=2
            )


            img = charts[chart_id]


            img = img.split(",")[1]


            image_bytes = base64.b64decode(img)


            image = BytesIO(image_bytes)


            document.add_picture(
                image,
                width=Inches(5.5)
            )



    # ==================================================
    # 1 - الجنس
    # ==================================================

    add_table(

        "توزيع الإشعارات حسب الجنس",

        [
            "الولاية",
            "إناث",
            "ذكور",
            "المجموع"
        ],

        [
            [
                request.user.delegate_profile.get_wilaya_display(),

                context["female_count"],

                context["male_count"],

                context["female_count"] +
                context["male_count"]

            ]
        ]

    )


    add_chart(
        "genderChart",
        "رسم بياني حسب الجنس"
    )



    # ==================================================
    # 2 - العمر
    # ==================================================

    add_table(

        "توزيع الإشعارات حسب الفئة العمرية",

        [
            "الفئة العمرية",
            "العدد"
        ],

        context["age_table"]

    )


    add_chart(
        "ageChart",
        "رسم بياني حسب الفئة العمرية"
    )



    # ==================================================
    # 3 - مصدر الإشعار
    # ==================================================

    add_table(

        "توزيع الإشعارات حسب مصدر الإشعار",

        [
            "المصدر",
            "العدد"
        ],

        context["source_table"]

    )


    add_chart(
        "sourceChart",
        "رسم بياني حسب مصدر الإشعار"
    )



    # ==================================================
    # 4 - مكان التهديد
    # ==================================================

    add_table(

        "توزيع الإشعارات حسب مكان التهديد",

        [
            "المكان",
            "العدد"
        ],

        context["place_table"]

    )


    add_chart(
        "placeChart",
        "رسم بياني حسب مكان التهديد"
    )



    # ==================================================
    # 5 - الوضعية التربوية
    # ==================================================

    edu_rows=[]


    for item in context["edu_table"]:

        edu_rows.append(

            [
                item["label"],
                item["value"]
            ]

        )


    add_table(

        "الوضعية التربوية",

        [
            "الوضعية",
            "العدد"
        ],

        edu_rows

    )


    add_chart(
        "eduChart",
        "رسم بياني حسب الوضعية التربوية"
    )



    # ==================================================
    # 6 - أشكال التهديد
    # ==================================================

    threat_rows=[]


    for row in context["threat_table"]:

        threat_rows.append(

            [
                row["label"],
                row["female"],
                row["male"],
                row["total"]
            ]

        )


    add_table(

        "أشكال التهديد",

        [
            "التهديد",
            "إناث",
            "ذكور",
            "المجموع"
        ],

        threat_rows

    )



    # ==================================================
    # 7 - الانتحار
    # ==================================================

    add_table(

        "محاولات الانتحار",

        [
            "الولاية",
            "إناث",
            "ذكور",
            "المجموع"
        ],

        [
            [
                request.user.delegate_profile.get_wilaya_display(),

                context["suicide_female"],

                context["suicide_male"],

                context["suicide_total"]

            ]
        ]

    )


    add_chart(
        "suicideChart",
        "رسم بياني لمحاولات الانتحار"
    )



    # ==================================================
    # 8 - وسائل الانتحار
    # ==================================================

    suicide_rows=[]


    for row in context["suicide_method_table"]:

        suicide_rows.append(

            [
                row["label"],
                row["female"],
                row["male"],
                row["total"]
            ]

        )


    add_table(

        "وسائل الانتحار",

        [
            "الوسيلة",
            "إناث",
            "ذكور",
            "المجموع"
        ],

        suicide_rows

    )


    add_chart(
        "suicideMethodChart",
        "رسم بياني حسب وسائل الانتحار"
    )



    # ==================================================
    # 9 - الولادات خارج الزواج
    # ==================================================

    birth_rows=[]


    for row in context["unmarried_birth_table"]:

        birth_rows.append(

            [
                row["wilaya"],
                row["female"],
                row["male"],
                row["total"]
            ]

        )


    add_table(

        "الولادات خارج إطار الزواج",

        [
            "الولاية",
            "إناث",
            "ذكور",
            "المجموع"
        ],

        birth_rows

    )


    add_chart(
        "unmarriedBirthChart",
        "رسم بياني للولادات خارج إطار الزواج"
    )



    # ==================================================
    # 10 - الأشهر
    # ==================================================

    add_table(

        "الإشعارات حسب الأشهر",

        [
            "الشهر",
            "العدد"
        ],

        context["month_table"]

    )


    add_chart(
        "notificationsChart",
        "رسم بياني حسب الأشهر"
    )



    # ==========================
    # حفظ Word
    # ==========================

    buffer = BytesIO()


    document.save(buffer)


    buffer.seek(0)



    response = HttpResponse(

        buffer.getvalue(),

        content_type=
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    )


    response["Content-Disposition"] = (

        f'attachment; filename="Statistiques_{context["current_year"]}.docx"'

    )


    return response


def dashboard_powerbi(request):
    return render(request, "dashboard/powerbi.html", {
        "powerbi_url": "https://app.powerbi.com/reportEmbed?reportId=c05a15f0-50fa-4677-8ff9-13eb575048fa&autoAuth=true&ctid=92dc117d-020f-4bfa-991b-94cd94ad7e4a"
    })


def View_logout(request):
    auth_logout(request)
    return redirect("login_delegate")

@login_required
def home_tableauboard(request):
    """
    Dashboard Central - Statistiques pour toutes les 24 wilayas
    """
    from collections import defaultdict
    from datetime import datetime, timedelta
    from django.utils import timezone
    from django.db.models import Count, Q
    
    # Vérifier que l'utilisateur est un délégué
    if not hasattr(request.user, 'delegate_profile'):
        messages.error(request, "❌ Vous n'avez pas accès à cette page.")
        return redirect('index2')
    
    now = timezone.now()
    today = now.date()
    
    # ===============================
    # Récupération des données (TOUTES les wilayas)
    # ===============================
    enfants_menaces_qs = Child.objects.select_related('delegate_ch').all()
    enfants_delinquants_qs = EnfantDelinquant.objects.select_related('delegue').all()
    
    # ===============================
    # KPIs PRINCIPAUX
    # ===============================
    total_menaces = enfants_menaces_qs.count()
    total_delinquants = enfants_delinquants_qs.count()
    total_global = total_menaces + total_delinquants
    
    def safe_percentage(part, total):
        return round((part / total * 100), 1) if total > 0 else 0
    
    # ===============================
    # KPIs AVANCÉS
    # ===============================
    # Enfants étrangers
    etrangers = enfants_menaces_qs.exclude(
        Q(nationality='TN') | Q(nationality__isnull=True)
    ).count()
    
    # Enfants hors mariage
    unmarried = enfants_menaces_qs.filter(
        birth_status="UNMARRIED"
    ).count()
    
    # Enfants étrangers en situation irrégulière
    irregular = enfants_menaces_qs.filter(
        nationality='FOREIGN',
        
    ).count()
    
    # Total des interventions
    total_interventions = Intervention.objects.count()
    taux_reponse = safe_percentage(total_interventions, total_global) if total_global > 0 else 0
    
    # Statistiques des notifications
    notifications_count = NouveauNotification.objects.count()
    
    # ===============================
    # KPIS
    # ===============================
    kpis = {
        "total_global": total_global,
        "total_menaces": total_menaces,
        "total_delinquants": total_delinquants,
        "menaces_pourcentage": safe_percentage(total_menaces, total_global),
        "delinquants_pourcentage": safe_percentage(total_delinquants, total_global),
        "etrangers": etrangers,
        "unmarried": unmarried,
        "irregular": irregular,
        "taux_reponse": taux_reponse,
        "notifications_count": notifications_count,
    }
    
    # ===============================
    # ÉVOLUTION MENSUELLE (12 derniers mois)
    # ===============================
    mois_arabe = {
        1: 'جانفي', 2: 'فيفري', 3: 'مارس', 4: 'أفريل',
        5: 'ماي', 6: 'جوان', 7: 'جويلية', 8: 'أوت',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    monthly_labels = []
    monthly_data_menaces = []
    monthly_data_delinquants = []
    
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i*30)
        year = month_date.year
        month = month_date.month
        
        monthly_labels.append(f"{mois_arabe[month]} {year}")
        
        monthly_data_menaces.append(
            enfants_menaces_qs.filter(
                created_at__year=year,
                created_at__month=month
            ).count()
        )
        
        monthly_data_delinquants.append(
            enfants_delinquants_qs.filter(
                date_creation__year=year,
                date_creation__month=month
            ).count()
        )
    
    # ===============================
    # STATISTIQUES PAR WILAYA (TOUTES LES 24)
    # ===============================
    wilaya_arabe = dict(WILAYAS)
    wilaya_stats = defaultdict(int)
    
    # Enfants menacés par wilaya
    menaces_by_wilaya = enfants_menaces_qs.exclude(
        birth_governorate__isnull=True
    ).values('birth_governorate').annotate(total=Count('id'))
    
    for item in menaces_by_wilaya:
        wilaya_stats[item['birth_governorate']] += item['total']
    
    # Enfants délinquants par wilaya
    delinquants_by_wilaya = enfants_delinquants_qs.exclude(
        delegue__wilaya__isnull=True
    ).values('delegue__wilaya').annotate(total=Count('id'))
    
    for item in delinquants_by_wilaya:
        wilaya_stats[item['delegue__wilaya']] += item['total']
    
    # Toutes les wilayas avec leurs statistiques
    all_wilayas_stats = []
    for code, name in WILAYAS:
        total = wilaya_stats.get(code, 0)
        percentage = safe_percentage(total, total_global) if total_global > 0 else 0
        all_wilayas_stats.append({
            'code': code,
            'name': name,
            'total': total,
            'percentage': percentage,
        })
    
    # Trier par nombre d'enfants (décroissant)
    all_wilayas_stats.sort(key=lambda x: x['total'], reverse=True)
    
    # Top 10 pour le graphique
    top_10_wilayas = all_wilayas_stats[:10]
    wilaya_labels = [wilaya['name'] for wilaya in top_10_wilayas]
    wilaya_data = [wilaya['total'] for wilaya in top_10_wilayas]
    
    # ===============================
    # DISTRIBUTION PAR ÂGE
    # ===============================
    age_groups = [
        ('0-5', 0, 5),
        ('6-10', 6, 10),
        ('11-15', 11, 15),
        ('16-18', 16, 18),
    ]
    age_labels = ['0-5 سنوات', '6-10 سنوات', '11-15 سنة', '16-18 سنة']
    age_data_menaces = []
    age_data_delinquants = []
    
    for _, min_age, max_age in age_groups:
        max_birth_date = today - timedelta(days=min_age*365)
        min_birth_date = today - timedelta(days=(max_age+1)*365)
        
        age_data_menaces.append(
            enfants_menaces_qs.filter(
                birth_date__gte=min_birth_date,
                birth_date__lte=max_birth_date
            ).count()
        )
        
        age_data_delinquants.append(
            enfants_delinquants_qs.filter(
                date_naissance__gte=min_birth_date,
                date_naissance__lte=max_birth_date
            ).count()
        )
    
    # ===============================
    # STATISTIQUES DES INTERVENTIONS
    # ===============================
    interventions = Intervention.objects.all()
    interventions_stats = {
        "total": interventions.count(),
        "avant_jugement": interventions.filter(etat_procedure="قبل المحاكمة").count(),
        "pendant_jugement": interventions.filter(etat_procedure="أثناء المحاكمة").count(),
        "apres_jugement": interventions.filter(etat_procedure="بعد المحاكمة").count(),
        "detention": interventions.filter(
            situation_actuelle_enfant__in=["في حالة إيقاف", "في حالة إيداع"]
        ).count(),
        "liberte": interventions.filter(situation_actuelle_enfant="في حالة سراح").count(),
    }
    
    intervention_labels = ["قبل المحاكمة", "أثناء المحاكمة", "بعد المحاكمة", "في حالة إيقاف", "في حالة سراح"]
    intervention_data = [
        interventions_stats['avant_jugement'],
        interventions_stats['pendant_jugement'],
        interventions_stats['apres_jugement'],
        interventions_stats['detention'],
        interventions_stats['liberte']
    ]
    
    # ===============================
    # RÉPARTITION DES NOTIFICATIONS PAR SOURCE
    # ===============================
    source_stats = NouveauNotification.objects.values('notifier_source').annotate(
        count=Count('id')
    ).order_by('-count')
    
    source_labels = []
    source_data = []
    source_colors = [
        '#b8860b', '#ffd966', '#cd853f', '#daa520', '#f0e68c',
        '#4dabf7', '#ff6b9d', '#51cf66', '#ff922b', '#845ef7',
        '#339af0', '#e64980', '#22b8cf', '#fcc419', '#94d82d',
        '#ff8787', '#9775fa', '#74c0fc'
    ]
    
    notifier_source_choices = dict(NouveauNotification.NOTIFIER_SOURCE_CHOICES)
    for item in source_stats[:15]:  # Top 15 sources
        label = notifier_source_choices.get(item['notifier_source'], item['notifier_source'])
        if label:
            source_labels.append(label)
            source_data.append(item['count'])
    
    # ===============================
    # ACTIVITÉ RÉCENTE (7 derniers jours)
    # ===============================
    recent_activity = []
    last_week = now - timedelta(days=7)
    
    recent_menaces = enfants_menaces_qs.filter(
        created_at__gte=last_week
    ).order_by('-created_at')[:5]
    
    for c in recent_menaces:
        recent_activity.append({
            "title": f"تسجيل طفل مهدد: {c.first_name} {c.last_name}",
            "subtitle": "حالة تهديد",
            "wilaya": c.get_birth_governorate_display() if c.birth_governorate else "",
            "date": c.created_at,
            "icon": "bi-person-exclamation",
            "color": "warning",
        })
    
    recent_delinquants = enfants_delinquants_qs.filter(
        date_creation__gte=last_week
    ).order_by('-date_creation')[:5]
    
    for e in recent_delinquants:
        recent_activity.append({
            "title": f"تسجيل طفل جانح: {e.prenom} {e.nom}",
            "subtitle": "حالة جنوح",
            "wilaya": e.delegue.get_wilaya_display() if e.delegue and hasattr(e.delegue, 'get_wilaya_display') else "",
            "date": e.date_creation,
            "icon": "bi-person-badge",
            "color": "danger",
        })
    
    recent_activity = sorted(recent_activity, key=lambda x: x["date"], reverse=True)[:10]
    
    # ===============================
    # CONTEXT FINAL
    # ===============================
    context = {
        "kpis": kpis,
        "all_wilayas_stats": all_wilayas_stats,  # Pour le tableau des 24 wilayas
        "wilaya_labels": json.dumps(wilaya_labels, ensure_ascii=False),
        "wilaya_data": json.dumps(wilaya_data),
        "monthly_labels": json.dumps(monthly_labels, ensure_ascii=False),
        "monthly_data_menaces": json.dumps(monthly_data_menaces),
        "monthly_data_delinquants": json.dumps(monthly_data_delinquants),
        "age_labels": json.dumps(age_labels, ensure_ascii=False),
        "age_data_menaces": json.dumps(age_data_menaces),
        "age_data_delinquants": json.dumps(age_data_delinquants),
        "intervention_labels": json.dumps(intervention_labels, ensure_ascii=False),
        "intervention_data": json.dumps(intervention_data),
        "interventions_stats": interventions_stats,
        "recent_activity": recent_activity,
        "source_labels": json.dumps(source_labels, ensure_ascii=False),
        "source_data": json.dumps(source_data),
        "source_colors": json.dumps(source_colors[:len(source_data)]),
        "current_date": now,
        "current_time": now.strftime("%H:%M"),
        "last_update": now.strftime("%d/%m/%Y %H:%M"),
        "total_records": total_global,
    }
    
    return render(request, "dashboard/tableauboard.html", context)

def home_mandoub_jihawi(request):
  

    return render(request, 'dashboard/page_mandoub_jihawi.html')

   
def admindashboard(request):
    
    return render(request, 'dashboard/tableauboard.html')  

# ==================== LISTES SPÉCIALISÉES ====================

def unmarried_children_list(request):
    children = Child.objects.filter(birth_status="UNMARRIED").order_by('-created_at')

    context = {
        'children': children,
    }
    return render(request, 'account/unmarried_children_list.html', context)

def foreign_child_list(request):
    # الأطفال الأجانب فقط
    children = Child.objects.filter(nationality="FOREIGN").order_by('-created_at')

    context = {
        'children': children,
        'total_children': children.count(),
    }

    return render(request, 'account/foreign_child_list.html', context)


@login_required
def foreign_irregular_children_list(request):
    children = Child.objects.filter(
        birth_status="UNMARRIED",
        nationality="FOREIGN",
       
    )

    return render(
        request,
        "account/foreign_irregular_children_list.html",
        {"children": children, 'total_children': children.count(),}
    )

# ---------------------- REGISTER DELEGATE ----------------------

def get_next_unique_id_for_wilaya(wilaya_code):
    prefix = f"D{wilaya_code}_"
    qs = Delegate.objects.filter(
        wilaya=wilaya_code,
        unique_id__startswith=prefix
    ).values_list('unique_id', flat=True)

    max_suffix = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for uid in qs:
        m = pattern.match(uid)
        if m:
            try:
                num = int(m.group(1))
                if num > max_suffix:
                    max_suffix = num
            except:
                continue

    return f"{prefix}{max_suffix + 1}"


def register_delegate(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            wilaya = form.cleaned_data["wilaya"]
            delegate_code = form.cleaned_data["delegate_code"]
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            role = form.cleaned_data["role"]
            phone = form.cleaned_data["phone"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # 🔐 Vérifications
            if not delegate_code:
                messages.error(request, "المعرف الوحيد مطلوب")
                return redirect("register_delegate")

            if not re.fullmatch(r"\d{10}", delegate_code):
                messages.error(request, "المعرف الوحيد يجب أن يحتوي على 10 أرقام بالضبط")
                return redirect("register_delegate")

            # Vérifier si le delegate_code existe déjà
            if Delegate.objects.filter(delegate_code=delegate_code).exists():
                messages.error(request, "هذا المعرف الوحيد مستخدم بالفعل")
                return redirect("register_delegate")

            if User.objects.filter(username=delegate_code).exists():
                messages.error(request, "هذا الحساب موجود بالفعل")
                return redirect("register_delegate")

            try:
                with transaction.atomic():
                    # 1️⃣ Création User
                    user = User.objects.create_user(
                        username=delegate_code,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        email=email or ""
                    )

                    # 2️⃣ Création Delegate
                    delegate = Delegate.objects.create(
                        user=user,
                        delegate_code=delegate_code,
                        wilaya=wilaya,
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        phone=phone,
                        email=email
                    )

                    # 💾 IMPORTANT : Stocker en session pour la page de succès
                    request.session['last_registered_delegate'] = delegate.id
                    request.session['generated_password'] = password  

                    return redirect("register_success")

            except Exception as e:
                messages.error(request, f"خطأ في إنشاء المندوب: {str(e)}")
                return redirect("register_delegate")

        else:
            # Debug : afficher les erreurs du formulaire
            print("Form errors:", form.errors)
            messages.error(request, f"أخطاء: {form.errors}")
            return redirect("register_delegate")

    return render(request, "central/register_delegate.html")


def register_success_view(request):
    delegate_id = request.session.get('last_registered_delegate')
    generated_password = request.session.get('generated_password', '')
    
    delegate = None
    
    if delegate_id:
        try:
            delegate = Delegate.objects.get(id=delegate_id)
            del request.session['last_registered_delegate']
        except Delegate.DoesNotExist:
            pass
    
    # Nettoyer le mot de passe après récupération
    if 'generated_password' in request.session:
        del request.session['generated_password']
    
    context = {
        'delegate': delegate,
        'generated_password': generated_password,
    }
    
    return render(request, 'central/register_success.html', context)


def create_delegate(request):
    if request.method == "POST":
        wilaya = request.POST.get("wilaya")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        role = request.POST.get("role")
        phone = request.POST.get("phone")
        email = request.POST.get("email")
        password = request.POST.get("password")
        unique_number = request.POST.get("unique_number")  # 12 chiffres

        # Vérifications
        if not wilaya or not first_name or not last_name or not email or not password:
            messages.error(request, "جميع الحقول المطلوبة يجب أن تكون معبأة.")
            return redirect("delegate_create")

        if not re.fullmatch(r"\d{12}", unique_number):
            messages.error(request, "الرقم يجب أن يحتوي على 12 رقمًا.")
            return redirect("delegate_create")

        with transaction.atomic():
            # Créer l'utilisateur Django
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            # Générer unique_id
            unique_id = get_next_unique_id_for_wilaya(wilaya)

            # Créer le profil Delegate
            delegate = Delegate.objects.create(
                user=user,
                wilaya=wilaya,
                unique_id=unique_id,
                unique_number=unique_number,
                first_name=first_name,
                last_name=last_name,
                role=role,
                phone=phone,
                email=email
            )

        messages.success(request, f"تم تسجيل المندوب {first_name} {last_name} بنجاح!")
        return redirect("login")

    return render(request, "central/register_delegate.html")

# ---------------------- AJAX ----------------------

def ajax_next_delegate_id(request):
    wilaya = request.GET.get("wilaya")
    if not wilaya:
        return JsonResponse({"error": "wilaya missing"}, status=400)
    next_id = get_next_unique_id_for_wilaya(wilaya)
    return JsonResponse({"next_id": next_id})


def get_state_prefix(request):
    state_code = request.GET.get("state")
    if not state_code:
        return JsonResponse({"error": "State code missing"}, status=400)
    prefix = f"{state_code}-"
    return JsonResponse({"prefix": prefix})


# ==================== AUTHENTIFICATION ====================

def other_dashboard(request):
    return render(request, 'account/index2.html')


def login_delegate(request):
    if request.method == "POST":
        form = DelegateLoginForm(request.POST)

        if form.is_valid():
            unique_id = form.cleaned_data["unique_id"]
            password = form.cleaned_data["password"]

            try:
                delegate = Delegate.objects.select_related("user").get(delegate_code=unique_id)
            except Delegate.DoesNotExist:
                form.add_error(None, "المعرف أو كلمة المرور غير صحيحة")
                return render(request, "account/login.html", {"form": form})

            user = authenticate(
                request,
                username=delegate.user.username,
                password=password
            )

            if user is not None:
                auth_login(request, user)

                # ✅ REDIRECTION VERS L'INTERFACE ADMIN PERSONNALISÉE
                if delegate.role == "chef de bureau":
                    return redirect("admin_dashboard")  # Dashboard admin personnalisé
                elif delegate.role == "central":
                    return redirect("tableauboard")
                else:
                    return redirect("index2")

            form.add_error(None, "المعرف أو كلمة المرور غير صحيحة")

    else:
        form = DelegateLoginForm()

    return render(request, "account/login.html", {"form": form})


@login_required
def delegate_list(request):
    selected_wilaya = request.GET.get('wilaya')
    delegates = Delegate.objects.all()
    if selected_wilaya:
        delegates = delegates.filter(wilaya=selected_wilaya)

    return render(request, "account/delegate_list.html", {
        "delegates": delegates,
        "selected_wilaya": selected_wilaya,
        "wilayas": WILAYAS,
        "roles": ROLES,
    })


def clear_messages(request):
    """Vue pour vider les messages de la session"""
    if request.method == 'POST':
        storage = get_messages(request)
        list(storage)  # Vider les messages
    return JsonResponse({'status': 'ok'})

from django.contrib.messages import get_messages

from django.contrib.messages import get_messages


def delegate_edit(request, pk):
    delegate = get_object_or_404(Delegate, pk=pk)
    
    # FORCER LA SUPPRESSION DES MESSAGES EN GET
    if request.method == 'GET':
        storage = get_messages(request)
        for _ in storage:
            pass
    
    if request.method == 'POST':
        old_wilaya = delegate.wilaya
        old_delegate_code = delegate.delegate_code  # Sauvegarder l'ancien code
        
        delegate.first_name = request.POST.get('first_name')
        delegate.last_name = request.POST.get('last_name')
        new_wilaya = request.POST.get('wilaya')
        delegate.role = request.POST.get('role')
        
        # Validation téléphone
        phone = request.POST.get('phone', '')
        if phone:
            phone = re.sub(r'\D', '', phone)[:8]
        delegate.phone = phone
        
        delegate.email = request.POST.get('email')
        
        # ========== MODIFICATION DU DELEGATE_CODE ==========
        new_delegate_code = request.POST.get('delegate_code', '').strip()
        
        # Vérifier que le nouveau code est valide
        if not new_delegate_code:
            messages.error(request, "المعرف الوحيد مطلوب")
            return render(request, 'account/delegate_edit.html', {
                'delegate': delegate,
                'wilayas': WILAYAS,
                'roles': ROLES
            })
        
        if not re.fullmatch(r"\d{10}", new_delegate_code):
            messages.error(request, "المعرف الوحيد يجب أن يحتوي على 10 أرقام بالضبط")
            return render(request, 'account/delegate_edit.html', {
                'delegate': delegate,
                'wilayas': WILAYAS,
                'roles': ROLES
            })
        
        # Vérifier que le nouveau code n'est pas déjà utilisé par un autre délégué
        if new_delegate_code != old_delegate_code:
            if Delegate.objects.filter(delegate_code=new_delegate_code).exclude(pk=delegate.pk).exists():
                messages.error(request, "هذا المعرف الوحيد مستخدم بالفعل من قبل مندوب آخر")
                return render(request, 'account/delegate_edit.html', {
                    'delegate': delegate,
                    'wilayas': WILAYAS,
                    'roles': ROLES
                })
            
            # Mettre à jour le delegate_code et le username de l'utilisateur
            delegate.delegate_code = new_delegate_code
            delegate.user.username = new_delegate_code
            delegate.user.save()
        
        # Mise à jour wilaya et unique_id si changement
        if new_wilaya != old_wilaya:
            delegate.wilaya = new_wilaya
            prefix = f"D{new_wilaya}_"
            existing_ids = Delegate.objects.filter(
                wilaya=new_wilaya,
                unique_id__startswith=prefix
            ).exclude(pk=delegate.pk).values_list('unique_id', flat=True)
            
            max_suffix = 0
            pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
            for uid in existing_ids:
                match = pattern.match(uid)
                if match:
                    num = int(match.group(1))
                    if num > max_suffix:
                        max_suffix = num
            
            delegate.unique_id = f"{prefix}{max_suffix + 1}"
        
        # Mot de passe
        password = request.POST.get('password')
        if password and password.strip():
            delegate.user.set_password(password)
            delegate.user.save()
        
        # Sauvegarder D'ABORD le delegate
        delegate.save()
        
        # Puis ajouter le message de succès
        messages.success(request, f"تم تعديل بيانات المندوب {delegate.first_name} {delegate.last_name} بنجاح.")
        
        # REDIRECTION au lieu de render - C'est la clé !
        return redirect('delegate_list')
    
    return render(request, 'central/delegate_edit.html', {
        'delegate': delegate,
        'wilayas': WILAYAS,
        'roles': ROLES
    })

def delegate_delete(request, pk):
    delegate = get_object_or_404(Delegate, pk=pk)
    if request.method == "POST":
        nom_complet = f"{delegate.first_name} {delegate.last_name}"
        delegate.delete()
        messages.success(request, f"تم حذف المندوب {nom_complet} بنجاح.")
        return redirect('delegate_list')
    return render(request, 'central/delegate_confirm_delete.html', {'delegate': delegate})


def register_success(request):
    return render(request, 'account/login.html')

def get_state_prefix(request):
    state_code = request.GET.get("state")
    if not state_code:
        return JsonResponse({"error": "State code missing"}, status=400)
    prefix = f"{state_code}-"
    return JsonResponse({"prefix": prefix})

def child_threatened(request):
    return render(request, 'account/child_threatened.html')


def investigation(request):
    return render(request, 'account/investigation.html')


def trafficking(request):
    return render(request, 'account/trafficking.html')


# ==================== ENFANT DELINQUANT ====================


def enfant_create(request):
    if request.method == 'POST':
        
        delegue_id = request.POST.get("delegue") or getattr(request.user.delegate_profile, 'id', None)
        if not delegue_id:
            messages.error(request, "الحقل 'المندوب' فارغ")
            return redirect(request.path)

        try:
            delegue_obj = Delegate.objects.get(id=delegue_id)  # هنا نحول الـ id لكائن
        except Delegate.DoesNotExist:
            messages.error(request, "المندوب المحدد غير موجود")
            return redirect(request.path)
        
        nom = request.POST.get('nom')
        prenom = request.POST.get('prenom')
        sexe = request.POST.get('sexe')
        date_naissance = request.POST.get('date_naissance')
        num_extrait_naissance = request.POST.get('num_extrait_naissance')
        delegue = delegue_obj

        EnfantDelinquant.objects.create(
            nom=nom,
            prenom=prenom,
            sexe=sexe,
            date_naissance=date_naissance,
            num_extrait_naissance=num_extrait_naissance,
            delegue=delegue
        )
        return redirect('enfant_list')
    
    return render(request, 'enfants/enfant_form.html')

def enfant_update(request, pk):
    enfant = get_object_or_404(EnfantDelinquant, pk=pk)
    
    if request.method == 'POST':
        delegue_id = request.POST.get("delegue") or getattr(request.user.delegate_profile, 'id', None)
        if not delegue_id:
            messages.error(request, "الحقل 'المندوب' فارغ")
            return redirect(request.path)

        try:
            delegue_obj = Delegate.objects.get(id=delegue_id)  # هنا نحول الـ id لكائن
        except Delegate.DoesNotExist:
            messages.error(request, "المندوب المحدد غير موجود")
            return redirect(request.path)
        
        enfant.nom = request.POST.get('nom')
        enfant.prenom = request.POST.get('prenom')
        enfant.sexe = request.POST.get('sexe')
        enfant.date_naissance = request.POST.get('date_naissance')
        enfant.num_extrait_naissance = request.POST.get('num_extrait_naissance')
        enfant.delegue = delegue_obj

        enfant.save()
        return redirect('enfant_list')
    
    return render(request, 'enfants/enfant_form.html', {'enfant': enfant})

def enfant_delete(request, pk):
    enfant = get_object_or_404(EnfantDelinquant, pk=pk)
    if request.method == 'POST':
        enfant.delete()
        return redirect('enfant_list')
    return render(request, 'enfants/enfant_confirm_delete.html', {'enfant': enfant})

@login_required
def enfant_hors_mariage_delete(request, pk):
    enfant = get_object_or_404(Child, pk=pk, birth_status="UNMARRIED")
    
    allowed_roles = ['chef de bureau', 'central']
    
    if not request.user.is_superuser:
        if not hasattr(request.user, 'delegate_profile'):
            messages.error(request, "❌ Vous n'avez pas les droits.")
            return redirect('central_enfants_hors_mariage')
        
        if request.user.delegate_profile.role not in allowed_roles:
            messages.error(request, "❌ Votre rôle ne permet pas cette action.")
            return redirect('central_enfants_hors_mariage')
    
    if request.method == 'POST':
        nom_complet = f"{enfant.first_name} {enfant.last_name}"
        enfant.delete()
        messages.success(request, f'✅ تم حذف الطفل {nom_complet} بنجاح')
        return redirect('central_enfants_hors_mariage')
    
    return render(request, 'central/confirm_delete_enfant_hors_mariage.html', {
        'child': enfant
    })

# ==================== SOCIAL FILE ====================


from django.contrib.contenttypes.models import ContentType
@login_required
def social_file(request, enfant_id):
   
    enfant = get_object_or_404(Child, id=enfant_id)
    try:
        social_file = SocialFile.objects.get(enfant=enfant_id)
        is_update = True

    except SocialFile.DoesNotExist:
        social_file = None
        is_update = False 

    if request.method == "POST":
        delegue_id = request.POST.get("delegue") or getattr(request.user.delegate_profile, 'id', None)
        if not delegue_id:
            messages.error(request, "الحقل 'المندوب' فارغ")
            return redirect(request.path)

        try:
            delegue_obj = Delegate.objects.get(id=delegue_id)  # هنا نحول الـ id لكائن
        except Delegate.DoesNotExist:
            messages.error(request, "المندوب المحدد غير موجود")
            return redirect(request.path)
        
        if social_file is None:
            social_file = SocialFile(enfant=enfant)
            is_update = False
        social_file.famille_type = request.POST.get("famille_type", "")
        social_file.relation_parents = request.POST.get("relation_parents", "")
        social_file.source_revenu = request.POST.get("source_revenu", "")
        social_file.situation_sociale = request.POST.get("situation_sociale", "")
        social_file.couverture_sante = request.POST.get("couverture_sante", "")

        social_file.adresse_enfant = request.POST.get("adresse_enfant", "")
        social_file.gouvernorat_enfant = request.POST.get("gouvernorat_enfant", "")
        social_file.delegation_enfant = request.POST.get("delegation_enfant", "")
        social_file.situation_scolaire_enfant = request.POST.get("situation_scolaire_enfant", "")
        social_file.situation_sante_enfant = request.POST.get("situation_sante_enfant", "")
        social_file.beneficiaire_allocation_enfant = request.POST.get("beneficiaire_allocation_enfant", "")
        social_file.resultat_scolaire_enfant = request.POST.get("resultat_scolaire_enfant", "")

        social_file.nom_pere = request.POST.get("nom_pere", "")
        social_file.prenom_pere = request.POST.get("prenom_pere", "")
        social_file.nationalite_pere = request.POST.get("nationalite_pere", "")
        social_file.residence_pere = request.POST.get("residence_pere", "")
        social_file.gouvernorat_pere = request.POST.get("gouvernorat_pere", "")
        social_file.delegation_pere = request.POST.get("delegation_pere", "")
        social_file.pays_pere = request.POST.get("pays_pere", "")
        social_file.niveau_etude_pere = request.POST.get("niveau_etude_pere", "")
        social_file.etat_sante_pere = request.POST.get("etat_sante_pere", "")
        social_file.emploi_pere = request.POST.get("emploi_pere", "")

        social_file.nom_mere = request.POST.get("nom_mere", "")
        social_file.prenom_mere = request.POST.get("prenom_mere", "")
        social_file.nationalite_mere = request.POST.get("nationalite_mere", "")
        social_file.residence_mere = request.POST.get("residence_mere", "")
        social_file.gouvernorat_mere = request.POST.get("gouvernorat_mere", "")
        social_file.delegation_mere = request.POST.get("delegation_mere", "")
        social_file.pays_mere = request.POST.get("pays_mere", "")
        social_file.niveau_etude_mere = request.POST.get("niveau_etude_mere", "")
        social_file.etat_sante_mere = request.POST.get("etat_sante_mere", "")
        social_file.emploi_mere = request.POST.get("emploi_mere", "")
        social_file.delegue = delegue_obj

        social_file.save()
        
        if is_update:
            messages.success(request, "تم تحديث الملف الاجتماعي بنجاح.")
        else:
            messages.success(request, "تم إنشاء الملف الاجتماعي بنجاح.")

        return redirect("enfant_list")

    return render(request, "social_file/social_file_form.html", {"enfant": enfant, "social_file": social_file})



# ==================== INTERVENTIONS ====================

def calculate_age(birth_date, ref_date):
    return ref_date.year - birth_date.year - (
        (ref_date.month, ref_date.day) < (birth_date.month, birth_date.day)
    )



@login_required
def intervention_list(request, enfant_id):
    enfant = get_object_or_404(Child, id=enfant_id)
    if enfant.status != "DELINQUENT":
        messages.error(request, "لا يمكن عرض مطالب الوساطة لهذا الطفل لأنه مسجل كطفل مهدد فقط و ليس طفل جانح.")
        return redirect("enfant_list")
    
    interventions = Intervention.objects.filter(enfant=enfant)

    return render(request, "intervention/intervention_list.html", {
        "enfant": enfant,
        "interventions": interventions
    })


@login_required
def intervention_create(request, enfant_id):
    enfant = get_object_or_404(Child, id=enfant_id)

    if enfant.status != "DELINQUENT":
        messages.error(request, "لا يمكن إضافة تدخل لهذا الطفل لأنه مسجل كطفل مهدد فقط و ليس طفل جانح.")
        return redirect("intervention_list", enfant_id=enfant.id)

    total_interventions = Intervention.objects.filter(enfant=enfant).count()
    before_trial = Intervention.objects.filter(enfant=enfant, etat_procedure="قبل المحاكمة").count()
    during_trial = Intervention.objects.filter(enfant=enfant, etat_procedure="أثناء المحاكمة").count()
    after_trial = Intervention.objects.filter(enfant=enfant, etat_procedure="بعد المحاكمة").count()
    total_recidive = Intervention.objects.filter(enfant=enfant, enfant_recidiviste="نعم").count()
    total_detention = Intervention.objects.filter(
        enfant=enfant,
        situation_actuelle_enfant__in=["في حالة إيقاف", "في حالة إيداع"]
    ).count()
    total_free = Intervention.objects.filter(
        enfant=enfant,
        situation_actuelle_enfant="في حالة سراح"
    ).count()

    if request.method == "POST":
        try:
            date_intervention = safe_date(request.POST.get("date_intervention"))
            date_fait = safe_date(request.POST.get("date_fait"))
            accord_date = safe_date(request.POST.get("accord_date"))

            if not date_intervention:
                messages.error(request, "تاريخ التدخل إجباري")
                return redirect(request.path)

            if date_fait:
                if not enfant.birth_date:
                    messages.error(request, "تاريخ ميلاد الطفل غير محدد، الرجاء تحيينه")
                    return redirect(request.path)

                age = calculate_age(enfant.birth_date, date_fait)

                if age > 18:
                    messages.error(request, "عمر الطفل أكبر من 18 سنة")
                    return redirect(request.path)

                if age <= 0:
                    messages.error(request, "تاريخ الفعلة غير صالح مقارنة بتاريخ الميلاد")
                    return redirect(request.path)

            delegue_id = request.POST.get("delegue") or getattr(request.user, "delegate_profile", None)

            if not delegue_id:
                messages.error(request, "حقل المندوب إجباري")
                return redirect(request.path)

            delegue_obj = Delegate.objects.get(id=delegue_id)

            accord = request.POST.get("accord_reached")
            accord_reached = True if accord == "true" else False if accord == "false" else None
            # 
            num_affaire = request.POST.get("num_affaire")
            try:
                num_affaire = int(num_affaire) if num_affaire else 0
            except ValueError:
                num_affaire = 0

            Intervention.objects.create(
                enfant=enfant,
                date_intervention=date_intervention,
                date_fait=date_fait,

                role_demandeur=request.POST.get("role_demandeur") or "",
                concerne=request.POST.get("concerne") or "",
                description_concerne=request.POST.get("description_concerne") or "",
                situation_juridique_concerne=request.POST.get("situation_juridique_concerne") or "",
                adresse_concerne=request.POST.get("adresse_concerne") or "",

                num_affaire=num_affaire,
                juridiction_competente=request.POST.get("juridiction_competente") or "",
                lieu_fait=request.POST.get("lieu_fait") or "",
                type_fait=request.POST.get("type_fait") or "",
                etat_procedure=request.POST.get("etat_procedure") or "",
                enfant_recidiviste=request.POST.get("enfant_recidiviste") or "",

                situation_actuelle_enfant=request.POST.get("situation_actuelle_enfant") or "غير محددة",
                description_situation_actuelle_enfant=request.POST.get("description_situation_actuelle_enfant") or "غير محددة",

                accord_reached=accord_reached,
                accord_date=accord_date,
                delegue=delegue_obj
            )

            messages.success(request, "تمّت إضافة الوساطة بنجاح")
            return redirect("intervention_list", enfant_id=enfant.id)

        except Delegate.DoesNotExist:
            messages.error(request, "المندوب المحدد غير موجود")
            return redirect(request.path)

        except Exception as e:
            print("Insertion error:", e)
            messages.error(request, "حدث خطأ أثناء إضافة الوساطة")
            return redirect(request.path)

    return render(request, "intervention/intervention_form.html", {
        "enfant": enfant,
        "total_interventions": total_interventions,
        "before_trial": before_trial,
        "during_trial": during_trial,
        "after_trial": after_trial,
        "total_recidive": total_recidive,
        "total_detention": total_detention,
        "total_free": total_free,
    })

from datetime import date
@login_required
def intervention_edit(request, id):
    intervention = get_object_or_404(Intervention, id=id)
    enfant = intervention.enfant

    if enfant.status != "DELINQUENT":
        messages.error(request, "لا يمكن تعديل تدخل لطفل مهدد فقط")
        return redirect("intervention_list", enfant_id=enfant.id)

    if request.method == "POST":
        try:
            date_intervention = safe_date(request.POST.get("date_intervention"))
            date_fait = safe_date(request.POST.get("date_fait"))
            accord_date = safe_date(request.POST.get("accord_date"))

            if not date_intervention:
                messages.error(request, "تاريخ التدخل إجباري")
                return redirect(request.path)

            if date_fait:
                if not enfant.birth_date:
                    messages.error(request, "تاريخ ميلاد الطفل غير محدد")
                    return redirect(request.path)

                age = calculate_age(enfant.birth_date, date_fait)

                if age > 18:
                    messages.error(request, "عمر الطفل أكبر من 18 سنة")
                    return redirect(request.path)

                if age <= 0:
                    messages.error(request, "تاريخ الفعلة غير صالح ( " + str(age) + " سنة )  مقارنة بتاريخ الميلاد")
                    return redirect(request.path)

            delegue_id = request.POST.get("delegue") or getattr(request.user, "delegate_profile", None)

            if not delegue_id:
                messages.error(request, "حقل المندوب إجباري")
                return redirect(request.path)

            try:
                delegue_obj = Delegate.objects.get(id=delegue_id)
            except Delegate.DoesNotExist:
                messages.error(request, "المندوب غير موجود")
                return redirect(request.path)

            accord = request.POST.get("accord_reached")
            accord_reached = True if accord == "true" else False if accord == "false" else None

            num_affaire = request.POST.get("num_affaire")
            try:
                num_affaire = int(num_affaire) if num_affaire else 0
            except ValueError:
                num_affaire = 0

            intervention.date_intervention = date_intervention
            intervention.date_fait = date_fait

            intervention.role_demandeur = request.POST.get("role_demandeur") or ""
            intervention.concerne = request.POST.get("concerne") or ""
            intervention.description_concerne = request.POST.get("description_concerne") or ""
            intervention.situation_juridique_concerne = request.POST.get("situation_juridique_concerne") or ""
            intervention.adresse_concerne = request.POST.get("adresse_concerne") or ""

            intervention.num_affaire = num_affaire
            intervention.juridiction_competente = request.POST.get("juridiction_competente") or ""
            intervention.lieu_fait = request.POST.get("lieu_fait") or ""
            intervention.type_fait = request.POST.get("type_fait") or ""
            intervention.etat_procedure = request.POST.get("etat_procedure") or ""
            intervention.enfant_recidiviste = request.POST.get("enfant_recidiviste") or ""

            intervention.situation_actuelle_enfant = request.POST.get("situation_actuelle_enfant") or "غير محددة"
            intervention.description_situation_actuelle_enfant = request.POST.get("description_situation_actuelle_enfant") or "غير محددة"

            intervention.accord_reached = accord_reached
            intervention.accord_date = accord_date

            intervention.delegue = delegue_obj

            intervention.save()

            messages.success(request, "تمّ تعديل التدخل بنجاح ")
            return redirect("intervention_list", enfant_id=enfant.id)

        except Exception as e:
            print("Edit error:", e)
            messages.error(request, "حدث خطأ أثناء التعديل")
            return redirect(request.path)

    return render(request, "intervention/intervention_form.html", {
        "intervention": intervention,
        "enfant": enfant
    })


@login_required
def intervention_delete(request, id):
    intervention = get_object_or_404(Intervention, id=id)
    enfant_id = intervention.enfant.id
    intervention.delete()
    return redirect("intervention_list", enfant_id=enfant_id)


# ==================== CHILD REGISTRATION ====================

@login_required
def enfant_list(request):
    search_query = request.GET.get('q', '')

    enfants = Child.objects.exclude(status="THREATENED")
    social_file = SocialFile.objects.all()

    if search_query:
        query = (
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query)
        )

        if search_query.isdigit():
            query |= Q(id=int(search_query))

        enfants = enfants.filter(query)

    total_enfants = enfants.count()
    total_male = enfants.filter(gender='M').count()
    total_female = enfants.filter(gender='F').count()
    total_not_specified = enfants.filter(gender__isnull=True).count()
    total_social_files = SocialFile.objects.count()

    return render(request, 'enfants/enfant_list.html', {
        'enfants': enfants,
        'social_file': social_file,
        'total_enfants': total_enfants,
        'total_male': total_male,
        'total_female': total_female,
        'total_not_specified': total_not_specified,
        'total_social_files': total_social_files,
    })



# ==================== CHILD REGISTRATION ====================

def child_registration(request):
    persons = ['الأم', 'الأب', 'العائلة الموسعة']
    zip_values = [
        ('accompany', 'اصطحاب'),
        ('temp_abandon', 'تخلي مؤقت'),
        ('final_abandon', 'تخلي نهائي'),
    ]

    uid_auto = get_next_uid()

    if request.method == 'POST':
        child_type = request.POST.get('child_type', 'menaced')

        if child_type == 'menaced':
            form = ChildForm(request.POST)
            if form.is_valid():
                child = form.save(commit=False)
                child.uid = uid_auto

                initial = {p: request.POST.get(f'initial_{p}') for p in persons if request.POST.get(f'initial_{p}')}
                child.initial_status_at_birth = initial

                if request.user.is_authenticated and hasattr(request.user, "delegate_profile"):
                    delegate = request.user.delegate_profile
                    child.delegate_ch = delegate
                    child.delegate_unique_id = delegate.unique_id
                    child.delegate_unique_number = delegate.delegate_code

                child.save()
                messages.success(request, "تم إضافة الطفل المهدد بنجاح")
                return redirect('enfant_list')

            else:
                messages.error(request, "الرجاء تصحيح الأخطاء في النموذج.")
                return render(request, 'account/child_registration.html', {
                    'form': form,
                    'persons': persons,
                    'zip_values': zip_values,
                    'uid_auto': uid_auto,
                    'WILAYAS': WILAYAS,
                    'DEPARTMENTS': Child.DEPARTMENTS,
                })

        elif child_type == 'delinquant':
            try:
                delegue_obj = None
                if request.user.is_authenticated and hasattr(request.user, 'delegate_profile'):
                    delegue_obj = request.user.delegate_profile
                else:
                    delegue_id = request.POST.get('delegue')
                    if delegue_id:
                        delegue_obj = get_object_or_404(Delegate, id=delegue_id)
                
                if not delegue_obj:
                    messages.error(request, "المندوب غير موجود أو المستخدم غير متصل")
                    return redirect(request.path)
                
                enfant = EnfantDelinquant(
                    nom=request.POST.get('nom', '').strip(),
                    prenom=request.POST.get('prenom', '').strip(),
                    sexe=request.POST.get('sexe', ''),
                    date_naissance=request.POST.get('date_naissance') or None,
                    num_extrait_naissance=request.POST.get('num_extrait_naissance', '').strip(),
                    delegue=delegue_obj,
                    wilaya=request.POST.get('wilaya', '')
                )
                
                if hasattr(enfant, 'uid'):
                    enfant.uid = uid_auto
                
                enfant.save()
                
                messages.success(request, "تم إضافة الطفل الجانح بنجاح")
                return redirect('enfant_list')
                
            except Exception as e:
                messages.error(request, f"خطأ في إضافة الطفل الجانح: {str(e)}")
                print(f"Error creating delinquent child: {e}")
                return redirect(request.path)

    else:
        form = ChildForm(initial={'uid': uid_auto})

    return render(request, 'account/child_registration.html', {
        'form': form,
        'persons': persons,
        'zip_values': zip_values,
        'uid_auto': uid_auto,
        'WILAYAS': WILAYAS,
        'DEPARTMENTS': Child.DEPARTMENTS,
    })


# ==================== DASHBOARD CENTRAL ====================

from datetime import datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect

@login_required
def central_enfants_juveniles(request):
    query = request.GET.get('q', '').strip()

    # ==================== 1. Enfants du modèle EnfantDelinquant ====================
    enfants_delinquant_model = EnfantDelinquant.objects.select_related('delegue').all()

    if query:
        filters = Q()
        filters |= Q(nom__icontains=query)
        filters |= Q(prenom__icontains=query)
        filters |= Q(uid__icontains=query)
        filters |= Q(num_extrait_naissance__icontains=query)

        try:
            if '/' in query:
                parts = query.split('/')
                if len(parts) == 3:
                    date_obj = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    filters |= Q(date_naissance=date_obj)
            elif '-' in query and len(query) == 10:
                date_obj = datetime.strptime(query, '%Y-%m-%d').date()
                filters |= Q(date_naissance=date_obj)
        except (ValueError, IndexError):
            pass

        if query.isdigit():
            filters |= Q(id=int(query))

        for code, name in WILAYAS:
            if query.lower() in name.lower():
                filters |= Q(delegue__wilaya=code)

        enfants_delinquant_model = enfants_delinquant_model.filter(filters)

    # ==================== 2. Enfants du modèle Child avec status='DELINQUENT' ====================
    enfants_child_model = Child.objects.filter(status='DELINQUENT').select_related('delegate_ch')

    if query:
        filters_child = Q()
        filters_child |= Q(first_name__icontains=query)
        filters_child |= Q(last_name__icontains=query)
        filters_child |= Q(uid__icontains=query)

        try:
            if '/' in query:
                parts = query.split('/')
                if len(parts) == 3:
                    date_obj = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    filters_child |= Q(birth_date=date_obj)
            elif '-' in query and len(query) == 10:
                date_obj = datetime.strptime(query, '%Y-%m-%d').date()
                filters_child |= Q(birth_date=date_obj)
        except (ValueError, IndexError):
            pass

        if query.isdigit():
            filters_child |= Q(id=int(query))

        for code, name in Child.TUNISIA_GOVERNORATES:
            if query.lower() in name.lower():
                filters_child |= Q(birth_governorate=code)

        enfants_child_model = enfants_child_model.filter(filters_child)

    # ==================== 3. Fusion des deux listes avec wrapper compatible template ====================
    class DelinquentWrapper:
        """Wrapper pour rendre un Child compatible avec les champs attendus par le template
        (nom, prenom, sexe, date_naissance, num_extrait_naissance, delegue, uid, id)."""
        pass

    combined = list(enfants_delinquant_model)

    for child in enfants_child_model:
        wrapper = DelinquentWrapper()
        wrapper.id = child.id
        wrapper.nom = child.last_name
        wrapper.prenom = child.first_name
        wrapper.sexe = child.gender
        wrapper.date_naissance = child.birth_date
        wrapper.num_extrait_naissance = child.uid
        wrapper.uid = child.uid
        wrapper.delegue = child.delegate_ch
        # Marqueur pour savoir de quel modèle vient l'objet (utile si besoin
        # d'adapter l'URL de suppression selon le type, voir note plus bas)
        wrapper.source_model = 'child'
        wrapper.date_creation = child.created_at
        combined.append(wrapper)

    # Tri combiné par date de création (du plus récent au plus ancien)
    combined.sort(
        key=lambda e: getattr(e, 'date_creation', None) or timezone.now(),
        reverse=True
    )

    paginator = Paginator(combined, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'query': query,
        'total_results': len(combined) if query else None,
        'total_children': len(combined),
        'WILAYAS': WILAYAS,
    }

    return render(request, 'central/central_enfants_juvéniles.html', context)


@login_required
def central_enfants_menaces(request):
    query = request.GET.get('q', '').strip()

    enfants = Child.objects.filter(
        status='THREATENED',
        nationality='TUN'
    ).select_related('delegate_ch').order_by('-created_at')

    if query:
        filters = Q()
        try:
            if '/' in query:
                parts = query.split('/')
                if len(parts) == 3:
                    date_obj = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    filters |= Q(birth_date=date_obj)
            elif '-' in query and len(query) == 10:
                date_obj = datetime.strptime(query, '%Y-%m-%d').date()
                filters |= Q(birth_date=date_obj)
        except (ValueError, IndexError):
            pass

        if query.isdigit():
            filters |= Q(id=int(query))
        filters |= Q(uid__icontains=query)
        filters |= Q(numero_dossier__icontains=query)
        filters |= Q(first_name__icontains=query)
        filters |= Q(last_name__icontains=query)

        for code, name in Child.TUNISIA_GOVERNORATES:
            if query.lower() in name.lower():
                filters |= Q(birth_governorate=code)

        enfants = enfants.filter(filters)

    paginator = Paginator(enfants, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'central/central_enfants_menaces.html', {
        'page_obj': page_obj,
        'query': query,
        'total_children': enfants.count(),
    })


@login_required
def central_enfants_etrangers(request):
    query = request.GET.get('q', '').strip()

    enfants = Child.objects.filter(
        nationality="FOREIGN"
    ).select_related('delegate_ch').order_by('-created_at')

    if query:
        filters = Q()
        filters |= Q(first_name__icontains=query)
        filters |= Q(last_name__icontains=query)
        filters |= Q(uid__icontains=query)
        
        pays_map = {
            'egypte': 'EG', 'مصر': 'EG',
            'libye': 'LY', 'ليبيا': 'LY',
            'algérie': 'DZ', 'الجزائر': 'DZ',
            'tunisie': 'TN', 'تونس': 'TN'
        }
        for key, code in pays_map.items():
            if key in query.lower():
                filters |= Q(foreign_country=code)
        
        
        
        if query.isdigit():
            filters |= Q(id=int(query))
        
        enfants = enfants.filter(filters)

    paginator = Paginator(enfants, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'central/central_enfants_etrangers.html', {
        'page_obj': page_obj,
        'query': query,
        'total_children': enfants.count(),
    })


@login_required
def central_enfants_hors_mariage(request):
    query = request.GET.get('q', '').strip()

    enfants = Child.objects.filter(
        birth_status="UNMARRIED"
    ).select_related('delegate_ch').order_by('-created_at')

    if query:
        filters = Q()
        filters |= Q(first_name__icontains=query)
        filters |= Q(last_name__icontains=query)
        filters |= Q(uid__icontains=query)
        
        if 'افتراضية' in query or 'virtuelle' in query.lower():
            filters |= Q(child_identity_type='VIRTUAL')
        elif 'بيولوجية' in query:
            filters |= Q(child_identity_type='BIOLOGICAL')
        
        if 'قاصر' in query:
            filters |= Q(mother_age_at_birth='MINOR')
        elif 'راشد' in query:
            filters |= Q(mother_age_at_birth='ADULT')
        
        try:
            if '/' in query:
                parts = query.split('/')
                if len(parts) == 3:
                    date_obj = datetime(int(parts[2]), int(parts[1]), int(parts[0])).date()
                    filters |= Q(birth_date=date_obj)
            elif '-' in query and len(query) == 10:
                date_obj = datetime.strptime(query, '%Y-%m-%d').date()
                filters |= Q(birth_date=date_obj)
        except (ValueError, IndexError):
            pass
        
        if query.isdigit():
            filters |= Q(id=int(query))
        
        enfants = enfants.filter(filters)

    paginator = Paginator(enfants, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'central/central_enfants_hors_mariage.html', {
        'page_obj': page_obj,
        'query': query,
        'total_children': enfants.count(),
    })


# ==================== FONCTIONS DE SUPPRESSION ====================

@login_required
def enfant_menace_delete(request, pk):
    enfant = get_object_or_404(Child, pk=pk, status='THREATENED')
    
    # ✅ Rôles autorisés à supprimer
    ROLES_AUTORISES = ['chef de bureau', 'central']
    
    # Vérification des droits
    if not request.user.is_superuser:
        if not hasattr(request.user, 'delegate_profile'):
            messages.error(request, "❌ Vous n'avez pas les droits pour supprimer cet enfant.")
            return redirect('central_enfants_menaces')
        
        if request.user.delegate_profile.role not in ROLES_AUTORISES:
            messages.error(
                request, 
                f"❌ Votre rôle '{request.user.delegate_profile.role}' n'est pas autorisé. "
                f"Rôles autorisés : {', '.join(ROLES_AUTORISES)}"
            )
            return redirect('central_enfants_menaces')
    
    if request.method == 'POST':
        nom_complet = f"{enfant.first_name} {enfant.last_name}"
        try:
            with transaction.atomic():
                # ✅ Supprimer d'abord les Investigation liées aux notifications
                # (sinon la suppression de NouveauNotification peut échouer
                # si la FK Investigation.notification n'est pas en CASCADE)
                Investigation.objects.filter(notification__child=enfant).delete()
                Investigation.objects.filter(child=enfant).delete()

                NouveauNotification.objects.filter(child=enfant).delete()
                ThreatAssessment.objects.filter(child=enfant).delete()
                MesureConvenue.objects.filter(child=enfant).delete()
                MesureUrgente.objects.filter(child=enfant).delete()
                SocialDossierEnfant.objects.filter(child=enfant).delete()
                TraffickingNotification.objects.filter(child=enfant).delete()
                Production.objects.filter(enfant=enfant).delete()
                ProductionRequest.objects.filter(enfant=enfant).delete()
                enfant.delete()

            messages.success(request, f"✅ تم حذف الطفل المهدد {nom_complet} بنجاح")

        except Exception as e:
            print("=" * 50)
            print("ERREUR enfant_menace_delete:", str(e))
            print(traceback.format_exc())
            print("=" * 50)
            messages.error(request, f"❌ خطأ في حذف الطفل: {str(e)}")

        return redirect('central_enfants_menaces')
    
    return render(request, 'central/confirm_delete_enfant_menaces.html', {
        'child': enfant
    })

@login_required
def enfant_juvenile_delete(request, pk):
    """
    Supprimer un enfant délinquant (Child avec status='DELINQUENT' ou EnfantDelinquant)
    """
    # ✅ Rôles autorisés : 'chef de bureau', 'central' ou superuser
    allowed_roles = ['chef de bureau', 'central']
    
    if not request.user.is_superuser:
        if not hasattr(request.user, 'delegate_profile'):
            messages.error(request, "❌ Vous n'avez pas les droits pour supprimer cet enfant.")
            return redirect('central_enfants_juveniles')
        
        if request.user.delegate_profile.role not in allowed_roles:
            messages.error(
                request,
                f"❌ Votre rôle '{request.user.delegate_profile.role}' ne permet pas de supprimer "
                f"des enfants. Rôles autorisés : {', '.join(allowed_roles)}"
            )
            return redirect('central_enfants_juveniles')
    
    # ===============================
    # 1. RECHERCHER L'ENFANT (Child avec status='DELINQUENT' OU EnfantDelinquant)
    # ===============================
    enfant = None
    is_child_model = False
    
    # Essayer de récupérer un Child avec status='DELINQUENT'
    enfant = Child.objects.filter(id=pk, status='DELINQUENT').first()
    if enfant:
        is_child_model = True
        child_ref = enfant
    else:
        # Essayer de récupérer un EnfantDelinquant
        enfant = EnfantDelinquant.objects.filter(id=pk).first()
        if enfant:
            is_child_model = False
            # Essayer de trouver le Child correspondant
            child_ref = Child.objects.filter(id=pk, status='DELINQUENT').first()
            if not child_ref and hasattr(enfant, 'uid'):
                child_ref = Child.objects.filter(uid=enfant.uid, status='DELINQUENT').first()
        else:
            messages.error(request, "❌ Enfant non trouvé")
            return redirect('central_enfants_juveniles')
    
    if request.method == 'POST':
        nom_complet = f"{enfant.first_name} {enfant.last_name}" if is_child_model else f"{enfant.nom} {enfant.prenom}"
        
        try:
            with transaction.atomic():
                # Si c'est un Child, supprimer ses données liées
                if is_child_model:
                    # Supprimer les données liées
                    Investigation.objects.filter(notification__child=enfant).delete()
                    Investigation.objects.filter(child=enfant).delete()
                    NouveauNotification.objects.filter(child=enfant).delete()
                    ThreatAssessment.objects.filter(child=enfant).delete()
                    MesureConvenue.objects.filter(child=enfant).delete()
                    MesureUrgente.objects.filter(child=enfant).delete()
                    SocialDossierEnfant.objects.filter(child=enfant).delete()
                    TraffickingNotification.objects.filter(child=enfant).delete()
                    Production.objects.filter(enfant=enfant).delete()
                    ProductionRequest.objects.filter(enfant=enfant).delete()
                    Intervention.objects.filter(enfant=enfant).delete()
                    
                    # Supprimer le SocialFile lié
                    SocialFile.objects.filter(enfant=enfant).delete()
                    
                    # Supprimer l'enfant
                    enfant.delete()
                
                else:
                    # C'est un EnfantDelinquant
                    # Supprimer le SocialFile lié
                    SocialFile.objects.filter(enfant=enfant.id).delete()
                    
                    # Si un Child correspondant existe, le supprimer aussi
                    if child_ref:
                        # Supprimer les données liées au Child
                        Investigation.objects.filter(notification__child=child_ref).delete()
                        Investigation.objects.filter(child=child_ref).delete()
                        NouveauNotification.objects.filter(child=child_ref).delete()
                        ThreatAssessment.objects.filter(child=child_ref).delete()
                        MesureConvenue.objects.filter(child=child_ref).delete()
                        MesureUrgente.objects.filter(child=child_ref).delete()
                        SocialDossierEnfant.objects.filter(child=child_ref).delete()
                        TraffickingNotification.objects.filter(child=child_ref).delete()
                        Production.objects.filter(enfant=child_ref).delete()
                        ProductionRequest.objects.filter(enfant=child_ref).delete()
                        Intervention.objects.filter(enfant=child_ref).delete()
                        
                        # Supprimer le Child
                        child_ref.delete()
                    
                    # Supprimer l'EnfantDelinquant
                    enfant.delete()

            messages.success(request, f'✅ تم حذف الطفل الجانح {nom_complet} بنجاح')

        except Exception as e:
            print("=" * 50)
            print("ERREUR enfant_juvenile_delete:", str(e))
            print(traceback.format_exc())
            print("=" * 50)
            messages.error(request, f'❌ خطأ في حذف الطفل: {str(e)}')

        return redirect('central_enfants_juveniles')
    
    # GET - Afficher la confirmation
    return render(request, 'central/confirm_delete_enfant_juvenile.html', {
        'child': enfant,
        'is_child_model': is_child_model,
    })


@login_required
def delete_enfant_etranger(request, pk):
    enfant = get_object_or_404(Child, pk=pk, nationality="FOREIGN")

    # ✅ Rôles autorisés : 'chef de bureau', 'central' ou superuser
    ROLES_AUTORISES = ['chef de bureau', 'central']
    
    if not request.user.is_superuser:
        if not hasattr(request.user, 'delegate_profile'):
            messages.error(request, "❌ Vous n'avez pas les droits pour supprimer cet enfant.")
            return redirect('central_enfants_etrangers')
        
        if request.user.delegate_profile.role not in ROLES_AUTORISES:
            messages.error(
                request, 
                f"❌ Votre rôle '{request.user.delegate_profile.role}' n'est pas autorisé. "
                f"Rôles autorisés : {', '.join(ROLES_AUTORISES)}"
            )
            return redirect('central_enfants_etrangers')

    if request.method == "POST":
        nom_complet = f"{enfant.first_name} {enfant.last_name}"
        
        try:
            with transaction.atomic():
                # ✅ Supprimer d'abord les Investigation liées (sinon la suppression
                # de NouveauNotification peut échouer si Investigation.notification
                # n'est pas en CASCADE)
                Investigation.objects.filter(notification__child=enfant).delete()
                Investigation.objects.filter(child=enfant).delete()

                # Supprimer toutes les autres données liées
                NouveauNotification.objects.filter(child=enfant).delete()
                ThreatAssessment.objects.filter(child=enfant).delete()
                MesureConvenue.objects.filter(child=enfant).delete()
                MesureUrgente.objects.filter(child=enfant).delete()
                SocialDossierEnfant.objects.filter(child=enfant).delete()
                TraffickingNotification.objects.filter(child=enfant).delete()
                Production.objects.filter(enfant=enfant).delete()
                ProductionRequest.objects.filter(enfant=enfant).delete()
                Intervention.objects.filter(enfant=enfant).delete()
                enfant.delete()

            messages.success(request, f"✅ تم حذف الطفل الأجنبي {nom_complet} بنجاح")

        except Exception as e:
            print("=" * 50)
            print("ERREUR delete_enfant_etranger:", str(e))
            print(traceback.format_exc())
            print("=" * 50)
            messages.error(request, f'❌ خطأ في حذف الطفل: {str(e)}')

        return redirect('central_enfants_etrangers')

    return render(request, 'central/confirm_delete_enfant_etrangers.html', {
        'enfant': enfant
    })


# ---------------------- CHILD SEARCH ----------------------
@login_required
def recherche_child_list_(request):
    children = Child.objects.all()
    uid_query = request.GET.get('uid', '')
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        if not children.exists():
            return render(request, 'account/child_list_institutions.html', {
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
            })
    return render(request, 'account/child_list_institutions.html', {'children': children, 'uid_query': uid_query})


@login_required
def recherche_investigation_list_(request):
    uid_query = request.GET.get('uid', '')
    
    children = Child.objects.all()
    
    if uid_query:
        children = children.filter(uid__icontains=uid_query)
        
        if not children.exists():
            return render(request, 'account/child_list_Investigation.html', {
                'show_error_modal': True,
                'error_message': "⚠️ الطفل غير موجود، الرجاء القيام بإدخال بياناته.",
                'uid_query': uid_query,
                'children_with_notifications': [],
            })
    
    children_with_notifications = []
    for child in children:
        notifications = list(NouveauNotification.objects.filter(child=child))
        children_with_notifications.append({
            'child': child,
            'notifications': notifications,
        })
    
    return render(request, 'account/child_list_Investigation.html', {
        'children_with_notifications': children_with_notifications,
        'uid_query': uid_query,
    })


# ==================== DETAILS ENFANT ====================

@login_required
def child_menaced_detail(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
   
    if hasattr(request.user, 'delegate_profile'):
        notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=request.user.delegate_profile
        ).order_by('-notification_date')
    else:
        notifications = NouveauNotification.objects.none()
    
    try:
        social_file = SocialDossierEnfant.objects.filter(child=child).select_related('notification').order_by('-created_at').first()
    except SocialDossierEnfant.DoesNotExist:
        social_file = None
    
    context = {
        'child': child,
        'notifications': notifications,
        'child_type': 'menaced',
        'social_file': social_file,
    }
    return render(request, 'account/child_detail.html', context)


@login_required
def enfant_delinquent_detail(request, enfant_id):

    # ============================================================
    # 1. PRIORITÉ AU MODÈLE Child
    # ============================================================

    child = Child.objects.filter(
        id=enfant_id,
        status='DELINQUENT'
    ).select_related(
        'delegate_ch'
    ).first()

    if child:

        # --------------------------------------------------------
        # Interventions liées directement au Child
        # --------------------------------------------------------

        interventions = (
            Intervention.objects
            .filter(enfant=child)
            .order_by('-date_intervention')
        )

        # --------------------------------------------------------
        # Fichier social
        # --------------------------------------------------------

        social_file = (
            SocialDossierEnfant.objects
            .filter(child=child)
            .order_by('-created_at')
            .first()
        )

        context = {
            'child': child,
            'child_type': 'delinquent',
            'interventions': interventions,
            'social_file': social_file,

            # Important pour le template
            'is_child_model': True,
            'child_id': child.id,
        }

        return render(
            request,
            'account/enfant_detail.html',
            context
        )

    # ============================================================
    # 2. COMPATIBILITÉ AVEC L'ANCIEN MODÈLE
    # ============================================================

    enfant = get_object_or_404(
        EnfantDelinquant,
        id=enfant_id
    )

    # ------------------------------------------------------------
    # Recherche éventuelle du Child correspondant
    # ------------------------------------------------------------

    if getattr(enfant, 'num_extrait_naissance', None):

        child_ref = (
            Child.objects
            .filter(
                uid=enfant.num_extrait_naissance
            )
            .first()
        )

    else:

        child_ref = None

    # ------------------------------------------------------------
    # Interventions
    # ------------------------------------------------------------

    if child_ref:

        interventions = (
            Intervention.objects
            .filter(enfant=child_ref)
            .order_by('-date_intervention')
        )

    else:

        interventions = []

    # ------------------------------------------------------------
    # Ancien fichier social
    # ------------------------------------------------------------

    try:

        social_file = SocialFile.objects.get(
            enfant=enfant.id
        )

    except SocialFile.DoesNotExist:

        social_file = None

    context = {
        'child': enfant,
        'child_type': 'delinquent',
        'interventions': interventions,
        'social_file': social_file,
        'is_child_model': False,
        'child_id': child_ref.id if child_ref else None,
    }

    return render(
        request,
        'account/enfant_detail.html',
        context
    )


@login_required
def download_social_file_pdf(request, child_id):
    from django.template.loader import get_template
    from weasyprint import HTML
    from datetime import datetime

    child = None
    child_type = None

    try:
        child = Child.objects.get(id=child_id)
        child_type = 'menaced'
    except Child.DoesNotExist:
        try:
            child = EnfantDelinquant.objects.get(id=child_id)
            child_type = 'delinquent'
        except EnfantDelinquant.DoesNotExist:
            messages.error(request, "❌ الطفل غير موجود")
            return redirect('index2')

    # Sécurité supplémentaire : si jamais child est resté None
    if child is None:
        messages.error(request, "❌ الطفل غير موجود")
        return redirect('index2')

    try:
        social_file = SocialDossierEnfant.objects.filter(child=child).order_by('-created_at').first()
    except Exception:
        social_file = None

    if not social_file:
        messages.error(request, "❌ لا يوجد ملف اجتماعي لهذا الطفل")
        if child_type == 'menaced':
            return redirect('child_menaced_detail', child_id=child_id)
        else:
            return redirect('enfant_delinquent_detail', enfant_id=child_id)

    context = {
        'child': child,
        'social_file': social_file,
        'child_type': child_type,
        'date_generation': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'request': request,
    }

    template = get_template('account/child_detail_pdf.html')
    html_content = template.render(context)

    pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    if child_type == 'menaced':
        nom_fichier = f"social_file_{child.first_name}_{child.last_name}.pdf"
    else:
        nom_fichier = f"social_file_{child.prenom}_{child.nom}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response

@login_required
def download_enfant_delinquent_pdf(request, enfant_id):
    from django.template.loader import get_template
    from weasyprint import HTML
    from datetime import datetime

    is_child_model = False
    try:
        child = Child.objects.get(id=enfant_id, status='DELINQUENT')
        is_child_model = True
    except Child.DoesNotExist:
        child = get_object_or_404(EnfantDelinquant, id=enfant_id)

    try:
        social_file = SocialFile.objects.get(enfant=child.id)
    except SocialFile.DoesNotExist:
        social_file = None

    context = {
        'child': child,
        'is_child_model': is_child_model,
        'social_file': social_file,
        'date_generation': datetime.now().strftime("%d/%m/%Y %H:%M"),
        'request': request,
    }

    template = get_template('account/enfant_detail_pdf.html')
    html_content = template.render(context)

    pdf_file = HTML(string=html_content, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    if is_child_model:
        nom_fichier = f"social_file_{child.first_name}_{child.last_name}.pdf"
    else:
        nom_fichier = f"social_file_{child.prenom}_{child.nom}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


@login_required
def child_detail(request, child_id):
    try:
        child = Child.objects.get(id=child_id)
        return redirect('child_menaced_detail', child_id=child_id)
    except Child.DoesNotExist:
        pass
    
    try:
        enfant = EnfantDelinquant.objects.get(id=child_id)
        return redirect('enfant_delinquent_detail', enfant_id=child_id)
    except EnfantDelinquant.DoesNotExist:
        raise Http404("Enfant non trouvé")


# ==================== ADMIN - GESTION DES DÉLÉGUÉS ====================

@login_required
@admin_required 
def admin_delegate_list(request):
    selected_wilaya = request.GET.get('wilaya')
    delegates = Delegate.objects.all().order_by('wilaya', 'first_name')
    
    if selected_wilaya:
        delegates = delegates.filter(wilaya=selected_wilaya)
    
    total_delegates = delegates.count()
    central_delegates = delegates.filter(role='central').count()
    regional_delegates = delegates.filter(role='regional').count()
    
    context = {
        'delegates': delegates,
        'selected_wilaya': selected_wilaya,
        'wilayas': WILAYAS,
        'roles': ROLES,
        'total_delegates': total_delegates,
        'central_delegates': central_delegates,
        'regional_delegates': regional_delegates,
    }
    return render(request, 'admin/delegate_list.html', context)


@login_required
@admin_required
def admin_delegate_edit(request, pk):
    delegate = get_object_or_404(Delegate, pk=pk)
    
    if request.method == 'GET':
        storage = get_messages(request)
        for _ in storage:
            pass
    
    if request.method == 'POST':
        old_wilaya = delegate.wilaya
        old_delegate_code = delegate.delegate_code
        
        delegate.first_name = request.POST.get('first_name')
        delegate.last_name = request.POST.get('last_name')
        new_wilaya = request.POST.get('wilaya')
        delegate.role = request.POST.get('role')
        
        phone = request.POST.get('phone', '')
        if phone:
            phone = re.sub(r'\D', '', phone)[:8]
        delegate.phone = phone
        
        delegate.email = request.POST.get('email')
        
        new_delegate_code = request.POST.get('delegate_code', '').strip()
        
        if not new_delegate_code:
            messages.error(request, "المعرف الوحيد مطلوب")
            return render(request, 'admin/delegate_edit.html', {
                'delegate': delegate,
                'wilayas': WILAYAS,
                'roles': ROLES
            })
        
        if not re.fullmatch(r"\d{10}", new_delegate_code):
            messages.error(request, "المعرف الوحيد يجب أن يحتوي على 10 أرقام بالضبط")
            return render(request, 'admin/delegate_edit.html', {
                'delegate': delegate,
                'wilayas': WILAYAS,
                'roles': ROLES
            })
        
        if new_delegate_code != old_delegate_code:
            if Delegate.objects.filter(delegate_code=new_delegate_code).exclude(pk=delegate.pk).exists():
                messages.error(request, "هذا المعرف الوحيد مستخدم بالفعل من قبل مندوب آخر")
                return render(request, 'admin/delegate_edit.html', {
                    'delegate': delegate,
                    'wilayas': WILAYAS,
                    'roles': ROLES
                })
            
            delegate.delegate_code = new_delegate_code
            delegate.user.username = new_delegate_code
            delegate.user.save()
        
        if new_wilaya != old_wilaya:
            delegate.wilaya = new_wilaya
            prefix = f"D{new_wilaya}_"
            existing_ids = Delegate.objects.filter(
                wilaya=new_wilaya,
                unique_id__startswith=prefix
            ).exclude(pk=delegate.pk).values_list('unique_id', flat=True)
            
            max_suffix = 0
            pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
            for uid in existing_ids:
                match = pattern.match(uid)
                if match:
                    num = int(match.group(1))
                    if num > max_suffix:
                        max_suffix = num
            
            delegate.unique_id = f"{prefix}{max_suffix + 1}"
        
        password = request.POST.get('password')
        if password and password.strip():
            delegate.user.set_password(password)
            delegate.user.save()
        
        delegate.save()
        
        messages.success(request, f"✅ تم تعديل بيانات المندوب {delegate.first_name} {delegate.last_name} بنجاح.")
        return redirect('admin_delegate_list')
    
    return render(request, 'admin/delegate_edit.html', {
        'delegate': delegate,
        'wilayas': WILAYAS,
        'roles': ROLES,
    })


@login_required
@admin_required
def admin_register_delegate(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        
        if form.is_valid():
            wilaya = form.cleaned_data["wilaya"]
            delegate_code = form.cleaned_data["delegate_code"]
            first_name = form.cleaned_data["first_name"]
            last_name = form.cleaned_data["last_name"]
            role = form.cleaned_data["role"]
            phone = form.cleaned_data["phone"]
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            if not delegate_code:
                messages.error(request, "المعرف الوحيد مطلوب")
                return redirect("admin_register_delegate")

            if not re.fullmatch(r"\d{10}", delegate_code):
                messages.error(request, "المعرف الوحيد يجب أن يحتوي على 10 أرقام بالضبط")
                return redirect("admin_register_delegate")

            if Delegate.objects.filter(delegate_code=delegate_code).exists():
                messages.error(request, "هذا المعرف الوحيد مستخدم بالفعل")
                return redirect("admin_register_delegate")

            if User.objects.filter(username=delegate_code).exists():
                messages.error(request, "هذا الحساب موجود بالفعل")
                return redirect("admin_register_delegate")

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=delegate_code,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        email=email or ""
                    )

                    delegate = Delegate.objects.create(
                        user=user,
                        delegate_code=delegate_code,
                        wilaya=wilaya,
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        phone=phone,
                        email=email
                    )

                    request.session['last_registered_delegate'] = delegate.id
                    request.session['generated_password'] = password

                    return redirect("admin_register_success")

            except Exception as e:
                messages.error(request, f"خطأ في إنشاء المندوب: {str(e)}")
                return redirect("admin_register_delegate")

    return render(request, "admin/admin_register_delegate.html")


@login_required
@admin_required
def admin_register_success(request):
    delegate_id = request.session.get('last_registered_delegate')
    generated_password = request.session.get('generated_password', '')
    
    delegate = None
    
    if delegate_id:
        try:
            delegate = Delegate.objects.get(id=delegate_id)
            del request.session['last_registered_delegate']
        except Delegate.DoesNotExist:
            pass
    
    if 'generated_password' in request.session:
        del request.session['generated_password']
    
    context = {
        'delegate': delegate,
        'generated_password': generated_password,
    }
    
    return render(request, 'admin/admin_register_success.html', context)


@login_required
@admin_required 
def admin_delegate_delete(request, pk):
    delegate = get_object_or_404(Delegate, pk=pk)
    
    if request.method == 'POST':
        nom_complet = f"{delegate.first_name} {delegate.last_name}"
        if delegate.user:
            delegate.user.delete()
        delegate.delete()
        messages.success(request, f'✅ تم حذف المندوب "{nom_complet}" بنجاح.')
        return redirect('admin_delegate_list')
    
    return render(request, 'admin/delegate_confirm_delete.html', {'delegate': delegate})


# ==================== ADMIN - GESTION DES ENFANTS ====================

@login_required
def admin_dashboard(request):
    """
    Dashboard Admin - Gestion des délégués uniquement
    avec répartition par wilaya et statistiques par rôle.
    """
    if not hasattr(request.user, 'delegate_profile') or request.user.delegate_profile.role not in ['chef de bureau', 'central']:
        messages.error(request, "❌ Vous n'avez pas les droits pour accéder à cette page.")
        return redirect('index2')

    from django.utils import timezone
    import json

    now = timezone.now()

    # === RÉCUPÉRATION DES DONNÉES DÉLÉGUÉS ===
    all_delegates = Delegate.objects.select_related('user').all()

    total_delegates = all_delegates.count()
    central_count = all_delegates.filter(role='central').count()
    regional_count = all_delegates.filter(role='regional').count()
    admin_count = all_delegates.filter(role='chef de bureau').count()

    # === RÉPARTITION PAR WILAYA ===
    delegates_by_wilaya = []

    # Initialiser toutes les 24 wilayas
    for code, name in WILAYAS:
        delegates_by_wilaya.append({
            'wilaya_code': code,
            'wilaya_name': name,
            'count': 0,
            'central': 0,
            'regional': 0,
            'admin': 0,
        })

    # Compter les délégués par wilaya et par rôle
    for delegate in all_delegates:
        for entry in delegates_by_wilaya:
            if entry['wilaya_code'] == delegate.wilaya:
                entry['count'] += 1
                if delegate.role == 'central':
                    entry['central'] += 1
                elif delegate.role == 'regional':
                    entry['regional'] += 1
                elif delegate.role == 'chef de bureau':
                    entry['admin'] += 1
                break

    # Trier par nombre de délégués (décroissant), wilayas vides à la fin
    delegates_by_wilaya = sorted(
        delegates_by_wilaya,
        key=lambda x: (-x['count'], x['wilaya_name'])
    )

    # Délégués récents (5 derniers inscrits)
    recent_delegates = all_delegates.order_by('-user__date_joined')[:5]

    context = {
        'total_delegates': total_delegates,
        'central_count': central_count,
        'regional_count': regional_count,
        'admin_count': admin_count,
        'recent_delegates': recent_delegates,
        'delegates_by_wilaya': json.dumps(delegates_by_wilaya, ensure_ascii=False),
    }

    return render(request, 'admin/admin_dashboard.html', context)


@login_required
@admin_required
def admin_child_edit(request, pk):
    child = get_object_or_404(Child, pk=pk)
    
    persons = ['الأم', 'الأب', 'العائلة الموسعة']
    zip_values = [
        ('accompany', 'اصطحاب'),
        ('temp_abandon', 'تخلي مؤقت'),
        ('final_abandon', 'تخلي نهائي'),
    ]
    
    initial_status = child.initial_status_at_birth or {}
    
    if request.method == "POST":
        form = ChildForm(request.POST, instance=child)
        
        if form.is_valid():
            child = form.save(commit=False)
            
            new_initial = {}
            for p in persons:
                value = request.POST.get(f'initial_{p}')
                if value:
                    new_initial[p] = value
            child.initial_status_at_birth = new_initial
            
            
            
            child.save()
            
            messages.success(request, f'✅ تم تعديل بيانات الطفل {child.first_name} {child.last_name} بنجاح')
            return redirect('admin_child_list')
    else:
        form = ChildForm(instance=child)
    
    return render(request, 'admin/child_edit.html', {
        'form': form,
        'child': child,
        'persons': persons,
        'zip_values': zip_values,
        'initial_status': initial_status,
        'DEPARTMENTS': Child.DEPARTMENTS,
    })


@login_required
@admin_required
def admin_child_delete(request, pk):
    child = get_object_or_404(Child, pk=pk)
    
    if request.method == 'POST':
        nom_complet = f"{child.first_name} {child.last_name}"
        NouveauNotification.objects.filter(child=child).delete()
        child.delete()
        messages.success(request, f'✅ L\'enfant "{nom_complet}" a été supprimé avec succès.')
        return redirect('admin_child_list')
    
    return render(request, 'admin/child_confirm_delete.html', {
        'child': child
    })


@login_required
@admin_required
def admin_child_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    wilaya_filter = request.GET.get('wilaya', '')
    
    children = Child.objects.select_related('delegate_ch').all().order_by('-created_at')
    
    if query:
        children = children.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(uid__icontains=query) |
            Q(numero_dossier__icontains=query)
        )
    
    if status_filter:
        children = children.filter(status=status_filter)
    
    if wilaya_filter:
        children = children.filter(birth_governorate=wilaya_filter)
    
    total_children = children.count()
    threatened_count = children.filter(status='THREATENED').count()
    delinquent_count = children.filter(status='DELINQUENT').count()
    
    paginator = Paginator(children, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'status_filter': status_filter,
        'wilaya_filter': wilaya_filter,
        'total_children': total_children,
        'threatened_count': threatened_count,
        'delinquent_count': delinquent_count,
        'status_choices': Child.STATUS_CHOICES,
        'wilayas': WILAYAS,
    }
    return render(request, 'admin/child_list.html', context)


# ==================== ECHARTS DASHBOARD ====================

@login_required
def echarts_dashboard(request):
    from collections import defaultdict
    from django.db.models import Count
    
    now = timezone.now()
    
    GOVERNORATE_ARABIC_NAMES = {
        "tunis": "تونس",
        "ariana": "أريانة",
        "ben_arous": "بن عروس",
        "manouba": "منوبة",
        "nabeul": "نابل",
        "zaghouan": "زغوان",
        "bizerte": "بنزرت",
        "beja": "باجة",
        "jendouba": "جندوبة",
        "kef": "الكاف",
        "siliana": "سليانة",
        "kairouan": "القيروان",
        "kasserine": "القصرين",
        "sidi_bouzid": "سيدي بوزيد",
        "sousse": "سوسة",
        "monastir": "المنستير",
        "mahdia": "المهدية",
        "sfax": "صفاقس",
        "gabes": "قابس",
        "medenine": "مدنين",
        "tataouine": "تطاوين",
        "tozeur": "توزر",
        "kebili": "قبلي",
        "gafsa": "قفصة",
    }
    
    enfants_menaces_qs = Child.objects.select_related('delegate_ch').all()
    enfants_delinquants_qs = EnfantDelinquant.objects.select_related('delegue').all()
    
    total_menaces = enfants_menaces_qs.count()
    total_delinquants = enfants_delinquants_qs.count()
    total_global = total_menaces + total_delinquants
    
    def safe_percentage(part, total):
        return round((part / total * 100), 1) if total > 0 else 0
    
    mois_arabe = {
        1: 'جانفي', 2: 'فيفري', 3: 'مارس', 4: 'أفريل',
        5: 'ماي', 6: 'جوان', 7: 'جويلية', 8: 'أوت',
        9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'
    }
    
    monthly_labels = []
    monthly_data_menaces = []
    monthly_data_delinquants = []
    
    for i in range(11, -1, -1):
        month_date = now - timedelta(days=i*30)
        year = month_date.year
        month = month_date.month
        monthly_labels.append(f"{mois_arabe[month]} {year}")
        monthly_data_menaces.append(
            enfants_menaces_qs.filter(
                created_at__year=year, created_at__month=month
            ).count()
        )
        monthly_data_delinquants.append(
            enfants_delinquants_qs.filter(
                date_creation__year=year, date_creation__month=month
            ).count()
        )
    
    wilaya_stats = defaultdict(int)
    menaces_by_wilaya = enfants_menaces_qs.exclude(birth_governorate__isnull=True).values('birth_governorate').annotate(total=Count('id'))
    for item in menaces_by_wilaya:
        wilaya_stats[item['birth_governorate']] += item['total']
    
    sorted_wilayas = sorted(wilaya_stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    wilaya_labels = []
    wilaya_data = []
    for code, count in sorted_wilayas:
        arabic_name = GOVERNORATE_ARABIC_NAMES.get(code, code)
        wilaya_labels.append(arabic_name)
        wilaya_data.append(count)
    
    today = now.date()
    age_groups = [('0-5', 0, 5), ('6-10', 6, 10), ('11-15', 11, 15), ('16-18', 16, 18)]
    age_labels = ['0-5 سنوات', '6-10 سنوات', '11-15 سنة', '16-18 سنة']
    age_data_menaces = []
    age_data_delinquants = []
    
    for _, min_age, max_age in age_groups:
        max_birth_date = today - timedelta(days=min_age*365)
        min_birth_date = today - timedelta(days=(max_age+1)*365)
        age_data_menaces.append(
            enfants_menaces_qs.filter(birth_date__gte=min_birth_date, birth_date__lte=max_birth_date).count()
        )
        age_data_delinquants.append(
            enfants_delinquants_qs.filter(date_naissance__gte=min_birth_date, date_naissance__lte=max_birth_date).count()
        )
    
    etrangers = enfants_menaces_qs.exclude(models.Q(nationality='TN') | models.Q(nationality__isnull=True)).count()
    unmarried = enfants_menaces_qs.filter(birth_status="UNMARRIED").count()
    irregular = enfants_menaces_qs.filter(nationality='FOREIGN').count()
    total_interventions = Intervention.objects.count()
    taux_reponse = safe_percentage(total_interventions, total_global)
    total_delegues = Delegate.objects.count()
    delegues_actifs = Delegate.objects.filter(user__is_active=True).count()
    taux_couverture = safe_percentage(delegues_actifs, total_delegues) if total_delegues > 0 else 0
    
    kpis = {
        "total_global": total_global,
        "total_menaces": total_menaces,
        "total_delinquants": total_delinquants,
        "menaces_pourcentage": safe_percentage(total_menaces, total_global),
        "delinquants_pourcentage": safe_percentage(total_delinquants, total_global),
        "etrangers": etrangers,
        "unmarried": unmarried,
        "irregular": irregular,
        "taux_reponse": taux_reponse,
        "taux_couverture": taux_couverture,
    }
    
    print("=== NOMS DES WILAYAS EN ARABE ===")
    for i, (label, data) in enumerate(zip(wilaya_labels, wilaya_data)):
        print(f"{label}: {data}")
    print("=================================")
    
    context = {
        'kpis': kpis,
        'monthly_labels': json.dumps(monthly_labels, ensure_ascii=False),
        'monthly_data_menaces': json.dumps(monthly_data_menaces),
        'monthly_data_delinquants': json.dumps(monthly_data_delinquants),
        'wilaya_labels': json.dumps(wilaya_labels, ensure_ascii=False),
        'wilaya_data': json.dumps(wilaya_data),
        'age_labels': json.dumps(age_labels, ensure_ascii=False),
        'age_data_menaces': json.dumps(age_data_menaces),
        'age_data_delinquants': json.dumps(age_data_delinquants),
        'total_delegues': total_delegues,
        'delegues_actifs': delegues_actifs,
        'current_date': now,
        'current_time': now.strftime("%H:%M"),
        'last_update': now.strftime("%d/%m/%Y %H:%M"),
    }
    
    return render(request, 'dashboard/echarts_dashboard.html', context)


def dashboard_powerbi(request):
    powerbi_url = "https://app.powerbi.com/view?r=VOTRE_VRAI_TOKEN_ICI"
    return render(request, "dashboard/powerbi_central.html", {
        "powerbi_url": powerbi_url
    })


# ==================== MESURES CONVENTIONNELLES ====================

@login_required
def mesure_convenue_list(request):
    from .models import MesureUrgente, ThreatAssessment
    
    current_user = request.user
    delegate_profile = None
    
    if hasattr(current_user, 'delegate_profile'):
        delegate_profile = current_user.delegate_profile
    elif hasattr(current_user, 'delegue_profile'):
        delegate_profile = current_user.delegue_profile
    
    if not delegate_profile:
        messages.warning(request, "⚠️ Vous n'avez pas les droits d'accès à cette page.")
        return redirect('index2')
    
    # ✅ CORRECTION : enfants créés par le délégué OU notifiés par le délégué
    from django.db.models import Q
    
    children_with_notifications = Child.objects.filter(
        Q(delegate_ch=delegate_profile) | 
        Q(notifications__created_by=delegate_profile),
        status="THREATENED"
    ).distinct()
    
    first_child = children_with_notifications.first()
    
    children_with_data = []
    selected_notif_id = request.GET.get('notif_id')
    open_child_id = request.GET.get('open_child')
    
    for child in children_with_notifications:
        # ✅ SEULEMENT les notifications créées par le délégué
        all_notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate_profile
        ).order_by('-notification_date')
        
        filtered_notifications = []
        for notif in all_notifications:
            try:
                threat_assessment = ThreatAssessment.objects.get(notification=notif)
                
                has_commitment = (
                    threat_assessment.decision_social_protection or
                    threat_assessment.decision_family_judge or
                    threat_assessment.decision_public_prosecutor or
                    threat_assessment.decision_violence_unit or
                    threat_assessment.decision_relevant_services or
                    threat_assessment.decision_trafficking_committee
                )
                
                if has_commitment:
                    notif.commitment_decisions = []
                    if threat_assessment.decision_social_protection:
                        notif.commitment_decisions.append('توفير الحماية الاجتماعية')
                    if threat_assessment.decision_family_judge:
                        notif.commitment_decisions.append('اعلام قاضي الأسرة')
                    if threat_assessment.decision_public_prosecutor:
                        notif.commitment_decisions.append('إعلام النيابة العمومية بوضعية الطفل')
                    if threat_assessment.decision_violence_unit:
                        notif.commitment_decisions.append('إحالة الوضعية على الوحدة المختصة بالبحث في جرائم العنف ضد المرأة والطفل')
                    if threat_assessment.decision_relevant_services:
                        notif.commitment_decisions.append('إعلام المصالح ذات الصلة بالوضعية')
                    if threat_assessment.decision_trafficking_committee:
                        notif.commitment_decisions.append('إعلام الهيئة الوطنية للإتجار')
                    
                    filtered_notifications.append(notif)
                    
            except ThreatAssessment.DoesNotExist:
                continue
        
        if filtered_notifications:
            mesures = MesureConvenue.objects.filter(child=child)
            
            if selected_notif_id:
                mesures = mesures.filter(notification_id=selected_notif_id)
            
            urgentes_count = MesureUrgente.objects.filter(child=child).count()
            
            for notif in filtered_notifications:
                notif.urgentes_count = MesureUrgente.objects.filter(notification=notif).count()
            
            children_with_data.append({
                'child': child,
                'notifications': filtered_notifications,
                'mesures': mesures,
                'mesures_count': mesures.count(),
                'urgentes_count': urgentes_count,
            })
    
    context = {
        'children_with_data': children_with_data,
        'selected_notif_id': selected_notif_id,
        'open_child_id': open_child_id,
        'child': first_child,
        'has_child': first_child is not None,
    }
    return render(request, 'mesures_convenues_prises/mesure_convenue_list.html', context)


@login_required
def mesure_convenue_create(request, child_id, notif_id):
    child = get_object_or_404(Child, id=child_id)
    notification = get_object_or_404(NouveauNotification, id=notif_id, child=child)
    
    existing_mesure = MesureConvenue.objects.filter(notification=notification).first()
    if existing_mesure:
        messages.warning(request, "⚠️ يوجد بالفعل تدبير اتفاقي لهذا الإشعار. يمكنك تعديله.")
        return redirect('mesure_convenue_edit', pk=existing_mesure.id)
    
    if request.method == 'POST':
        try:
            placement_type = request.POST.get('placement_type')
            placement_location = request.POST.get('placement_location')
            placement_location_danger = request.POST.get('placement_location_danger')
            
            has_type_or_location = bool(placement_type or placement_location)
            has_danger = bool(placement_location_danger)
            
            if has_type_or_location and has_danger:
                messages.error(request, "❌ الرجاء اختيار مكان الإيواء أو مكان الإيداع فقط، ليس كليهما")
                return render(request, 'mesures_convenues_prises/mesure_convenue.html', {
                    'child': child,
                    'notification': notification,
                })
            
            mesure = MesureConvenue(
                child=child,
                notification=notification,
                measure_date=request.POST.get('measure_date') or None,
                family_awareness_date=request.POST.get('family_awareness_date') or None,
                agreement_type=request.POST.get('agreement_type') or None,
                placement_type=placement_type or None,
                placement_location=placement_location or None,
                other_placement_location=request.POST.get('other_placement_location') or None,
                placement_location_danger=placement_location_danger or None,
                other_placement_location_danger=request.POST.get('other_placement_location_danger') or None,
            )
            mesure.save()
            
            messages.success(request, "✅ تم إضافة التدبير الاتفاقي بنجاح")
            return redirect('mesure_convenue_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ في إضافة التدبير الاتفاقي: {str(e)}")
    
    context = {
        'child': child,
        'notification': notification,
    }
    return render(request, 'mesures_convenues_prises/mesure_convenue.html', context)


@login_required
def mesure_convenue_edit(request, pk):
    mesure = get_object_or_404(MesureConvenue, id=pk)
    child = mesure.child
    notification = mesure.notification
    
    if request.method == 'POST':
        try:
            placement_type = request.POST.get('placement_type')
            placement_location = request.POST.get('placement_location')
            placement_location_danger = request.POST.get('placement_location_danger')
            
            has_type_or_location = bool(placement_type or placement_location)
            has_danger = bool(placement_location_danger)
            
            if has_type_or_location and has_danger:
                messages.error(request, "❌ الرجاء اختيار مكان الإيواء أو مكان الإيداع فقط، ليس كليهما")
                return render(request, 'mesures_convenues_prises/mesure_convenue.html', {
                    'mesure': mesure,
                    'child': child,
                    'notification': notification,
                })
            
            mesure.measure_date = request.POST.get('measure_date') or None
            mesure.family_awareness_date = request.POST.get('family_awareness_date') or None
            mesure.agreement_type = request.POST.get('agreement_type') or None
            mesure.placement_type = placement_type or None
            mesure.placement_location = placement_location or None
            mesure.other_placement_location = request.POST.get('other_placement_location') or None
            mesure.placement_location_danger = placement_location_danger or None
            mesure.other_placement_location_danger = request.POST.get('other_placement_location_danger') or None
            mesure.save()
            
            messages.success(request, "✅ تم تعديل التدبير الاتفاقي بنجاح")
            return redirect('mesure_convenue_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ في تعديل التدبير الاتفاقي: {str(e)}")
            return redirect('mesure_convenue_edit', pk=pk)
    
    context = {
        'mesure': mesure,
        'child': child,
        'notification': notification,
    }
    return render(request, 'mesures_convenues_prises/mesure_convenue.html', context)


@login_required
def mesure_convenue_delete(request, pk):
    mesure = get_object_or_404(MesureConvenue, id=pk)
    child_id = mesure.child.id
    
    if request.method == 'POST':
        mesure.delete()
        messages.success(request, "✅ تم حذف التدبير الاتفاقي بنجاح")
        return redirect('mesure_convenue_list')
    
    context = {
        'mesure': mesure,
        'child': mesure.child,
    }
    return render(request, 'mesures_convenues_prises/mesure_convenue_confirm_delete.html', context)


@login_required
def mesure_convenue_update_followup(request, pk):
    mesure = get_object_or_404(MesureConvenue, id=pk)
    if request.method == 'POST':
        follow_up_status = request.POST.get('follow_up_status')
        if follow_up_status:
            mesure.follow_up_status = follow_up_status
            mesure.save()
            messages.success(request, "✅ تم تحديث حالة المتابعة بنجاح")
    return redirect('mesure_convenue_list')


@login_required
@require_POST
def mesure_convenue_update_status_ajax(request, pk):
    try:
        mesure = get_object_or_404(MesureConvenue, id=pk)
        data = json.loads(request.body)
        new_status = data.get('follow_up_status')
        
        if new_status:
            mesure.follow_up_status = new_status
            mesure.save()
            return JsonResponse({'success': True, 'message': 'Statut mis à jour avec succès'})
        else:
            return JsonResponse({'success': False, 'error': 'Statut invalide'})
            
    except MesureConvenue.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mesure non trouvée'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ==================== MESURES URGENTES ====================
@login_required
def mesure_urgente_list_all(request):
    from django.db.models import Q
    
    delegate = request.user.delegate_profile
    
    # ✅ CORRECTION : enfants créés par le délégué OU notifiés par le délégué
    children_of_delegate = Child.objects.filter(
        Q(delegate_ch=delegate) | 
        Q(notifications__created_by=delegate),
        status="THREATENED"
    ).distinct()
    
    children_with_data = []
    
    for child in children_of_delegate:
        # ✅ SEULEMENT les notifications créées par le délégué
        all_notifications = NouveauNotification.objects.filter(
            child=child,
            created_by=delegate
        ).order_by('-notification_date')
        
        filtered_notifications = []
        total_neglect_count = 0
        total_danger_count = 0
        
        for notif in all_notifications:
            threats = notif.threats or {}
            
            has_organized_crime = False
            organized_crime_keys = [
                'organized_crime', 'organized_crime_exploitation', 'child_exploitation_organized_crime',
                'border_crossing_smuggling', 'smuggling_goods', 'incitement_violence',
                'extremism_hatred', 'online_violence', 'drug_trafficking',
                'theft_pickpocketing', 'alcohol_trafficking', 'public_property_damage',
                'organized_begging', 'armed_conflict', 'trafficking_abroad',
                'child_adoption_exploitation', 'child_selling', 'organ_trafficking', 'other_crime'
            ]
            
            for key in organized_crime_keys:
                if key in threats and threats.get(key):
                    has_organized_crime = True
                    break
            
            if not has_organized_crime:
                for key, value in threats.items():
                    key_lower = key.lower()
                    if ('crime' in key_lower or 'exploitation' in key_lower or 'organized' in key_lower) and value:
                        has_organized_crime = True
                        break
            
            has_neglect = False
            neglect_keys = ['neglect', 'child_neglect', 'neglect_exploitation']
            
            for key in neglect_keys:
                if key in threats and threats.get(key):
                    has_neglect = True
                    break
            
            if not has_neglect:
                for key, value in threats.items():
                    if 'neglect' in key.lower() and value:
                        has_neglect = True
                        break
            
            if has_organized_crime or has_neglect:
                mesures_neglect = []
                mesures_danger = []
                
                for mesure in notif.mesures_urgentes.all():
                    if hasattr(mesure, 'menace_type'):
                        if mesure.menace_type == 'neglect':
                            mesures_neglect.append(mesure)
                        elif mesure.menace_type == 'danger':
                            mesures_danger.append(mesure)
                        else:
                            mesures_neglect.append(mesure)
                            mesures_danger.append(mesure)
                    else:
                        if mesure.urgent_measure_neglect_date or mesure.court_permission_date or mesure.placement_location:
                            mesures_neglect.append(mesure)
                        if mesure.urgent_measure_danger_date or mesure.approval_date or mesure.placement_location_danger:
                            mesures_danger.append(mesure)
                
                total_neglect_count += len(mesures_neglect)
                total_danger_count += len(mesures_danger)
                
                filtered_notifications.append({
                    'notif': notif,
                    'mesures_neglect': mesures_neglect,
                    'mesures_danger': mesures_danger,
                    'has_neglect': has_neglect,
                    'has_danger': has_organized_crime,
                })
        
        if filtered_notifications:
            mesures_count = total_neglect_count + total_danger_count
            
            children_with_data.append({
                'child': child,
                'notifications': filtered_notifications,
                'mesures_count': mesures_count,
                'neglect_count': total_neglect_count,
                'danger_count': total_danger_count,
            })
    
    return render(request, 'mesures_urgentes/mesure_urgente_list.html', {'children_with_data': children_with_data})


@login_required
def mesure_urgente_list(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
    # ✅ Vérifier que le délégué a le droit d'accéder à cet enfant
    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile
        
        from django.db.models import Q
        
        # Vérifier si l'enfant est visible par le délégué
        is_visible = Child.objects.filter(
            Q(delegate_ch=delegate) | 
            Q(notifications__created_by=delegate),
            id=child_id,
            status="THREATENED"
        ).exists()
        
        if not is_visible:
            messages.error(request, "❌ Vous n'avez pas accès à ce dossier")
            return redirect('mesure_urgente_list_all')
    else:
        messages.error(request, "❌ Vous n'êtes pas authentifié")
        return redirect('index2')
    
    # ✅ SEULEMENT les notifications créées par le délégué
    all_notifications = NouveauNotification.objects.filter(
        child=child,
        created_by=delegate
    ).order_by('-notification_date')
    
    notifications = []
    
    for notif in all_notifications:
        threats = notif.threats or {}
        
        has_organized_crime = False
        organized_crime_keys = [
            'organized_crime', 'organized_crime_exploitation', 'border_crossing_smuggling',
            'smuggling_goods', 'incitement_violence', 'extremism_hatred', 'online_violence',
            'drug_trafficking', 'theft_pickpocketing', 'alcohol_trafficking', 'public_property_damage',
            'organized_begging', 'armed_conflict', 'trafficking_abroad', 'child_adoption_exploitation',
            'child_selling', 'organ_trafficking', 'other_crime'
        ]
        
        for key in organized_crime_keys:
            if key in threats and threats.get(key):
                has_organized_crime = True
                break
        
        if not has_organized_crime:
            for key, value in threats.items():
                key_lower = key.lower()
                if ('crime' in key_lower or 'exploitation' in key_lower) and value:
                    has_organized_crime = True
                    break
        
        has_neglect = False
        if 'neglect' in threats and threats.get('neglect'):
            has_neglect = True
        elif 'child_neglect' in threats and threats.get('child_neglect'):
            has_neglect = True
        else:
            for key, value in threats.items():
                if 'neglect' in key.lower() and value:
                    has_neglect = True
                    break
        
        if has_organized_crime or has_neglect:
            mesures_neglect = []
            mesures_danger = []
            
            for mesure in notif.mesures_urgentes.all():
                if hasattr(mesure, 'menace_type'):
                    if mesure.menace_type == 'neglect':
                        mesures_neglect.append(mesure)
                    elif mesure.menace_type == 'danger':
                        mesures_danger.append(mesure)
                    else:
                        mesures_neglect.append(mesure)
                        mesures_danger.append(mesure)
                else:
                    if mesure.urgent_measure_neglect_date or mesure.court_permission_date or mesure.placement_location:
                        mesures_neglect.append(mesure)
                    if mesure.urgent_measure_danger_date or mesure.approval_date or mesure.placement_location_danger:
                        mesures_danger.append(mesure)
            
            notifications.append({
                'notif': notif,
                'mesures_neglect': mesures_neglect,
                'mesures_danger': mesures_danger,
                'has_neglect': has_neglect,
                'has_danger': has_organized_crime,
            })
    
    if not notifications:
        messages.info(request, f"ℹ️ الطفل {child.first_name} {child.last_name} n'a aucun إشعار contenant 'استغلال الطفل في الإجرام المنظم' ou 'تعريض الطفل للإهمال والتشرد'")
    
    context = {
        'child': child,
        'notifications': notifications,
    }
    return render(request, 'mesures_urgentes/mesure_urgente_list.html', context)


@login_required
def mesure_urgente_create(request, child_id, notif_id):
    child = get_object_or_404(Child, id=child_id)
    
    if child.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à ce dossier")
        return redirect('mesure_urgente_list')  # ✅ Changé vers 'mesure_urgente_list'
    
    notification = get_object_or_404(NouveauNotification, id=notif_id, child=child)
    threats = notification.threats or {}
    
    requested_type = request.GET.get('type', 'mixed')
    
    has_organized_crime = False
    for key, value in threats.items():
        key_lower = key.lower()
        if ('crime' in key_lower or 'exploitation' in key_lower) and value:
            has_organized_crime = True
            break
    
    has_neglect = 'neglect' in threats and threats.get('neglect')
    if not has_neglect:
        for key, value in threats.items():
            if 'neglect' in key.lower() and value:
                has_neglect = True
                break
    
    if requested_type == 'neglect' and not has_neglect:
        messages.error(request, "⚠️ Ce notification ne contient pas 'تعريض الطفل للإهمال والتشرد'")
        return redirect('mesure_urgente_list')
    
    if requested_type == 'danger' and not has_organized_crime:
        messages.error(request, "⚠️ Ce notification ne contient pas 'استغلال الطفل في الإجرام المنظم'")
        return redirect('mesure_urgente_list')
    
    if requested_type == 'neglect':
        form_type = 'neglect'
    elif requested_type == 'danger':
        form_type = 'danger'
    else:
        form_type = 'mixed'
    
    existing_count = MesureUrgente.objects.filter(notification=notification).count()
    next_order = existing_count + 1
    
    if request.method == 'POST':
        try:
            judge_action = request.POST.get('judge_action')
            if judge_action == 'yes':
                judge_informed = True
                judge_approval = True
            else:
                judge_informed = False
                judge_approval = False
            
            police_assistance = request.POST.get('police_assistance') == 'on'
            menace_type = request.POST.get('menace_type', form_type)
            
            mesure = MesureUrgente.objects.create(
                child=child,
                notification=notification,
                order=next_order,
                urgent_measure_neglect_date=request.POST.get('urgent_measure_neglect_date') or None,
                court_permission_date=request.POST.get('court_permission_date') or None,
                placement_location=request.POST.get('placement_location') or None,
                placement_location_other=request.POST.get('placement_location_other') or None,
                urgent_measure_danger_date=request.POST.get('urgent_measure_danger_date') or None,
                approval_date=request.POST.get('approval_date') or None,
                placement_location_danger=request.POST.get('placement_location_danger') or None,
                placement_location_danger_other=request.POST.get('placement_location_danger_other') or None,
                judge_informed=judge_informed,
                judge_approval=judge_approval,
                police_assistance=police_assistance,
                menace_type=menace_type,
            )
            
           
            # ✅ Redirection vers la liste générale
            return redirect('mesure_urgente_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ: {str(e)}")
            print(f"Erreur création mesure urgente: {e}")
    
    context = {
        'child': child,
        'notification': notification,
        'next_order': next_order,
        'existing_count': existing_count,
        'form_type': form_type,
        'has_neglect': has_neglect,
        'has_danger': has_organized_crime,
    }
    
    return render(request, 'mesures_urgentes/mesure_urgente_form.html', context)


@login_required
def mesure_urgente_edit(request, pk):
    mesure = get_object_or_404(MesureUrgente, id=pk)
    
    if mesure.child.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à ce dossier")
        return redirect('mesure_urgente_list')
    
    if request.method == 'POST':
        try:
            judge_action = request.POST.get('judge_action')
            if judge_action == 'yes':
                mesure.judge_informed = True
                mesure.judge_approval = True
            else:
                mesure.judge_informed = False
                mesure.judge_approval = False
            
            mesure.police_assistance = request.POST.get('police_assistance') == 'on'
            
            mesure.urgent_measure_neglect_date = request.POST.get('urgent_measure_neglect_date') or None
            mesure.court_permission_date = request.POST.get('court_permission_date') or None
            mesure.placement_location = request.POST.get('placement_location') or None
            mesure.placement_location_other = request.POST.get('placement_location_other') or None
            mesure.urgent_measure_danger_date = request.POST.get('urgent_measure_danger_date') or None
            mesure.approval_date = request.POST.get('approval_date') or None
            mesure.placement_location_danger = request.POST.get('placement_location_danger') or None
            mesure.placement_location_danger_other = request.POST.get('placement_location_danger_other') or None
            
            mesure.save()
            
            
            return redirect('mesure_urgente_list')
        except Exception as e:
            messages.error(request, f"❌ خطأ: {str(e)}")
    
    if hasattr(mesure, 'menace_type'):
        form_type = mesure.menace_type
    else:
        form_type = 'mixed'
    
    context = {
        'mesure': mesure,
        'child': mesure.child,
        'notification': mesure.notification,
        'form_type': form_type,
    }
    
    return render(request, 'mesures_urgentes/mesure_urgente_form.html', context)


@login_required
def mesure_urgente_delete(request, pk):
    mesure = get_object_or_404(MesureUrgente, id=pk)
    
    if mesure.child.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à ce dossier")
        return redirect('mesure_urgente_list')
    
    child_id = mesure.child.id
    notification = mesure.notification
    order_deleted = mesure.order
    
    if request.method == 'POST':
        mesure.delete()
        
        remaining = MesureUrgente.objects.filter(notification=notification).order_by('order')
        for new_order, m in enumerate(remaining, 1):
            m.order = new_order
            m.save()
        
        
        return redirect('mesure_urgente_list')
    
    return render(request, 'mesures_urgentes/mesure_urgente_confirm_delete.html', {'mesure': mesure})

# ==================== NOTIFICATIONS DE TRAITE ====================

@login_required
def trafficking_notification_list(request):
    children_with_trafficking = ThreatAssessment.objects.filter(
        decision_trafficking_committee=True
    ).values_list('child_id', flat=True).distinct()
    
    all_notifications = TraffickingNotification.objects.filter(
        delegate_ch=request.user.delegate_profile,
        child_id__in=children_with_trafficking
    ).select_related('child', 'threat_assessment').order_by('-notification_date')
    
    search_query = request.GET.get('q', '').strip()
    if search_query:
        all_notifications = all_notifications.filter(
            Q(child__first_name__icontains=search_query) |
            Q(child__last_name__icontains=search_query) |
            Q(child__uid__icontains=search_query)
        )
    
    for notification in all_notifications:
        notification.is_completed = notification.has_complete_information()
    
    per_page = request.GET.get('per_page', 10)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10
    
    paginator = Paginator(all_notifications, per_page)
    page = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    first_child = None
    if all_notifications.exists():
        first_notification = all_notifications.first()
        if first_notification and first_notification.child:
            first_child = first_notification.child
    
    return render(request, 'trafficking/trafficking_notification_list.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'per_page': per_page,
        'search_query': search_query,
        'unique_children_count': all_notifications.values('child').distinct().count(),
        'child': first_child,  
        'has_child': first_child is not None,  
    })


@login_required
def trafficking_notification_create(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    
    if child.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à ce dossier")
        return redirect('child_list_institutions')
    
    if request.method == 'POST':
        try:
            entry_method_regular = request.POST.get('entry_method_regular') == 'on'
            entry_method_irregular = request.POST.get('entry_method_irregular') == 'on'
            
            notification = TraffickingNotification.objects.create(
                child=child,
                delegate_ch=request.user.delegate_profile,
                notifier_number=request.POST.get('notifier_number', ''),
                entry_method_regular=entry_method_regular,
                entry_method_irregular=entry_method_irregular,
                entry_irregular_sea=request.POST.get('entry_irregular_sea') == 'on' if entry_method_irregular else False,
                entry_irregular_land=request.POST.get('entry_irregular_land') == 'on' if entry_method_irregular else False,
                exploitation_location_abroad=request.POST.get('exploitation_location_abroad') == 'on',
                exploitation_location_tunisia=request.POST.get('exploitation_location_tunisia') == 'on',
                exploitation_governorate=request.POST.get('exploitation_governorate'),
                exploitation_home=request.POST.get('exploitation_home') == 'on',
                exploitation_relatives_home=request.POST.get('exploitation_relatives_home') == 'on',
                exploitation_other_residence=request.POST.get('exploitation_other_residence') == 'on',
                exploitation_employer_home=request.POST.get('exploitation_employer_home') == 'on',
                exploitation_legal_workshop=request.POST.get('exploitation_legal_workshop') == 'on',
                exploitation_illegal_workshop=request.POST.get('exploitation_illegal_workshop') == 'on',
                exploitation_private_place=request.POST.get('exploitation_private_place') == 'on',
                exploitation_fields=request.POST.get('exploitation_fields') == 'on',
                exploitation_factories=request.POST.get('exploitation_factories') == 'on',
                exploitation_street=request.POST.get('exploitation_street') == 'on',
                exploitation_markets=request.POST.get('exploitation_markets') == 'on',
                exploitation_public_places=request.POST.get('exploitation_public_places') == 'on',
                exploitation_other=request.POST.get('exploitation_other') == 'on',
                exploitation_other_text=request.POST.get('exploitation_other_text'),
                exploiter_parents=request.POST.get('exploiter_parents') == 'on',
                exploiter_father=request.POST.get('exploiter_father') == 'on',
                exploiter_mother=request.POST.get('exploiter_mother') == 'on',
                exploiter_guardian=request.POST.get('exploiter_guardian') == 'on',
                exploiter_relative=request.POST.get('exploiter_relative') == 'on',
                exploiter_outside_family=request.POST.get('exploiter_outside_family') == 'on',
                exploiter_unknown=request.POST.get('exploiter_unknown') == 'on',
                exploiter_employer=request.POST.get('exploiter_employer') == 'on',
                exploiter_other=request.POST.get('exploiter_other') == 'on',
                exploiter_other_text=request.POST.get('exploiter_other_text'),
                exploitation_sexual=request.POST.get('exploitation_sexual') == 'on',
                exploitation_labor=request.POST.get('exploitation_labor') == 'on',
                exploitation_begging=request.POST.get('exploitation_begging') == 'on',
                exploitation_forced_marriage=request.POST.get('exploitation_forced_marriage') == 'on',
                exploitation_organ_trafficking=request.POST.get('exploitation_organ_trafficking') == 'on',
                exploitation_drug_trafficking=request.POST.get('exploitation_drug_trafficking') == 'on',
                exploitation_armed_conflict=request.POST.get('exploitation_armed_conflict') == 'on',
                crime_recruitment=request.POST.get('crime_recruitment') == 'on',
                crime_enlistment=request.POST.get('crime_enlistment') == 'on',
                crime_transport=request.POST.get('crime_transport') == 'on',
                crime_relocation=request.POST.get('crime_relocation') == 'on',
                crime_diversion=request.POST.get('crime_diversion') == 'on',
                crime_deportation=request.POST.get('crime_deportation') == 'on',
                crime_reception=request.POST.get('crime_reception') == 'on',
            )
            
            messages.success(request, f"✅ تم إضافة إشعار الاتجار للطفل {child.first_name} بنجاح")
            return redirect('trafficking_notification_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ: {str(e)}")
    
    gouvernorats = [
        'تونس', 'أريانة', 'بن عروس', 'منوبة', 'نابل', 'زغوان', 'بنزرت', 'باجة',
        'جندوبة', 'الكاف', 'سليانة', 'سوسة', 'المنستير', 'المهدية', 'صفاقس',
        'القيروان', 'القصرين', 'سيدي بوزيد', 'قابس', 'مدنين', 'تطاوين', 'قفصة', 'توزر'
    ]
    
    return render(request, 'trafficking/trafficking_notification_form.html', {
        'child': child,
        'gouvernorats': gouvernorats,
    })


@login_required
def trafficking_notification_edit(request, pk):
    notification = get_object_or_404(TraffickingNotification, id=pk)
    
    if notification.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à cette notification")
        return redirect('trafficking_notification_list')
    
    if request.method == 'POST':
        try:
            entry_method_regular = request.POST.get('entry_method_regular') == 'on'
            entry_method_irregular = request.POST.get('entry_method_irregular') == 'on'
            
            notification.entry_method_regular = entry_method_regular
            notification.entry_method_irregular = entry_method_irregular
            notification.entry_irregular_sea = request.POST.get('entry_irregular_sea') == 'on' if entry_method_irregular else False
            notification.entry_irregular_land = request.POST.get('entry_irregular_land') == 'on' if entry_method_irregular else False
            notification.exploitation_location_abroad = request.POST.get('exploitation_location_abroad') == 'on'
            notification.exploitation_location_tunisia = request.POST.get('exploitation_location_tunisia') == 'on'
            notification.exploitation_governorate = request.POST.get('exploitation_governorate')
            notification.exploitation_home = request.POST.get('exploitation_home') == 'on'
            notification.exploitation_relatives_home = request.POST.get('exploitation_relatives_home') == 'on'
            notification.exploitation_other_residence = request.POST.get('exploitation_other_residence') == 'on'
            notification.exploitation_employer_home = request.POST.get('exploitation_employer_home') == 'on'
            notification.exploitation_legal_workshop = request.POST.get('exploitation_legal_workshop') == 'on'
            notification.exploitation_illegal_workshop = request.POST.get('exploitation_illegal_workshop') == 'on'
            notification.exploitation_private_place = request.POST.get('exploitation_private_place') == 'on'
            notification.exploitation_fields = request.POST.get('exploitation_fields') == 'on'
            notification.exploitation_factories = request.POST.get('exploitation_factories') == 'on'
            notification.exploitation_street = request.POST.get('exploitation_street') == 'on'
            notification.exploitation_markets = request.POST.get('exploitation_markets') == 'on'
            notification.exploitation_public_places = request.POST.get('exploitation_public_places') == 'on'
            notification.exploitation_other = request.POST.get('exploitation_other') == 'on'
            notification.exploitation_other_text = request.POST.get('exploitation_other_text')
            notification.exploiter_parents = request.POST.get('exploiter_parents') == 'on'
            notification.exploiter_father = request.POST.get('exploiter_father') == 'on'
            notification.exploiter_mother = request.POST.get('exploiter_mother') == 'on'
            notification.exploiter_guardian = request.POST.get('exploiter_guardian') == 'on'
            notification.exploiter_relative = request.POST.get('exploiter_relative') == 'on'
            notification.exploiter_outside_family = request.POST.get('exploiter_outside_family') == 'on'
            notification.exploiter_unknown = request.POST.get('exploiter_unknown') == 'on'
            notification.exploiter_employer = request.POST.get('exploiter_employer') == 'on'
            notification.exploiter_other = request.POST.get('exploiter_other') == 'on'
            notification.exploiter_other_text = request.POST.get('exploiter_other_text')
            notification.exploitation_sexual = request.POST.get('exploitation_sexual') == 'on'
            notification.exploitation_labor = request.POST.get('exploitation_labor') == 'on'
            notification.exploitation_begging = request.POST.get('exploitation_begging') == 'on'
            notification.exploitation_forced_marriage = request.POST.get('exploitation_forced_marriage') == 'on'
            notification.exploitation_organ_trafficking = request.POST.get('exploitation_organ_trafficking') == 'on'
            notification.exploitation_drug_trafficking = request.POST.get('exploitation_drug_trafficking') == 'on'
            notification.exploitation_armed_conflict = request.POST.get('exploitation_armed_conflict') == 'on'
            notification.crime_recruitment = request.POST.get('crime_recruitment') == 'on'
            notification.crime_enlistment = request.POST.get('crime_enlistment') == 'on'
            notification.crime_transport = request.POST.get('crime_transport') == 'on'
            notification.crime_relocation = request.POST.get('crime_relocation') == 'on'
            notification.crime_diversion = request.POST.get('crime_diversion') == 'on'
            notification.crime_deportation = request.POST.get('crime_deportation') == 'on'
            notification.crime_reception = request.POST.get('crime_reception') == 'on'
            
            notification.save()
            
            messages.success(request, "✅ تم تعديل الإشعار بنجاح")
            return redirect('trafficking_notification_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ: {str(e)}")
    
    gouvernorats = [
        'تونس', 'أريانة', 'بن عروس', 'منوبة', 'نابل', 'زغوان', 'بنزرت', 'باجة',
        'جندوبة', 'الكاف', 'سليانة', 'سوسة', 'المنستير', 'المهدية', 'صفاقس',
        'القيروان', 'القصرين', 'سيدي بوزيد', 'قابس', 'مدنين', 'تطاوين', 'قفصة', 'توزر'
    ]
    
    return render(request, 'trafficking/trafficking_notification_form.html', {
        'notification': notification,
        'child': notification.child,
        'gouvernorats': gouvernorats,
        'is_edit': True
    })


@login_required
def trafficking_notification_detail(request, pk):
    notification = get_object_or_404(TraffickingNotification, id=pk)
    
    if notification.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à cette notification")
        return redirect('trafficking_notification_list')
    
    return render(request, 'trafficking/trafficking_notification_detail.html', {
        'notification': notification
    })


@login_required
def trafficking_notification_delete(request, pk):
    notification = get_object_or_404(TraffickingNotification, id=pk)
    
    if notification.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à cette notification")
        return redirect('trafficking_notification_list')
    
    child_name = f"{notification.child.first_name} {notification.child.last_name}"
    
    if request.method == 'POST':
        notification.delete()
        messages.success(request, f"✅ تم حذف إشعار الاتجار للطفل {child_name} بنجاح")
        return redirect('trafficking_notification_list')
    
    return render(request, 'trafficking/trafficking_notification_confirm_delete.html', {
        'notification': notification
    })


@login_required
def trafficking_notification_complete(request, notification_id):
    notification = get_object_or_404(TraffickingNotification, id=notification_id)
    
    if notification.delegate_ch != request.user.delegate_profile:
        messages.error(request, "❌ Vous n'avez pas accès à cette notification")
        return redirect('trafficking_notification_list')
    
    if request.method == 'POST':
        try:
            entry_method_regular = request.POST.get('entry_method_regular') == 'on'
            entry_method_irregular = request.POST.get('entry_method_irregular') == 'on'
            
            notification.entry_method_regular = entry_method_regular
            notification.entry_method_irregular = entry_method_irregular
            notification.entry_irregular_sea = request.POST.get('entry_irregular_sea') == 'on' if entry_method_irregular else False
            notification.entry_irregular_land = request.POST.get('entry_irregular_land') == 'on' if entry_method_irregular else False
            notification.exploitation_location_abroad = request.POST.get('exploitation_location_abroad') == 'on'
            notification.exploitation_location_tunisia = request.POST.get('exploitation_location_tunisia') == 'on'
            notification.exploitation_governorate = request.POST.get('exploitation_governorate')
            notification.exploitation_home = request.POST.get('exploitation_home') == 'on'
            notification.exploitation_relatives_home = request.POST.get('exploitation_relatives_home') == 'on'
            notification.exploitation_other_residence = request.POST.get('exploitation_other_residence') == 'on'
            notification.exploitation_employer_home = request.POST.get('exploitation_employer_home') == 'on'
            notification.exploitation_legal_workshop = request.POST.get('exploitation_legal_workshop') == 'on'
            notification.exploitation_illegal_workshop = request.POST.get('exploitation_illegal_workshop') == 'on'
            notification.exploitation_private_place = request.POST.get('exploitation_private_place') == 'on'
            notification.exploitation_fields = request.POST.get('exploitation_fields') == 'on'
            notification.exploitation_factories = request.POST.get('exploitation_factories') == 'on'
            notification.exploitation_street = request.POST.get('exploitation_street') == 'on'
            notification.exploitation_markets = request.POST.get('exploitation_markets') == 'on'
            notification.exploitation_public_places = request.POST.get('exploitation_public_places') == 'on'
            notification.exploitation_other = request.POST.get('exploitation_other') == 'on'
            notification.exploitation_other_text = request.POST.get('exploitation_other_text')
            notification.exploiter_parents = request.POST.get('exploiter_parents') == 'on'
            notification.exploiter_father = request.POST.get('exploiter_father') == 'on'
            notification.exploiter_mother = request.POST.get('exploiter_mother') == 'on'
            notification.exploiter_guardian = request.POST.get('exploiter_guardian') == 'on'
            notification.exploiter_relative = request.POST.get('exploiter_relative') == 'on'
            notification.exploiter_outside_family = request.POST.get('exploiter_outside_family') == 'on'
            notification.exploiter_unknown = request.POST.get('exploiter_unknown') == 'on'
            notification.exploiter_employer = request.POST.get('exploiter_employer') == 'on'
            notification.exploiter_other = request.POST.get('exploiter_other') == 'on'
            notification.exploiter_other_text = request.POST.get('exploiter_other_text')
            notification.exploitation_sexual = request.POST.get('exploitation_sexual') == 'on'
            notification.exploitation_labor = request.POST.get('exploitation_labor') == 'on'
            notification.exploitation_begging = request.POST.get('exploitation_begging') == 'on'
            notification.exploitation_forced_marriage = request.POST.get('exploitation_forced_marriage') == 'on'
            notification.exploitation_organ_trafficking = request.POST.get('exploitation_organ_trafficking') == 'on'
            notification.exploitation_drug_trafficking = request.POST.get('exploitation_drug_trafficking') == 'on'
            notification.exploitation_armed_conflict = request.POST.get('exploitation_armed_conflict') == 'on'
            notification.crime_recruitment = request.POST.get('crime_recruitment') == 'on'
            notification.crime_enlistment = request.POST.get('crime_enlistment') == 'on'
            notification.crime_transport = request.POST.get('crime_transport') == 'on'
            notification.crime_relocation = request.POST.get('crime_relocation') == 'on'
            notification.crime_diversion = request.POST.get('crime_diversion') == 'on'
            notification.crime_deportation = request.POST.get('crime_deportation') == 'on'
            notification.crime_reception = request.POST.get('crime_reception') == 'on'
            
            notification.save()
            
            messages.success(request, "✅ تم إكمال معلومات الإشعار بنجاح")
            return redirect('trafficking_notification_list')
            
        except Exception as e:
            messages.error(request, f"❌ خطأ: {str(e)}")
    
    gouvernorats = [
        'تونس', 'أريانة', 'بن عروس', 'منوبة', 'نابل', 'زغوان', 'بنزرت', 'باجة',
        'جندوبة', 'الكاف', 'سليانة', 'سوسة', 'المنستير', 'المهدية', 'صفاقس',
        'القيروان', 'القصرين', 'سيدي بوزيد', 'قابس', 'مدنين', 'تطاوين', 'قفصة', 'توزر'
    ]
    
    return render(request, 'trafficking/trafficking_notification_form.html', {
        'notification': notification,
        'child': notification.child,
        'gouvernorats': gouvernorats,
        'is_completion': True
    })


# ==================== PRODUCTION JUDICIAL ====================

@login_required
def production_judicial_create(request, enfant_id, notification_id):
    enfant = get_object_or_404(Child, id=enfant_id)
    notification = get_object_or_404(NouveauNotification, id=notification_id)
    
    if request.method == "POST":
        delegue_id = request.POST.get("delegue")
        delegue_obj = None

        if delegue_id:
            try:
                delegue_obj = Delegate.objects.get(id=delegue_id)
            except Delegate.DoesNotExist:
                messages.error(request, "المندوب غير موجود")
                return redirect(request.path)
        
        Production.objects.create(
            enfant=enfant,
            notification=notification,
            delegue=delegue_obj,
            date_mesure_temporaire=request.POST.get("date_mesure_temporaire") or None,
            date_affectation=request.POST.get("date_affectation") or None,
            date_resultats_recherche=request.POST.get("date_resultats_recherche") or None,
            date_estimation_situation=request.POST.get("date_estimation_situation") or None,
            date_session_judiciaire=request.POST.get("date_session_judiciaire") or None,
            date_accord_protection=request.POST.get("date_accord_protection") or None,
            date_refus_protection=request.POST.get("date_refus_protection") or None,
            date_execution_decision=request.POST.get("date_execution_decision") or None,
            date_cloture=request.POST.get("date_cloture") or None,
            date_transfert_juge=request.POST.get("date_transfert_juge") or None,
            lieu_hebergement=request.POST.getlist("lieu_hebergement"),
            procedure_recherche=request.POST.getlist("procedure_recherche"),
            decision_judge=request.POST.getlist("decision_judge"),
            moyens_autorises=request.POST.getlist("moyens_autorises"),
            lieu_depot=request.POST.getlist("lieu_depot"),
            suivi_situation_enfant=request.POST.getlist("suivi_situation_enfant"),
            evaluation_situation_enfant=request.POST.getlist("evaluation_situation_enfant"),
            resultat_suivi=request.POST.getlist("resultat_suivi"),
            decision_protection_judge=request.POST.getlist("decision_protection_judge"),
            non_execution_decision=request.POST.getlist("non_execution_decision"),
            accord_protection=True if request.POST.get("accord_protection") == "oui"
            else False if request.POST.get("accord_protection") == "non"
            else None,
        )

        messages.success(request, "تم إنشاء الملف القضائي بنجاح")
        return redirect("production_list_notification")

    return render(request, "production/protection_judicial_form.html", {"enfant": enfant, "notification": notification})


@login_required
def production_request_create(request, enfant_id):
    enfant = get_object_or_404(Child, id=enfant_id)

    if request.method == "POST":
        ProductionRequest.objects.create(
            enfant=enfant,
            date_demande=request.POST.get("date_demande"),
            mesures=request.POST.getlist("mesures"),
            delegue_id=request.POST.get("delegue") or None
        )

        messages.success(request, "تم إنشاء مطلب الحماية بنجاح")
        return redirect("production_request_list", enfant_id=enfant.id)

    return render(request, "production/protection_request_form.html", {
        "enfant": enfant,
        "production_request": None
    })


@login_required
def production_list_notification_production(request):

    notifications = (
        NouveauNotification.objects
        .select_related('child', 'threat_assessment')
        .filter(
            threat_assessment__decision_family_referral=True
        )
        .order_by('-notif_at')
    )

    print(f"Notifications: {notifications.count()}")

    return render(
        request,
        'production/list_notifications_production.html',
        {
            'notifications': notifications
        }
    )


@login_required
def production_judicial(request, enfant_id, notification_id):
    enfant = get_object_or_404(Child, id=enfant_id)
    notification = get_object_or_404(NouveauNotification, id=notification_id)

    try:
        production = Production.objects.get(
            enfant=enfant,
            notification=notification
        )
        is_update = True
    except Production.DoesNotExist:
        production = None
        is_update = False

    if request.method == "POST":
        delegue_id = request.POST.get("delegue")
        delegue_obj = None
        if delegue_id:
            try:
                delegue_obj = Delegate.objects.get(id=delegue_id)
            except Delegate.DoesNotExist:
                messages.error(request, "المندوب غير موجود")
                return redirect(request.path)
        
        if production is None:
            production = Production(
                enfant=enfant,
                notification=notification
            )
            is_update = False
        
        # Mise à jour des champs
        production.date_mesure_temporaire = request.POST.get("date_mesure_temporaire") or None
        production.date_affectation = request.POST.get("date_affectation") or None
        production.date_resultats_recherche = request.POST.get("date_resultats_recherche") or None
        production.date_estimation_situation = request.POST.get("date_estimation_situation") or None
        production.date_session_judiciaire = request.POST.get("date_session_judiciaire") or None
        production.date_accord_protection = request.POST.get("date_accord_protection") or None
        production.date_refus_protection = request.POST.get("date_refus_protection") or None
        production.date_execution_decision = request.POST.get("date_execution_decision") or None
        production.date_cloture = request.POST.get("date_cloture") or None
        production.date_transfert_juge = request.POST.get("date_transfert_juge") or None
        
        # Champs de type liste (ManyToMany ou ArrayField)
        production.lieu_hebergement = request.POST.getlist("lieu_hebergement")
        production.procedure_recherche = request.POST.getlist("procedure_recherche")
        production.decision_judge = request.POST.getlist("decision_judge")
        production.moyens_autorises = request.POST.getlist("moyens_autorises")
        production.lieu_depot = request.POST.getlist("lieu_depot")
        production.suivi_situation_enfant = request.POST.getlist("suivi_situation_enfant")
        production.evaluation_situation_enfant = request.POST.getlist("evaluation_situation_enfant")
        production.resultat_suivi = request.POST.getlist("resultat_suivi")
        production.decision_protection_judge = request.POST.getlist("decision_protection_judge")
        production.non_execution_decision = request.POST.getlist("non_execution_decision")
        
        # Accord protection (boolean)
        accord = request.POST.get("accord_protection")
        if accord == "True":
            production.accord_protection = True
        elif accord == "False":
            production.accord_protection = False
        else:
            production.accord_protection = None
        
        production.delegue = delegue_obj
        production.save()

        messages.success(
            request,
            "تم التحديث بنجاح" if is_update else "تم الإنشاء بنجاح"
        )

        #  REDIRECTION vers la liste des notifications
        return redirect("production_list_notification")

    return render(request, "production/protection_judicial_form.html", {
        "enfant": enfant,
        "notification": notification,
        "production_judicial": production,
        "is_update": is_update,
    })


# ==================== PRODUCTION ====================

@login_required
def production(request):
    return render(request, 'production/production.html')


@login_required
def production_request(request, enfant_id):

    enfant = get_object_or_404(Child, id=enfant_id)

    if request.method == "POST":

        date_demande = request.POST.get("date_demande")
        mesures_list = request.POST.getlist("mesures")
        delegue_id = request.POST.get("delegue")

        delegue_obj = None
        if delegue_id:
            delegue_obj = Delegate.objects.filter(id=delegue_id).first()

        production_request = ProductionRequest.objects.create(
            enfant=enfant,
            date_demande=date_demande or timezone.now().date(),
            mesures=mesures_list or [],
            delegue=delegue_obj
        )

        messages.success(request, "تم إنشاء مطلب الحماية بنجاح")

        return redirect("production_request_list", enfant_id=enfant.id)

    return render(request, "production/protection_request_form.html", {
        "enfant": enfant,
        "production_request": None
        })


@login_required
def production_request_list(request, enfant_id):

    enfant = get_object_or_404(Child, id=enfant_id)

    demandes = ProductionRequest.objects.filter(
        enfant=enfant,
        delegue__user=request.user
    ).order_by('-id')

    return render(request, "production/production_request_list.html", {
        "enfant": enfant,
        "demandes": demandes
    })


@login_required
def production_request_edit(request, pk):

    production_request = get_object_or_404(ProductionRequest, id=pk)

    if request.method == "POST":
        production_request.date_demande = request.POST.get("date_demande")
        production_request.mesures = request.POST.getlist("mesures")
        production_request.save()

        messages.success(request, "تم التعديل بنجاح")

        return redirect("production_request_list", enfant_id=production_request.enfant.id)

    return render(request, "production/protection_request_form.html", {
        "enfant": production_request.enfant,
        "production_request": production_request
    })

@login_required
def resultat_production_request(request, pk):

    production_request = get_object_or_404(ProductionRequest, pk=pk)
    enfant = production_request.enfant 
    resultat, created = ResultatProductionRequest.objects.get_or_create(
        production_request=production_request
    )

    if request.method == "POST":

        resultat.delegue = production_request.delegue

        accord = request.POST.get("accord_protection")
        resultat.accord_protection = True if accord == "True" else False if accord == "False" else None

        resultat.date_accord_protection = request.POST.get("date_accord_protection") or None
        resultat.date_refus_protection = request.POST.get("date_refus_protection") or None

        resultat.decision_protection_judge = request.POST.getlist("decision_protection_judge")

        resultat.date_execution_decision = request.POST.get("date_execution_decision") or None

        resultat.non_execution_decision = request.POST.getlist("non_execution_decision")

        resultat.save()

        messages.success(request, "تم تسجيل مآل مطلب الحماية")

        return redirect("production_request_list", enfant_id=production_request.enfant.id)

    return render(request, "production/resultat_production_request_form.html", {
        "pr": production_request,
        "resultat": resultat, "enfant": enfant
    })



@login_required
def all_production_requests(request):
    from collections import defaultdict
    
    production_requests = ProductionRequest.objects.filter(
        delegue=request.user.delegate_profile
    ).select_related('enfant').order_by('-date_demande')
    
    enfants_groupes = defaultdict(list)
    for demande in production_requests:
        enfants_groupes[demande.enfant.id].append(demande)
    
    total_demandes = production_requests.count()
    total_enfants = len(enfants_groupes)
    
    context = {
        'enfants_groupes': dict(enfants_groupes),
        'total_demandes': total_demandes,
        'total_enfants': total_enfants,
        'production_requests': production_requests,
    }
    return render(request, 'production/all_production_requests.html', context)





from .models import Child, SuiviEnfant
from .forms import SuiviEnfantForm

from django.contrib.auth.decorators import login_required
from django.db.models import Q

@login_required
def liste_enfants_suivi(request):
    enfants = Child.objects.none()

    # Vérifier que l'utilisateur connecté est un mandoub
    if hasattr(request.user, 'delegate_profile'):
        delegate = request.user.delegate_profile

        # Afficher uniquement :
        # 1. les enfants affectés directement à ce mandoub
        # 2. OU les enfants ayant des notifications créées par ce mandoub
        # 3. ET uniquement les enfants menacés
        enfants = Child.objects.filter(
            Q(delegate_ch=delegate) |
            Q(notifications__created_by=delegate),
            status="THREATENED"
        ).distinct().order_by('-created_at')

    context = {
        'enfants': enfants,
        'total_enfants': enfants.count(),
    }

    return render(
        request,
        "account/liste_enfants_suivi.html",
        context
    )



def ajouter_suivi(request, child_id):

    child = get_object_or_404(Child, id=child_id)

    if request.method == 'POST':

        form = SuiviEnfantForm(request.POST)

        if form.is_valid():

            suivi = form.save(commit=False)

            suivi.child = child

            # ==========================
            # CALCUL NOMBRE ENTRETIENS
            # ==========================

            suivi.nb_entretiens = (
                suivi.avec_enfant +
                suivi.avec_mere +
                suivi.avec_pere +
                suivi.avec_famille_etendue +
                suivi.avec_tuteur_legal +
                suivi.avec_membre_famille +
                suivi.avec_cadre_medical +
                suivi.avec_cadre_educatif
            )

            # ==========================
            # CALCUL NOMBRE APPELS
            # ==========================

            suivi.nb_appels = (
                suivi.appel_enfant +
                suivi.appel_mere +
                suivi.appel_pere +
                suivi.appel_famille_etendue +
                suivi.appel_tuteur_legal +
                suivi.appel_membre_famille +
                suivi.appel_cadre_medical +
                suivi.appel_cadre_educatif
            )

            suivi.save()

            print("SUIVI SAUVE :", suivi.id)

            return redirect(
                'resume_suivi',
                child_id=child.id,
                suivi_id=suivi.id
            )

        else:

            print("ERREURS FORMULAIRE :", form.errors)

    else:

        form = SuiviEnfantForm()

    return render(
        request,
        'account/ajouter_suivi.html',
        {
            'form': form,
            'child': child,
        }
    )


    

def resume_suivi(request, child_id, suivi_id):

    child = get_object_or_404(
        Child,
        id=child_id
    )

    suivi = get_object_or_404(
        SuiviEnfant,
        id=suivi_id,
        child=child
    )

    return render(
        request,
        'account/resume_suivi.html',
        {
            'child': child,
            'suivi': suivi,
        }
    )