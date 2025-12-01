from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import LoginForm
from .models import Delegate
import re
from django.db import transaction

# ---------------------- PAGE D'ACCUEIL ----------------------
def index(request):
    return render(request, 'index1.html')


# ---------------------- LOGIN ----------------------
def login(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            password = form.cleaned_data["password"]

            # Authenticate via username=email
            user = authenticate(request, username=email, password=password)
            if user is not None:
                auth_login(request, user)
                try:
                    delegate = user.delegate_profile
                    role = delegate.role
                except Delegate.DoesNotExist:
                    role = None
                if role == "central":
                    return redirect("tableauboard")
                else:
                    return redirect("index2")
            else:
                form.add_error(None, "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    else:
        form = LoginForm()
    return render(request, "account/login.html", {"form": form})


# ---------------------- LOGOUT ----------------------
def View_logout(request):
    auth_logout(request)
    return redirect("login")


# ---------------------- UNIQUE ID AUTO ----------------------
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


# ---------------------- REGISTER DELEGATE ----------------------
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

    return render(request, "account/register_delegate.html")

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


# ---------------------- SUCCESS PAGE ----------------------
def register_success(request):
    return render(request, 'account/login.html')


# ---------------------- DASHBOARD ----------------------
def other_dashboard(request):
    return render(request, 'account/index2.html')


def child_threatened(request):
    return render(request, 'account/child_threatened.html')


def child_delinquent(request):
    return render(request, 'account/child_delinquent.html')


def investigation(request):
    return render(request, 'account/investigation.html')


def trafficking(request):
    return render(request, 'account/trafficking.html')

def home_tableauboard(request):
  

    return render(request, 'dashboard/admin_dashboard.html')