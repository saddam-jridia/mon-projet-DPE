from django.db import models
from django.contrib.auth.models import User
import random

# Liste des wilayas
WILAYAS = [
    ("01", "تونس"),
    ("02", "أريانة"),
    ("03", "بن عروس"),
    ("04", "منوبة"),
    ("05", "نابل"),
    ("06", "زغوان"),
    ("07", "بنزرت"),
    ("08", "جندوبة"),
    ("09", "الكاف"),
    ("10", "سليانة"),
    ("11", "القيروان"),
    ("12", "القصرين"),
    ("13", "سيدي بوزيد"),
    ("14", "سوسة"),
    ("15", "المنستير"),
    ("16", "المهدية"),
    ("17", "صفاقس"),
    ("18", "قابس"),
    ("19", "مدنين"),
    ("20", "تطاوين"),
    ("21", "قبلي"),
    ("22", "توزر"),
    ("23", "القصرين"),
    ("24", "سليانة"),
]

# Liste des rôles
ROLES = [
    ("central", "مندوب مركزي"),
    ("regional", "مندوب جهوي"),
    ("assistant", "مندوب حماية طفولة مساعد"),
    ("assistant_first", "مندوب حماية الطفولة رتبة أولى"),
    ("regional_second", "مندوب حماية الطفولة رتبة ثانية"),
    ("regional_third", "مندوب حماية الطفولة رتبة ثالثة"),
    ("social_specialist", "أخصائي اجتماعي"),
    ("psychologist", "أخصائي نفسي"),
    ("administrator", "إطار إداري"),
    ("administrative_assistant", "عون إداري"),
    ("other", "أخرى"),
]

# Fonction pour générer unique_number
def generate_unique_number():
    """
    Génère un unique_number de 16 caractères : 'D13_' + 12 chiffres
    Exemple : D13_123456789012
    """
    return "D13_" + str(random.randint(100000000000, 999999999999))

class Delegate(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="delegate_profile"
    )
    wilaya = models.CharField(max_length=2, choices=WILAYAS)
    unique_id = models.CharField(max_length=15, unique=True)
    unique_number = models.CharField(max_length=12, unique=True, default="000000000000")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=ROLES)
    phone = models.CharField(max_length=20, blank=True)
    email = models.CharField("البريد الإلكتروني", max_length=150, null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.unique_id}"

