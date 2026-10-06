from django.db import models
from django.db import transaction
from django.core.validators import RegexValidator
from django.utils.text import slugify
from django.contrib.auth.models import User
import re
import random
from django.utils import timezone
from django_countries.fields import CountryField
from django.db.models import Max




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
    ("23", "قفصة"),
    ("24", "باجة"),
]

ROLES = [
    ("central", "مندوب عام"),
    ("regional", " مندوب حماية الطفولة"),
    ("chef de bureau", " Admin"),
]



def generate_unique_number():
    return "D13_" + str(random.randint(100000000000, 999999999999))


class Delegate(models.Model):
    wilaya = models.CharField(max_length=2, choices=WILAYAS, verbose_name="الولاية")
    unique_id = models.CharField(max_length=20, unique=True, blank=True)  
    delegate_code = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="المعرف الوحيد")  # 10 chiffres saisis
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    role = models.CharField(max_length=100, choices=ROLES, verbose_name="الدور")
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField("البريد الإلكتروني", max_length=150, blank=True, null=True)

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="delegate_profile",
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):
        if not self.unique_id:
            prefix = f"D{self.wilaya}_"
            with transaction.atomic():
                existing_ids = Delegate.objects.filter(
                    wilaya=self.wilaya,
                    unique_id__startswith=prefix
                ).values_list('unique_id', flat=True)

                max_suffix = 0
                pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
                for uid in existing_ids:
                    match = pattern.match(uid)
                    if match:
                        num = int(match.group(1))
                        if num > max_suffix:
                            max_suffix = num

                self.unique_id = f"{prefix}{max_suffix + 1}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.unique_id})"



class Child(models.Model):
    GENDER_CHOICES = [('M','ذكر'),('F','أنثى')]

    BIRTH_PLACE_CHOICES = [
    ('IN_COUNTRY', 'داخل تراب الجمهورية'),
    ('ABROAD', 'خارج البلاد'),
    ]
    TUNISIA_GOVERNORATES = [
    ("tunis", "تونس"),
    ("ariana", "أريانة"),
    ("ben_arous", "بن عروس"),
    ("manouba", "منوبة"),
    ("nabeul", "نابل"),
    ("zaghouan", "زغوان"),
    ("bizerte", "بنزرت"),
    ("beja", "باجة"),
    ("jendouba", "جندوبة"),
    ("kef", "الكاف"),
    ("siliana", "سليانة"),
    ("kairouan", "القيروان"),
    ("kasserine", "القصرين"),
    ("sidi_bouzid", "سيدي بوزيد"),
    ("sousse", "سوسة"),
    ("monastir", "المنستير"),
    ("mahdia", "المهدية"),
    ("sfax", "صفاقس"),
    ("gabes", "قابس"),
    ("medenine", "مدنين"),
    ("tataouine", "تطاوين"),
    ("tozeur", "توزر"),
    ("kebili", "قبلي"),
    ("gafsa", "قفصة"),
]
    DEPARTMENTS = {
    "tunis": [
        "باب البحر", "باب السويقة", "التحرير", "المرسى", "المنزه", "باردو",
        "العمران", "العمران الأعلى", "الزهور", "السيجومي", "الحرايرية",
        "الجبل الأحمر", "جبل الجلود", "الكبارية", "حي الخضراء", "المدينة"
    ],

    "ariana": [
        "أريانة المدينة", "سيدي ثابت", "رواد", "قلعة الأندلس",
        "سكرة", "حي التضامن", "المنيهلة"
    ],

    "ben_arous": [
        "بن عروس", "حمام الأنف", "حمام الشط", "المدنية", "المروج",
        "بومهل", "الزهراء", "رادس", "مقرين"
    ],

    "manouba": [
        "وادي الليل", "دوار هيشر", "المرناقية", "البطان",
        "منوبة", "طبربة", "الجديدة", "الجهة"
    ],

    "nabeul": [
        "نابل", "دار شعبان", "قربة", "منزل تميم", "الهوارية",
        "منزل بوزلفة", "قليبية", "حمام الأغزاز", "الميدة",
        "بني خيار", "الحمامات"
    ],

    "zaghouan": [
        "زغوان", "الناظور", "بوعرقوب", "الفحص",
        "صواف", "جبل الوسط"
    ],

    "bizerte": [
        "بنزرت الشمالية", "بنزرت الجنوبية", "رأس الجبل",
        "غار الملح", "منزل بورقيبة", "ماطر",
        "منزل جميل", "أوتيك", "تينجة",
        "جرزونة", "العالية", "سجنان",
        "جومين", "منزل عبد الرحمان"
    ],

    "beja": [
        "باجة الشمالية", "باجة الجنوبية", "تبرسق", "تيبار",
        "نفزة", "مجاز الباب", "قبلاط", "عمدون"
    ],

    "jendouba": [
        "جندوبة", "جندوبة الشمالية", "بوسالم", "طبرقة",
        "عين دراهم", "فرنانة", "غار الدماء", "وادي مليز"
    ],

    "kef": [
        "الكاف", "الكاف الشرقية", "نبر", "قلعة سنان",
        "ساقية سيدي يوسف", "الطويرف", "الجريصة",
        "السرس", " الدهماني", "عين ماضي"
    ],

    "siliana": [
        "سليانة", "سليانة الجنوبية", "قعفور", "العروسة",
        "بوعرادة", "الكريب", "الروحية", "برقو",
        "القصور", "مكثر"
    ],

    "kairouan": [
        "القيروان الشمالية", "القيروان الجنوبية", "الوسلاتية",
        "الشراردة", "العلا", "حفوز", "نصر الله",
        "الطويلة", "بوحجلة", "حاجب العيون"
    ],

    "kasserine": [
        "القصرين", "القصرين الجنوبية", "تالة", "فريانة",
        "العيون", "حاسي الفريد", "جدليان",
        "سبيبة", "سبيطلة", "الزهور", "ماجل بلعباس"
    ],

    "sidi_bouzid": [
        "سيدي بوزيد الغربية", "سيدي بوزيد الشرقية", "جلمة",
        "السبالة", "المزونة", "منزل بوزيان",
        "سوق الجديد", "الرقاب", "أولاد حفوز",
        "بئر الحفي", "السعيدة"
    ],

    "sousse": [
        "سوسة المدينة", "سوسة الرياض", "سوسة سيدي عبد الحميد",
        "مساكن", "القلعة الكبرى", "القلعة الصغرى", "سيدي بوعلي",
        "أكودة", "الجميل", "كندار", "بوفيشة", "النفيضة",
        "هيرقل", "زاوية سوسة"
    ],

    "monastir": [
        "المنستير", "جمال", "زرمدين", "قصيبة المديوني",
        "بنبلة", "قصر هلال", "المكنين", "طبلبة",
        "البقالطة", "لمطة", "بني حسان", "الساحلين", "خنيس"
    ],

    "mahdia": [
        "المهدية", "الجم", "قصور الساف", "الشابة", "ملولش",
        "سيدي علوان", "أولاد الشامخ", "هبيرة",
        "السواسي", "بومرداس"
    ],

    "sfax": [
        "صفاقس المدينة", "صفاقس الغربية", "صفاقس الجنوبية",
        "ساقية الزيت", "ساقية الداير", "قرقنة",
        "عقارب", "جبنيانة", "العامرة",
        "الحنشة", "الغريبة", "بير علي بن خليفة",
        "منزل شاكر"
    ],

    "gabes": [
        "قابس المدينة", "قابس الجنوبية", "قابس الغربية",
        "المطوية", "منزل الحبيب", "غنوش",
        "المطوية", "الحامة", "ودران"
    ],

    "medenine": [
        "مدنين الشمالية", "مدنين الجنوبية", "جرجيس",
        "بني خداش", "بن قردان", "سيدي مخلوف",
        "جربة ميدون", "جربة أجيم", "جربة حومة السوق"
    ],

    "tataouine": [
        "تطاوين الشمالية", "تطاوين الجنوبية",
        "غمراسن", "البئر الأحمر",
        "ذهيبة", "الصمار"
    ],

    "tozeur": [
        "توزر", "دقاش", "تمغزة",
        "نفطة", "حزوة"
    ],

    "kebili": [
        "قبلي الجنوبية", "قبلي الشمالية",
        "دوز الشمالية", "دوز الجنوبية",
        "سوق الأحد", "رجيم معتوق"
    ],

    "gafsa": [
        "أم العرائس", "الرديف", "السند",
        "القصر", "القطار", "المتلوي", 
        "المظيلة", "بالخير", "زانوش", 
        "سيدي بوبكر", "سيدي عيش", "قفصة الجنوبية",
        "قفصة الشمالية"
    ],
    }
    
    REGISTRATION_CHOICES = [
        ('REGISTERED','مرسم'),
        ('NOT_REGISTERED','غير مرسم'),
        ('NOREGISTER','غير متوفر')

    ]

    NATIONALITY_CHOICES = [
        ('TUN','تونسية'),
        ('FOREIGN','أجنبية'),
        ('NONE','بدون جنسية'),
        ('UNDETER','غير محدد'),
        ('TUNFOR','تونسية و جنسية اخرى'),
    ]

    BIRTH_STATUS_CHOICES = [
        ('MARITAL','داخل إطار الزواج'),
        ('UNMARRIED','خارج إطار الزواج'),
    ]
    
    CHILD_IDENTITY_CHOICES = [
        ('VIRTUAL', 'هوية افتراضية'),
        ('BIOLOGICAL', 'هوية بيولوجية'),
        ('VIRBIO', 'عناصر الهوية غير مكتملة'),
    ]

    IDENTITY_PROOF_CHOICES = [
        ('FATHER_CONFIRM','إقرار في الاجال'),
        
        ('COURT', 'حكم قضائي'),
    ]

    MOTHER_AGE_STATUS_CHOICES = [
        ('MINOR', 'قاصر'),
        ('ADULT', 'راشد'),
    ]

    DETAIL_BIRTH_PLACE_CHOICES = [
        ('HOME', 'منزل'),
        ('PUBLIC_HEALTH', 'مؤسسة صحية عمومية'),
        ('PRIVATE_HEALTH', 'مؤسسة صحية خاصة'),
        ('NOTDISO', 'غير معلوم'),
        ('OTHER', 'أخرى'),
    ]

    CHILDREN_DISPOSITION_CHOICES = [
        ('ACCOMPANY', 'اصطحاب'),
        ('ABANDON', 'تخلي'),
    ]
    FOREIGN_FAMILY_CHOICES = [
    ("with_parents", "مصحوب بذويه"),
    ("alone", "غير مصحوب بذويه"),
    ("with_relative", "غير مصحوب بذويه مع أحد أفراد عائلته او المجتمع المحلي"),
    ]

   

    IDENTITY_DOCUMENTS_CHOICES = [
    (True, "متوفرة"),
    (False, "غير متوفرة"),
    ]


    
   
    uid = models.CharField(
        'المعرف الوحيد',
        max_length=8,
        unique=True,
        editable=False,
        validators=[
            RegexValidator(
                regex=r'^\d{8}$',
                message="المعرف الوحيد يجب أن يكون بصيغة SSSSSSYY (8 أرقام)."
            )
        ]
    )
    numero_dossier = models.CharField(
    "رقم الملف",
    max_length=30,
    unique=True,
    editable=False,
    null=True,
    blank=True
    )

    first_name = models.CharField('الاسم', max_length=200)
    last_name = models.CharField('اللقب', max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    gender = models.CharField('الجنس', max_length=1, choices=GENDER_CHOICES, null=True)

    birth_date = models.DateField('تاريخ الميلاد',
                              blank=True, null=True)      # ← rendu facultatif

    birth_place = models.CharField('مكان الولادة', max_length=20,
                               choices=BIRTH_PLACE_CHOICES,
                               blank=True, null=True)
    birth_governorate = models.CharField(
    "الولاية",
    max_length=50,
    blank=True,
    null=True,
    choices=TUNISIA_GOVERNORATES
    )

    birth_department = models.CharField(
    "المعتمدية",
    max_length=50,
    blank=True,
    null=True
    )
    birth_country = CountryField(
    verbose_name="الدولة",
    blank=True,
    null=True
)
    delegate_ch = models.ForeignKey(
        Delegate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children"
    )
    delegate_unique_id = models.CharField(max_length=50, null=True, blank=True)
    delegate_unique_number = models.CharField(max_length=50, null=True, blank=True)


    registration_type = models.CharField(
    'الترسيم بدفاتر الحالة المدنية',
    max_length=20,
    choices=REGISTRATION_CHOICES,
    blank=True, null=True                                # ← plus de default
    )   
    registration_number = models.CharField(
    "عدد الرسم",
    max_length=50,          # <-- garder 50
    blank=True,
    null=True,
    validators=[
        RegexValidator(
            regex=r'^\d{7}$',
            message="عدد الرسم يجب أن يتكون من 7 أرقام."
        )
    ]
    )


    registration_date = models.DateField('تاريخ الرسم',
                                     blank=True, null=True)


    nationality = models.CharField(
    'جنسية الطفل',
    max_length=50,
    choices=NATIONALITY_CHOICES,
    blank=True, null=True                                 # déjà OK
    )

    foreign_country = CountryField(
    verbose_name="الدولة",
    blank=True,
    null=True
)
    birth_status = models.CharField('الولادة', max_length=20,
                                choices=BIRTH_STATUS_CHOICES,
                                blank=True, null=True)

    # Extra unmarried
    child_identity_type = models.CharField(
        'هوية الطفل',
        max_length=20,
        choices=CHILD_IDENTITY_CHOICES,
        blank=True, null=True
    )
    identity_proof = models.CharField(
        'إثبات الهوية',
        max_length=20,
        choices=IDENTITY_PROOF_CHOICES,
        blank=True, null=True
    )

    mother_age_at_birth = models.CharField(
        "سن الأم عند الولادة",
        max_length=10,
        choices=MOTHER_AGE_STATUS_CHOICES,
        blank=True, null=True
    )

    birth_place_detail = models.CharField(
        'مكان الانجاب',
        max_length=20,
        choices=DETAIL_BIRTH_PLACE_CHOICES,
        blank=True, null=True
    )
    siblings_outside_marriage = models.PositiveIntegerField('عدد الإخوة خارج إطار الزواج', blank=True, null=True)
    

    children_disposition = models.CharField(
        'مآلهم',
        max_length=20,
        choices=CHILDREN_DISPOSITION_CHOICES,
        blank=True, null=True
    )
    
    siblings_outside = models.PositiveIntegerField('عدد الإخوة في صحبة الام ', blank=True, null=True)
    siblings_out = models.PositiveIntegerField('عدد الإخوة المتخلي عنهم', blank=True, null=True)

    identity_documents_available = models.BooleanField(
    "وثائق الهوية",
    null=True,
    blank=True,
    choices=IDENTITY_DOCUMENTS_CHOICES,
    )

    foreign_family_status = models.CharField(
        "الوضعية العائلية للطفل الأجنبي",
        max_length=50,
        choices=FOREIGN_FAMILY_CHOICES,
        null=True,
        blank=True,
    )

    

    initial_status_at_birth = models.JSONField(
    default=dict,
    blank=True,
    verbose_name="الموقف الأولي من الطفل عند الولادة"
    )
    
   
    STATUS_CHOICES = [
    ('THREATENED', 'طفل مهدد'),
    ('DELINQUENT', 'طفل جانح'),
    ]

    status = models.CharField(
    "وضعية الطفل",
    max_length=20,
    choices=STATUS_CHOICES,
    blank=True,
    null=True
    )
   
    status_updated_from_threatened = models.BooleanField(
        default=False,
        verbose_name="تم تحيين الوضعية من طفل مهدد إلى طفل في خلاف مع القانون"
    )

    # تاريخ تحيين الوضعية
    status_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="تاريخ تحيين الوضعية"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.uid})"
        
    def generate_numero_dossier(self):
        if not self.delegate_ch:
            return None

        prefix = f"{self.delegate_ch.unique_id}."

        # آخر ملف لنفس المندوب
        last_child = Child.objects.filter(
            numero_dossier__startswith=prefix
        ).order_by('-numero_dossier').first()

        if last_child and last_child.numero_dossier:
            last_number = int(last_child.numero_dossier.split('.')[-1])
            next_number = last_number + 1
        else:
            next_number = 1

        return f"{prefix}{str(next_number).zfill(4)}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

    # 🔵 UID
        if not self.uid:
           year = timezone.now().year % 100
           year_str = f"{year:02d}"

           last_child = Child.objects.filter(
            uid__endswith=year_str
           ).order_by('-uid').first()

           new_number = int(last_child.uid[:6]) + 1 if last_child else 1
           self.uid = f"{new_number:06d}{year_str}"

    # ⬅️ الحفظ الأول (بدون numero_dossier)
        super().save(*args, **kwargs)

    # 🔴 توليد رقم الملف بعد التأكد من وجود delegate
        if is_new and self.delegate_ch and not self.numero_dossier:
           self.numero_dossier = self.generate_numero_dossier()
           super().save(update_fields=["numero_dossier"])

              
    


class NouveauNotification(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='notifications', verbose_name="الطفل")
    notifier_number = models.PositiveIntegerField(
        "رقم الإشعار",
        blank=True,
        null=True
    )
    notification_date = models.DateField("تاريخ الإشعار")
    notif_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    # ============================================================
    # CHAMPS CRÉATEUR
    # ============================================================
    created_by = models.ForeignKey(
        'Delegate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_created',
        verbose_name="المندوب الذي أضاف الإشعار"
    )
    
    created_by_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="اسم المندوب الذي أضاف الإشعار"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="تاريخ الإضافة")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="تاريخ التعديل")

    # مصدر الإشعار
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
    notifier_source = models.CharField("مصدر الإشعار", max_length=50, choices=NOTIFIER_SOURCE_CHOICES)
    notifier_source_other = models.CharField(
    "مصدر الإشعار (آخر)",
    max_length=255,
    blank=True,
    null=True
    )


    # طريقة الإشعار
    METHOD_CHOICES = [
        ('direct', 'مباشرة'),
        ('phone', 'عبر الهاتف'),
        ('hotline', ' الخط الأخضر'),
        ('letter', 'اشعار كتابي'),
        ('email', 'مراسلة إلكترونية'),
        ('lettermail', 'مراسلة بريدية'),
    ]
    notification_method = models.CharField("طريقة الإشعار", max_length=50, choices=METHOD_CHOICES)

    # مجموعة التهديدات (JSON)
    threats = models.JSONField("أشكال التهديد", default=dict, blank=True)

    # مصدر التهديد
    THREAT_SOURCE_CHOICES = [
        ('child', 'الطفل نفسه'),
        ('another_child', 'طفل آخر'),
        ('father', 'الأب'),
        ('mother', 'الأم'),
        ('relative', 'أحد الأقارب'),
        ('neighbor', 'الجار'),
        ('guardian', 'الولي/الحاضن'),
        ('employee', 'اطار/ عون تربوي'),
        ('educator', 'اطار/عون صحي'),
        ('public_agent', 'موظف/عون عمومي'),
        ('organization', 'عامل مباشر لوضعية '),
        ('unknown', 'الطفل'),
        
        ('ot', 'الاعوان الحاملين للسلاح'),
 
        ('oth', 'منتسب لمنظمة أو جمعية'),
 
        ('othe', 'الاعلام'),
 
        ('othet', 'شخص مجهول'),
 
        ('othey', 'طفل اخر'),
 
        ('other', 'أخرى'),
    ]
    threat_source = models.CharField("مصدر التهديد", max_length=50, choices=THREAT_SOURCE_CHOICES)

    # مكان التهديد
    THREAT_PLACE_CHOICES = [
        ('home', 'المنزل'),
         ('schoo', 'مؤسسة تربوية ما قبل الدراسة	'),
        ('school', 'مؤسسة تربوية'),
        ('training', 'مؤسسة تكوين مهني '),
        ('security', 'مؤسسة أمنية'),
        ('health', 'مؤسسة صحية'),
        ('care', 'مؤسسة رعاية'),
        ('fun', 'مؤسسة ترفيهية'),
        ('workshop', 'ورشة تدريب/فضاء '),
        ('street', 'فضاء للتدريب المهني                                                                '),
        ('stree', 'الشارع'),
        ('prison', 'مؤسسة سجنية	اصلاحية'),
        ('virtual', 'فضاء افتراضي'),
        ('chaotic', 'فضاء فوضوي'),
        ('nochaotic', 'غير محدد'),
        ('other', 'أخرى'),
    ]
    threat_location = models.CharField("مكان التهديد", max_length=50, choices=THREAT_PLACE_CHOICES)
    

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['child', 'created_by', 'notifier_number'], 
                name='unique_notifier_number_per_child_per_delegate'
            )
        ]
        ordering = ['child', 'notifier_number']

    def __str__(self):
        return f"إشعار للطفل {self.child.first_name} – رقم {self.notifier_number}"

    def save(self, *args, **kwargs):
        # ✅ Génération du numéro d'ordre
        if not self.notifier_number:
            last_number = (
                NouveauNotification.objects
                .filter(child=self.child)
                .aggregate(Max('notifier_number'))['notifier_number__max']
                or 0
            )
            self.notifier_number = last_number + 1

        # ✅ Remplir automatiquement created_by_name (CORRIGÉ)
        if self.created_by and not self.created_by_name:
            self.created_by_name = f"{self.created_by.first_name} {self.created_by.last_name}"

        super().save(*args, **kwargs)

    # ✅ NOUVELLES MÉTHODES UTILITAIRES
    def get_created_by_display(self):
        """Retourne le nom du créateur de manière lisible"""
        if self.created_by_name:
            return self.created_by_name
        elif self.created_by:
            return f"{self.created_by.first_name} {self.created_by.last_name}"
        return "غير معروف"

    def is_created_by_delegate(self, delegate):
        """Vérifie si la notification a été créée par un délégué spécifique"""
        if not delegate:
            return False
        return self.created_by == delegate

# models.py
class SummonsMethod(models.TextChoices):
    PHONE = 'PHONE', 'عبر الهاتف'
    WRITTEN = 'WRITTEN', 'كتابياً'
    SECURITY = 'SECURITY', 'جهة أمنية'

class VisitPlace(models.TextChoices):
    HOME = 'HOME', 'المنزل'
    STREET = 'STREET', 'الشارع'
    EARLY_PRIVATE = 'EARLY_PRIVATE', 'مؤسسة طفولة مبكرة قطاع خاص'
    EARLY_PUBLIC = 'EARLY_PUBLIC', 'مؤسسة طفولة مبكرة قطاع عام'
    SCHOOL = 'SCHOOL', 'المدارس'
    INSTITUTE = 'INSTITUTE', 'المعاهد'
    VOCATIONAL = 'VOCATIONAL', 'مراكز التكوين المهني'
    ASSOCIATION = 'ASSOCIATION', 'الجمعيات'
    CARE_CENTER = 'CARE_CENTER', 'مراكز الرعاية الاجتماعية'
    PROTECTION_CENTER = 'PROTECTION_CENTER', 'مراكز الحماية الاجتماعية'
    HEALTH_FACILITY = 'HEALTH_FACILITY', 'مؤسسة صحية'
    PUBLIC_PLACE = 'PUBLIC_PLACE', 'فضاء عمومي'

class InvestigationSummons(models.Model):
    investigation = models.ForeignKey(
        'Investigation', 
        on_delete=models.CASCADE, 
        related_name='summons_list'
    )
    summons_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الاستدعاء')
    summons_method = models.CharField(
        max_length=20,
        choices=SummonsMethod.choices,
        null=True,
        blank=True,
        verbose_name='طريقة الاستدعاء'
    )
    attendance_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الحضور')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['summons_date']
        verbose_name = 'استدعاء'
        verbose_name_plural = 'استدعاءات'

    def __str__(self):
        return f"استدعاء {self.summons_date} - {self.get_summons_method_display()}"


class InvestigationVisit(models.Model):
    investigation = models.ForeignKey(
        'Investigation',
        on_delete=models.CASCADE,
        related_name='visit_list'
    )
    visit_date = models.DateField(null=True, blank=True, verbose_name='تاريخ الزيارة')
    visit_place = models.CharField(
        max_length=30,
        choices=VisitPlace.choices,
        null=True,
        blank=True,
        verbose_name='مكان الزيارة'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['visit_date']
        verbose_name = 'زيارة'
        verbose_name_plural = 'زيارات'

    def __str__(self):
        return f"زيارة {self.visit_date} - {self.get_visit_place_display()}"


class InvestigationSocialReport(models.Model):
    investigation = models.ForeignKey(
        'Investigation',
        on_delete=models.CASCADE,
        related_name='social_report_list'
    )
    
    # 🔵 تواريخ التقرير الاجتماعي
    report_request = models.DateField(null=True, blank=True, verbose_name='تاريخ طلب البحث / التقرير')
    report_receive = models.DateField(null=True, blank=True, verbose_name='تاريخ الحصول على البحث / التقرير')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['report_request']
        verbose_name = 'تقرير اجتماعي'
        verbose_name_plural = 'تقارير اجتماعية'

    def __str__(self):
        return f"تقرير اجتماعي {self.report_request}"


class Investigation(models.Model):
    # 🔗 relations
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="investigations")
    notification = models.OneToOneField(
        NouveauNotification,
        on_delete=models.CASCADE,
        related_name="investigation"
    )

    # 🔵 données automatiques
    created_at = models.DateTimeField(auto_now_add=True)

    # 🔵 الإجراءات

    # طلب إذن قضائي
    court_request_date = models.DateField(null=True, blank=True)

    # تاريخ الشروع في الأبحاث
    investigation_start = models.DateField(null=True, blank=True)

    # التقييم النفسي
    psychological_request = models.DateField(null=True, blank=True)
    psychological_result = models.DateField(null=True, blank=True)

    # التقييم الطبي النفسي
    medical_psych_request = models.DateField(null=True, blank=True)
    medical_psych_result = models.DateField(null=True, blank=True)

    # نهاية الأبحاث
    investigation_end = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Investigation - Child {self.child.id} - Notification {self.notification.id}"

from django.utils import timezone

class ThreatAssessment(models.Model):
    """
    نموذج تقدير جدية التهديد
    Évaluation de la gravité de la menace
    """
    notification = models.OneToOneField(
        'NouveauNotification',
        on_delete=models.CASCADE,
        related_name='threat_assessment',
        verbose_name='الإشعار'
    )
    child = models.ForeignKey(
        'Child',
        on_delete=models.CASCADE,
        related_name='threat_assessments',
        verbose_name='الطفل'
    )
    
    # تاريخ تقدير حالة التهديد
    assessment_date = models.DateField(
        null=True, blank=True,
        verbose_name='تاريخ تقدير حالة التهديد'
    )

    DECISION_TYPE_CHOICES = [
    ('commitment', 'التعهد بوضعية الطفل'),
    ('family', 'رفع الأمر إلى قاضي الأسرة'),
    ('no_commitment', 'عدم التعهد بوضعية الطفل'),
    ]

    decision_type = models.CharField(
        max_length=30,
        choices=DECISION_TYPE_CHOICES,
        null=True,
        blank=True
    )


    # ==========================================
    # التعهد بوضعية الطفل
    # ==========================================

    decision_social_protection = models.BooleanField(
        default=False,
        verbose_name='توفير الحماية الاجتماعية'
    )

    # اعلام قاضي الأسرة
    decision_family_judge = models.BooleanField(
        default=False,
        verbose_name='اعلام قاضي الأسرة'
    )

    decision_public_prosecutor = models.BooleanField(
        default=False,
        verbose_name='إعلام النيابة العمومية بوضعية الطفل'
    )

    decision_violence_unit = models.BooleanField(
        default=False,
        verbose_name='إحالة الوضعية على الوحدة المختصة بالبحث في جرائم العنف ضد المرأة والطفل'
    )

    decision_relevant_services = models.BooleanField(
        default=False,
        verbose_name='إعلام المصالح ذات الصلة بالوضعية'
    )

    decision_trafficking_committee = models.BooleanField(
        default=False,
        verbose_name='إعلام الهيئة الوطنية لمكافحة للإتجار بالاشخاص'
    )


    # ==========================================
    # رفع الأمر إلى قاضي الأسرة
    # ==========================================

    decision_family_referral = models.BooleanField(
        default=False,
        verbose_name='رفع الأمر إلى قاضي الأسرة'
    )


    # ==========================================
    # عدم التعهد بوضعية الطفل
    # ==========================================

    reason_not_serious = models.BooleanField(
        default=False,
        verbose_name='عدم جدية الإشعار'
    )

    reason_not_professional = models.BooleanField(
        default=False,
        verbose_name='عدم الاختصاص المهني'
    )

    reason_not_territorial = models.BooleanField(
        default=False,
        verbose_name='عدم الاختصاص الترابي مع إحالة الوضعية لمندوب حماية الطفولة المختص ترابيا'
    )

    reason_age_18 = models.BooleanField(
        default=False,
        verbose_name='بلوغ سن 18 سنة'
    )

    reason_address_inaccurate = models.BooleanField(
        default=False,
        verbose_name='تعذر التوصل إلى الطفل والعائلة لعدم دقة العنوان'
    )

    reason_threat_removed = models.BooleanField(
        default=False,
        verbose_name='زوال التهديد أثناء فترة التقصي'
    )

    reason_child_death = models.BooleanField(
        default=False,
        verbose_name='وفاة الطفل'
    )

    reason_no_agreement_20_days = models.BooleanField(
        default=False,
        verbose_name='عدم الحصول على أي اتفاق في 20 يوما من تاريخ التعهد بالحالة'
    )

    reason_agreement_breached = models.BooleanField(
        default=False,
        verbose_name='نقض الاتفاق من قبل الطفل أو أبويه أو من ينوبه'
    )


    # ملاحظات
    notes = models.TextField(
        blank=True, null=True,
        verbose_name='ملاحظات'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'تقدير جدية الإشعار'
        verbose_name_plural = 'تقديرات جدية الإشعار'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"تقدير جدية الإشعار - {self.notification.notifier_number}"
    
    def get_positive_decisions(self):
        """Retourne la liste des décisions positives"""
        decisions = []
        if self.decision_social_protection:
            decisions.append('توفير الحماية الاجتماعية')
        if self.decision_family_judge:
            decisions.append('اعلام قاضي الأسرة')
        if self.decision_public_prosecutor:
            decisions.append('إعلام النيابة العمومية')
        if self.decision_violence_unit:
            decisions.append('إحالة الوحدة المختصة بالعنف')
        if self.decision_relevant_services:
            decisions.append('إعلام المصالح ذات الصلة')
        if self.decision_trafficking_committee:
            decisions.append('إعلام الهيئة الوطنية لمكافحة للإتجار بالاشخاص')
        return decisions
    
    def get_negative_reasons(self):
        """Retourne la liste des raisons de non-prise en charge"""
        reasons = []
        if self.reason_not_serious:
            reasons.append('عدم جدية الإشعار')
        if self.reason_not_professional:
            reasons.append('عدم الاختصاص المهني')
        if self.reason_not_territorial:
            reasons.append('عدم الاختصاص الترابي')
        if self.reason_age_18:
            reasons.append('بلوغ سن 18 سنة')
        if self.reason_address_inaccurate:
            reasons.append('تعذر التوصل لعدم دقة العنوان')
        if self.reason_threat_removed:
            reasons.append('زوال التهديد أثناء فترة التقصي')
        if self.reason_child_death:
            reasons.append('وفاة الطفل')
        return reasons
    
    def is_commitment(self):
        """Vérifie si c'est un engagement (التعهد)"""
        return any([
            self.decision_social_protection,
            self.decision_family_judge,
            self.decision_public_prosecutor,
            self.decision_violence_unit,
            self.decision_relevant_services,
            self.decision_trafficking_committee
        ])
    
    def is_non_commitment(self):
        """Vérifie si c'est un non-engagement (عدم التعهد)"""
        return any([
            self.reason_not_serious,
            self.reason_not_professional,
            self.reason_not_territorial,
            self.reason_age_18,
            self.reason_address_inaccurate,
            self.reason_threat_removed,
            self.reason_child_death
        ])
    





class SocialDossierEnfant(models.Model):
    # ==================== EXISTING CHOICES ====================
    EDUCATIONAL_STATUS_CHOICES = [
        ('under_school_age', 'دون سن التمدرس'),
        ('enrolled', 'متمدرس'),
        ('vocational_training', 'مرسم بإحدى مسارات مراكز التكوين المهني/تدريب مهني'),
        ('dropped_out', 'منقطع عن الدراسة'),
        ('not_enrolled', 'لم يلتحق بأي مؤسسة تربوية بتاتا'),
        ('notauther', 'غير محدد'),
    ]
    
    HEALTH_STATUS_CHOICES = [
        ('good', 'في وضعية صحية طيبة'),
        ('chronic', 'يعاني من مرض مزمن'),
        ('mental', 'يعاني من مرض نفسي'),
        ('notheal', 'غير محدد'),
    ]

    # ✅ خيارات جديدة للإعاقة
    IS_DISABLED_CHOICES = [
        ('yes', 'نعم، حامل إعاقة'),
        ('no', 'لا، غير حامل إعاقة'),
    ]

    DISABILITY_TYPE_CHOICES = [
        ('physical', 'إعاقة عضوية'),
        ('visual', 'إعاقة بصرية'),
        ('hearing', 'إعاقة سمعية'),
        ('mental', 'إعاقة ذهنية'),
        ('multiple', 'إعاقة متعددة'),
    ]

    DISABILITY_DEGREE_CHOICES = [
        ('light', 'خفيفة'),
        ('medium', 'متوسطة'),
        ('severe', 'عميقة'),
    ]

    HEALTH_STATUS_CHOICES_FATH_Math = [
        ('good', 'في حالة صحية طيبة'),
        ('chronic', 'في حالة مرض مزمن'),
        ('mental', 'في حالة مرض نفسي'),
        ('disability', 'يعاني من وضعية إعاقة ذهني، بصري، سمعي، التوحد'),
        ('disab', 'حالة وفاة'),
        ('notheal', 'غير محدد'),
    ]
    
    SOCIAL_ALLOWANCE_CHOICES = [
        ('yes', 'نعم يتمتع الطفل بمنحة شهرية مخصصة للأطفال'),
        ('no', 'لا يتمتع الطفل بمنحة شهرية مخصصة للأطفال'),
        ('notyes', 'غير محدد'),
    ]
    
    ACADEMIC_RESULTS_CHOICES = [
        ('good', 'حسنة'),
        ('average', 'متوسطة'),
        ('poor', 'ضعيفة'),
        ('notau', 'غير محدد'),
    ]
    
    # ==================== NEW CHOICES ====================
    EDUCATION_LEVEL_CHOICES = [
        ('illiterate', 'أمي'),
        ('primary', 'تعليم أساسي'),
        ('secondary', 'تعليم ثانوي'),
        ('higher', 'تعليم عالي'),
        ('noted', 'غير محدد'),
    ]
    
    MOTHER_JOB_STATUS_CHOICES = [
        ('employed', 'موظفة'),
        ('worker', 'عاملة'),
        ('self_employed', 'مهنة حرة'),
        ('monthly_pension', 'جراية شهرية'),
        ('unemployed', 'عاطلة عن العمل'),
        ('notmo', 'غير محددة'),

    ]

    
    FATHER_JOB_STATUS_CHOICES = [
        ('employed', 'موظف'),
        ('worker', 'عامل'),
        ('self_employed', 'مهنة حرة'),
        ('monthly_pension', 'جراية شهرية'),
        ('unemployed', 'عاطل عن العمل'),
        ('notfa', 'غير محدد'),

    ]

    
    RESIDENCE_CHOICES = [
        ('inside', 'داخل تراب الجمهورية'),
        ('outside', 'خارج البلاد'),
    ]
    
    FAMILY_TYPE_CHOICES = [
        ('biological', 'عائلة بيولوجية'),
        ('single_parent', 'عائلة ذات ولي واحد'),
        ('extended', 'عائلة موسعة'),
        ('foster', 'عائلة استقبال'),
        ('adoption', 'عائلة تبني'),
        ('sponsorship', 'عائلة كفالة'),
    ]
    
    PARENTS_RELATIONSHIP_CHOICES = [
        ('married', 'زواج'),
        ('divorced', 'طلاق'),
        ('separated', 'فراق'),
        ('mother_deceased', 'وفاة الام'),
        ('father_deceased', 'وفاة الاب'),
        ('both_deceased', 'الوالدين متوفيان'),
        ('irregular', 'علاقة على خلاف الصيغ القانونية'),
    ]

    FAMILY_INCOME_SOURCE_CHOICES = [
    ('social_aid', 'إعانة اجتماعية'),
    ('alimony', 'نفقة'),
    ('salary', 'راتب'),
    ('pension', 'مدخول اعمال حرة'),
    ('other', 'أخرى'),
    ]


    FAMILY_SOCIAL_STATUS_CHOICES = [
        ('poor', 'عائلة معوزة، فقيرة'),
        ('low_income', 'عائلة محدودة الدخل'),
        ('average', 'متوسطة'),
        ('well_off', 'ميسورة الحال'),
    ]

    HEALTH_ACCESS_CHOICES = [
        ('health_fund', 'عائلة تتمتع بالتغطية الصحية من طرف الصناديق'),
        ('free_card', 'عائلة تتمتع ببطاقة العلاج المجاني'),
        ('reduced_rate', 'عائلة تتمتع ببطاقة العلاج بالتعريفة المنخفضة'),
        ('no_coverage_poor', 'عائلة معوزة لا تتمتع بأي تغطية صحية'),
        ('no_coverage_rich', 'عائلة ميسورة لا تتمتع بتغطية صحية'),
    ]

    # ==================== RELATIONSHIPS ====================
    notification = models.OneToOneField(
        'NouveauNotification', 
        on_delete=models.CASCADE,
        related_name='social_file',
        verbose_name='الإشعار'
    )
    child = models.ForeignKey(
        'Child',
        on_delete=models.CASCADE,
        related_name='social_files',
        verbose_name='الطفل'
    )

    # ==================== EXISTING FIELDS (Child Data) ====================
    current_address = models.TextField(
        verbose_name='عنوان الإقامة الحالية/ التواجد',
        blank=True
    )
    
    # ✅ CORRECTION : Utiliser Child.TUNISIA_GOVERNORATES
    governorate = models.CharField(
        max_length=100,
        choices=Child.TUNISIA_GOVERNORATES,
        verbose_name='الولاية',
        blank=True
    )
    
    delegation = models.CharField(
        max_length=100,
        verbose_name='المعتمدية',
        blank=True
    )
    
    educational_status = models.CharField(
        max_length=50,
        choices=EDUCATIONAL_STATUS_CHOICES,
        verbose_name='الوضعية التربوية– الدراسية الحالية',
        blank=True
    )
    
    health_status = models.CharField(
        max_length=50,
        choices=HEALTH_STATUS_CHOICES,
        verbose_name='الوضعية الصحية الحالية',
        blank=True
    )

    # ✅ الحقول الجديدة (بعد health_status)
    is_disabled = models.CharField(
        max_length=10,
        choices=IS_DISABLED_CHOICES,
        verbose_name='هل الطفل حامل إعاقة؟',
        blank=True
    )
    
    disability_type = models.CharField(
        max_length=20,
        choices=DISABILITY_TYPE_CHOICES,
        verbose_name='نوع الإعاقة',
        blank=True
    )
    
    disability_degree = models.CharField(
        max_length=20,
        choices=DISABILITY_DEGREE_CHOICES,
        verbose_name='درجة الإعاقة',
        blank=True
    )

    social_allowance = models.CharField(
        max_length=10,
        choices=SOCIAL_ALLOWANCE_CHOICES,
        verbose_name='المنحة الاجتماعية',
        blank=True
    )
    
    academic_results = models.CharField(
        max_length=20,
        choices=ACADEMIC_RESULTS_CHOICES,
        verbose_name='النتائج المدرسية',
        blank=True
    )

    # ==================== NEW: MOTHER DATA (1) ====================
    mother_first_name = models.CharField(
        max_length=100,
        verbose_name='الاسم',
        blank=True
    )
    mother_last_name = models.CharField(
        max_length=100,
        verbose_name='اللقب',
        blank=True
    )
    mother_nationality_1 = models.CharField(
        max_length=100,
        verbose_name='جنسية الأم 1',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    mother_nationality_2 = models.CharField(
        max_length=100,
        verbose_name='جنسية الأم 2',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    mother_residence_location = models.CharField(
        max_length=20,
        choices=RESIDENCE_CHOICES,
        verbose_name='مكان إقامة الأم',
        blank=True
    )
    
    # ✅ CORRECTION : Utiliser Child.TUNISIA_GOVERNORATES
    mother_governorate = models.CharField(
        max_length=100,
        choices=Child.TUNISIA_GOVERNORATES,
        verbose_name='ولاية إقامة الأم',
        blank=True,
        help_text='قائمة في ولايات الجمهورية'
    )
    
    mother_delegation = models.CharField(
        max_length=100,
        verbose_name='معتمدية إقامة الأم',
        blank=True,
        help_text='قائمة في معتمديات كل الولاية'
    )
    mother_country_abroad = models.CharField(
        max_length=100,
        verbose_name='الدولة (خارج البلاد)',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    mother_education_level = models.CharField(
        max_length=20,
        choices=EDUCATION_LEVEL_CHOICES,
        verbose_name='المستوى التعليمي للأم',
        blank=True
    )
    mother_job_status = models.CharField(
        max_length=20,
        choices=MOTHER_JOB_STATUS_CHOICES,
        verbose_name='الوضعية المهنية للأم',
        blank=True
    )
    mother_health_status = models.CharField(
        max_length=50,
        choices=HEALTH_STATUS_CHOICES_FATH_Math,
        verbose_name='الوضعية الصحية الحالية للأم',
        blank=True
    )
    
    # ==================== NEW: FATHER DATA (2) ====================
    father_first_name = models.CharField(
        max_length=100,
        verbose_name='الاسم',
        blank=True
    )
    father_last_name = models.CharField(
        max_length=100,
        verbose_name='اللقب',
        blank=True
    )
    father_nationality_1 = models.CharField(
        max_length=100,
        verbose_name='جنسية الأب 1',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    father_nationality_2 = models.CharField(
        max_length=100,
        verbose_name='جنسية الأب 2',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    father_residence_location = models.CharField(
        max_length=20,
        choices=RESIDENCE_CHOICES,
        verbose_name='مكان إقامة الأب',
        blank=True
    )
    
    # ✅ CORRECTION : Utiliser Child.TUNISIA_GOVERNORATES
    father_governorate = models.CharField(
        max_length=100,
        choices=Child.TUNISIA_GOVERNORATES,
        verbose_name='ولاية إقامة الأب',
        blank=True,
        help_text='قائمة في ولايات الجمهورية'
    )
    
    father_delegation = models.CharField(
        max_length=100,
        verbose_name='معتمدية إقامة الأب',
        blank=True,
        help_text='قائمة في معتمديات الولاية'
    )
    father_country_abroad = models.CharField(
        max_length=100,
        verbose_name='الدولة (خارج البلاد)',
        blank=True,
        help_text='قائمة في دول العالم'
    )
    father_education_level = models.CharField(
        max_length=20,
        choices=EDUCATION_LEVEL_CHOICES,
        verbose_name='المستوى التعليمي للأب',
        blank=True
    )
    father_job_status = models.CharField(
        max_length=20,
        choices=FATHER_JOB_STATUS_CHOICES,
        verbose_name='الوضعية المهنية للأب',
        blank=True
    )
    father_health_status = models.CharField(
        max_length=50,
        choices=HEALTH_STATUS_CHOICES_FATH_Math,
        verbose_name='الوضعية الصحية الحالية للأب',
        blank=True
    )
    
    # ==================== NEW: FAMILY DATA (3) ====================
    family_type = models.CharField(
        max_length=20,
        choices=FAMILY_TYPE_CHOICES,
        verbose_name='صنف العائلة*',
        blank=True
    )
    parents_relationship = models.CharField(
        max_length=20,
        choices=PARENTS_RELATIONSHIP_CHOICES,
        verbose_name='الوضعية العلائقية للوالدين*',
        blank=True
    )

    family_income_source = models.CharField(
        max_length=20,
        choices=FAMILY_INCOME_SOURCE_CHOICES,
        verbose_name='مصدر دخل العائلة',
        blank=True
    )

    family_social_status = models.CharField(
        max_length=20,
        choices=FAMILY_SOCIAL_STATUS_CHOICES,
        verbose_name='الوضعية الاجتماعية لعائلة الطفل',
        blank=True
    )
    
    health_access = models.CharField(
        max_length=20,
        choices=HEALTH_ACCESS_CHOICES,
        verbose_name='الولوج للخدمات الصحية',
        blank=True
    )

    # ==================== TIMESTAMPS ====================
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ==================== NATIONALITIES DICTIONARY ====================
    NATIONALITIES_AR = {
        'tunisian': 'تونسية',
        'algerian': 'جزائرية',
        'moroccan': 'مغربية',
        'libyan': 'ليبية',
        'egyptian': 'مصرية',
        'palestinian': 'فلسطينية',
        'syrian': 'سورية',
        'lebanese': 'لبنانية',
        'jordanian': 'أردنية',
        'iraqi': 'عراقية',
        'saudi': 'سعودية',
        'emirati': 'إماراتية',
        'qatari': 'قطرية',
        'kuwaiti': 'كويتية',
        'bahraini': 'بحرينية',
        'omani': 'عمانية',
        'yemeni': 'يمنية',
        'sudanese': 'سودانية',
        'mauritanian': 'موريتانية',
        'somali': 'صومالية',
        'comorian': 'جزر القمر',
        'djiboutian': 'جيبوتية',
        'turkish': 'تركية',
        'iranian': 'إيرانية',
        'afghan': 'أفغانية',
        'pakistani': 'باكستانية',
        'indian': 'هندية',
        'bangladeshi': 'بنغلاديشية',
        'indonesian': 'إندونيسية',
        'malaysian': 'ماليزية',
        'chinese': 'صينية',
        'japanese': 'يابانية',
        'korean': 'كورية',
        'thai': 'تايلاندية',
        'vietnamese': 'فيتنامية',
        'filipino': 'فلبينية',
        'russian': 'روسية',
        'ukrainian': 'أوكرانية',
        'french': 'فرنسية',
        'german': 'ألمانية',
        'british': 'بريطانية',
        'italian': 'إيطالية',
        'spanish': 'إسبانية',
        'portuguese': 'برتغالية',
        'dutch': 'هولندية',
        'belgian': 'بلجيكية',
        'swiss': 'سويسرية',
        'austrian': 'نمساوية',
        'swedish': 'سويدية',
        'norwegian': 'نرويجية',
        'danish': 'دنماركية',
        'finnish': 'فنلندية',
        'polish': 'بولندية',
        'czech': 'تشيكية',
        'hungarian': 'مجرية',
        'romanian': 'رومانية',
        'bulgarian': 'بلغارية',
        'greek': 'يونانية',
        'serbian': 'صربية',
        'croatian': 'كرواتية',
        'bosnian': 'بوسنية',
        'albanian': 'ألبانية',
        'macedonian': 'مقدونية',
        'slovenian': 'سلوفينية',
        'slovak': 'سلوفاكية',
        'lithuanian': 'ليتوانية',
        'latvian': 'لاتفية',
        'estonian': 'إستونية',
        'american': 'أمريكية',
        'canadian': 'كندية',
        'mexican': 'مكسيكية',
        'brazilian': 'برازيلية',
        'argentine': 'أرجنتينية',
        'chilean': 'تشيلية',
        'colombian': 'كولومبية',
        'peruvian': 'بيروفية',
        'venezuelan': 'فنزويلية',
        'ecuadorian': 'إكوادورية',
        'uruguayan': 'أوروغوايانية',
        'paraguayan': 'باراغوايانية',
        'bolivian': 'بوليفية',
        'cuban': 'كوبية',
        'dominican': 'دومينيكية',
        'australian': 'أسترالية',
        'new_zealander': 'نيوزيلندية',
        'south_african': 'جنوب أفريقية',
        'nigerian': 'نيجيرية',
        'ghanaian': 'غانية',
        'kenyan': 'كينية',
        'ethiopian': 'إثيوبية',
        'ugandan': 'أوغندية',
        'tanzanian': 'تنزانية',
        'zimbabwean': 'زيمبابوية',
        'zambian': 'زامبية',
        'malawian': 'مالاوية',
        'mozambican': 'موزمبيقية',
        'botswanan': 'بوتسوانية',
        'namibian': 'ناميبية',
        'angolan': 'أنغولية',
        'congolese': 'كونغولية',
        'gabonese': 'غابونية',
        'cameroonian': 'كاميرونية',
        'ivorian': 'إيفوارية',
        'senegalese': 'سنغالية',
        'malian': 'مالية',
        'burkinabe': 'بوركينابية',
        'nigerien': 'نيجرية',
        'chadian': 'تشادية',
        'central_african': 'أفريقية وسطى',
        'equatorial_guinean': 'غينية استوائية',
        'sao_tomean': 'ساو تومية',
        'gambian': 'غامبية',
        'guinean': 'غينية',
        'guinea_bissauan': 'غينية بيساوية',
        'sierra_leonean': 'سيراليونية',
        'liberian': 'ليبيرية',
        'togolese': 'توغولية',
        'beninese': 'بنينية',
    }

    # ==================== NATIONALITY METHODS ====================
    def get_nationality_ar(self, code):
        """
        Retourne le nom arabe d'une nationalité à partir de son code
        Si le code n'existe pas dans le dictionnaire, retourne le code lui-même
        """
        if not code:
            return 'غير محدد'
        return self.NATIONALITIES_AR.get(code, code)
    
    @property
    def father_nationality_1_ar(self):
        """جنسية الأب 1 بالعربية"""
        return self.get_nationality_ar(self.father_nationality_1)
    
    @property
    def father_nationality_2_ar(self):
        """جنسية الأب 2 بالعربية"""
        return self.get_nationality_ar(self.father_nationality_2)
    
    @property
    def mother_nationality_1_ar(self):
        """جنسية الأم 1 بالعربية"""
        return self.get_nationality_ar(self.mother_nationality_1)
    
    @property
    def mother_nationality_2_ar(self):
        """جنسية الأم 2 بالعربية"""
        return self.get_nationality_ar(self.mother_nationality_2)

    # ==================== META ====================
    class Meta:
        verbose_name = 'الملف الاجتماعي'
        verbose_name_plural = 'الملفات الاجتماعية'
        ordering = ['-created_at']

    def __str__(self):
        return f"الملف الاجتماعي - {self.child.first_name} {self.child.last_name}"
    
class EnfantDelinquant(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100) 
    sexe = models.CharField(max_length=10) 
    date_naissance = models.DateField() 
    num_extrait_naissance = models.TextField(blank=True, null=True)
    delegue = models.ForeignKey(Delegate, on_delete=models.SET_NULL, null=True, blank=True, related_name="enfants_delinquants")    
    date_creation = models.DateTimeField(auto_now_add=True)
    
    # AJOUTEZ CE CHAMP
    uid = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="المعرف الوحيد"
    )

    def __str__(self):
        return f"{self.nom} {self.prenom}"
    
    def save(self, *args, **kwargs):
        # Générer l'UID automatiquement s'il n'existe pas
        if not self.uid:
            from .views import get_next_uid
            self.uid = get_next_uid()
        super().save(*args, **kwargs)


from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class SocialFile(models.Model):
    enfant = models.OneToOneField(Child, on_delete=models.CASCADE, null=True, blank=True)

    famille_type = models.CharField(max_length=100)
    relation_parents = models.CharField(max_length=100)
    source_revenu = models.CharField(max_length=100)
    situation_sociale = models.CharField(max_length=100)
    couverture_sante = models.CharField(max_length=100)

    adresse_enfant = models.TextField()
    gouvernorat_enfant = models.CharField(max_length=100)
    delegation_enfant = models.CharField(max_length=100)
    situation_scolaire_enfant = models.CharField(max_length=100)
    situation_sante_enfant = models.CharField(max_length=100)
    beneficiaire_allocation_enfant = models.CharField(max_length=100)
    resultat_scolaire_enfant = models.CharField(blank=True, null=True, max_length=100)

    nom_pere = models.CharField(max_length=100)
    prenom_pere = models.CharField(max_length=100)
    nationalite_pere = models.CharField(max_length=500)
    residence_pere = models.CharField(max_length=50)
    gouvernorat_pere = models.CharField(max_length=100, blank=True, null=True)
    delegation_pere = models.CharField(max_length=100, blank=True, null=True)
    pays_pere = models.CharField(max_length=100, blank=True, null=True)

    niveau_etude_pere = models.CharField(max_length=100)
    etat_sante_pere = models.CharField(max_length=100)
    emploi_pere = models.CharField(max_length=100)

    nom_mere = models.CharField(max_length=100)
    prenom_mere = models.CharField(max_length=100)
    nationalite_mere = models.CharField(max_length=500)
    residence_mere = models.CharField(max_length=50)
    gouvernorat_mere = models.CharField(max_length=100, blank=True, null=True)
    delegation_mere = models.CharField(max_length=100, blank=True, null=True)
    pays_mere = models.CharField(max_length=100, blank=True, null=True)

    niveau_etude_mere = models.CharField(max_length=100)
    etat_sante_mere = models.CharField(max_length=100)
    emploi_mere = models.CharField(max_length=100)
    delegue = models.ForeignKey(Delegate, on_delete=models.SET_NULL, null=True, blank=True, related_name="fichiers_sociaux")    
    date_creation = models.DateTimeField(auto_now_add=True)
    
    
    def __str__(self):
        if self.enfant:
            return f"الملف الاجتماعي: {self.enfant.first_name} {self.enfant.last_name}"
        return "الملف الاجتماعي (بدون طفل)"


class Intervention(models.Model):
    enfant = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="interventions")
    date_intervention = models.DateField()
    role_demandeur = models.CharField(max_length=100, blank=True, null=True)
    concerne = models.CharField(max_length=100, blank=True, null=True)
    description_concerne = models.TextField(blank=True, null=True)
    situation_juridique_concerne = models.CharField(max_length=100, blank=True, null=True)
    adresse_concerne = models.TextField(blank=True, null=True)
    num_affaire = models.IntegerField()
    juridiction_competente = models.CharField(max_length=100, blank=True, null=True)
    date_fait = models.DateField(null=True, blank=True)
    lieu_fait = models.CharField(max_length=100, blank=True, null=True)
    type_fait = models.CharField(max_length=100, blank=True, null=True)
    etat_procedure = models.CharField(max_length=100, blank=True, null=True)
    enfant_recidiviste = models.CharField(max_length=10, blank=True, null=True)
    situation_actuelle_enfant = models.CharField(max_length=100, blank=True, null=True)
    description_situation_actuelle_enfant = models.TextField(blank=True, null=True)
    delegue = models.ForeignKey(Delegate, on_delete=models.SET_NULL, null=True, blank=True, related_name="interventions")
    date_creation = models.DateTimeField(auto_now_add=True)
    accord_reached = models.BooleanField(null=True, blank=True)
    accord_date = models.DateField(null=True, blank=True)
    
    
    def __str__(self):
        if self.enfant:
            return f"مطلب الوساطة: {self.enfant.first_name} {self.enfant.last_name}"
        return "مطلب الوساطة (بدون طفل)"
    

class MesureConvenue(models.Model):
    """
    Modèle pour les mesures conventionnelles (التدابير الاتفاقية المتخذة)
    """
    # Relations
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="mesures_convenues")
    notification = models.OneToOneField(
        NouveauNotification, 
        on_delete=models.CASCADE, 
        related_name="mesure_convenue"
    )
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    measure_date = models.DateField("تاريخ اتخاذ التدبير", null=True, blank=True)
    
    # Types de mesures conventionnelles
    AGREEMENT_TYPE_CHOICES = [
        ('keep_in_family_commitment', 'ابقاء الطفل في عائلته مع إلتزام الأبوين باتخاذ الإجراءات اللازمة لرفع الخطر المحدق به وذلك في آجال محددة ورهن رقابة دورية من مندوب حماية الطفولة'),
        ('keep_in_family_social_support', 'ابقاء الطفل في عائلته مع تنظيم طرق التدخل الاجتماعي الملائم وذلك بالتعاون مع الهيئة المعنية بتقديم الخدمات والمساعدة الاجتماعية اللازمة للطفل ولعائلته'),
        ('keep_in_family_prevent_contact', 'ابقاء الطفل في عائلته مع اخذ الاحتياطات اللازمة لمنع كل اتصال بينه وبين الأشخاص الذين من شأنهم ان يتسببوا له فيما يهدد صحته أو سلامته البدنية أو المعنوية'),
        ('temporary_placement', 'إيداع الطفل مؤقتا لدى عائلة أو أيهيئة أو مؤسسة اجتماعية أو تربوية أخرى ملائمة عمومية كانت او خاصة وعند الاقتضاء بمؤسسة استشفائية وذلك طبقا للقواعد المعمول بها'),
    ]
    
    agreement_type = models.CharField(
        "نوع التدبير الاتفاقي",
        max_length=100,
        choices=AGREEMENT_TYPE_CHOICES,
        null=True,
        blank=True
    )
    
    # توعية وتوجيه العائلة
    family_awareness_date = models.DateField("تاريخ توعية وتوجيه العائلة", null=True, blank=True)
    
    # ==================== مكان الإيواء (Hébergement) ====================
    
    # Type d'éloignement (مكان الإيواء)
    PLACEMENT_TYPE_CHOICES = [
        ('family_nuclear', 'لدى العائلة النواة'),
        ('family_extended', 'لدى العائلة الموسعة'),
    ]
    
    placement_type = models.CharField(
        "نوع الإيواء",
        max_length=50,
        choices=PLACEMENT_TYPE_CHOICES,
        null=True,
        blank=True
    )
    
    # ==================== مكان الإيداع (Dépôt) ====================
    
    # Lieu de dépôt (مكان الإيداع)
    PLACEMENT_LOCATION_CHOICES = [
        ('family_extended', 'لدى العائلة الموسعة'),
        ('foster_family', 'عائلة استقبال'),
        ('children_villages', 'قرى الأطفال س و س'),
        ('inpe', 'المعهد الوطني لرعاية الطفولة'),
        ('social_care_center', 'مركز رعاية الاجتماعية للأطفال'),
        ('social_support_center', 'مركز الإحاطة الاجتماعية'),
        ('association', 'جمعية / وحدة عيش'),
        ('youth_center', 'مركز مندمج للشباب والطفولة'),
        ('women_shelter', 'مركز لإيواء النساء والأطفال ضحايا العنف'),
        ('hospital', 'مؤسسة استشفائية'),
        ('migrant_center', 'المراكز المخصصة لإيواء الأطفال المهاجرين التابعة للمنظمات الدولية أو للجمعيات الناشطة'),
        ('other', 'أخرى'),
    ]
    
    placement_location = models.CharField(
        "مكان الإيداع",
        max_length=50,
        choices=PLACEMENT_LOCATION_CHOICES,
        null=True,
        blank=True
    )
    
    other_placement_location = models.CharField(
        "مكان إيداع آخر (تحديد)",
        max_length=255,
        null=True,
        blank=True
    )
    
    # ==================== 🔴 NOUVEAU : Champs pour la version "DANGER" (مكان الإيداع pour les cas de danger) ====================
    
    PLACEMENT_DANGER_CHOICES = [
        ('juvenile_center', 'مركز إيداع الأحداث'),
        ('police_custody', 'حراسة الشرطة'),
        ('penal_institution', 'مؤسسة إصلاحية'),
        ('rehabilitation_center', 'مركز إعادة التأهيل'),
        ('other_danger', 'أخرى'),
    ]
    
    placement_location_danger = models.CharField(
        "مكان الإيداع (حالة خطر)",
        max_length=50,
        choices=PLACEMENT_DANGER_CHOICES,
        null=True,
        blank=True
    )
    
    other_placement_location_danger = models.CharField(
        "مكان إيداع آخر (تحديد) - حالة خطر",
        max_length=255,
        null=True,
        blank=True
    )
    
    # ==================== SUIVI ====================
    
    FOLLOW_UP_STATUS_CHOICES = [
        ('continue', 'مواصلة تنفيذ التدبير الاتفاقي المتخذ'),
        ('review', 'مراجعة التدبير الاتفاقي من قبل مندوب حماية الطفولة'),
        ('refuse_proposal', 'رفع الأمر لقاضي الأسرة بسبب رفض التدبير المقترح'),
        ('child_violation', 'رفع الأمر لقاضي الأسرة بسبب نقض التدبير الاتفاقي من قبل الطفل'),
        ('parents_violation', 'رفع الأمر لقاضي الأسرة بسبب نقض التدبير الاتفاقي من قبل الابوين أو من له النظر'),
        ('judge_request', 'رفع الأمر لقاضي الأسرة بطلب منه'),
        ('file_closed', 'حفظ الملف لزوال موجب التعهد'),
    ]
    
    follow_up_status = models.CharField(
        "حالة المتابعة",
        max_length=50,
        choices=FOLLOW_UP_STATUS_CHOICES,
        null=True,
        blank=True
    )
    
    # ==================== VALIDATION : Choix exclusif ====================
    
    def clean(self):
        """
        Validation au niveau modèle : Un seul type de placement peut être choisi
        """
        from django.core.exceptions import ValidationError
        
        # Vérifier si un champ de la catégorie "مكان الإيواء" est rempli
        has_placement_hebergement = bool(
            self.placement_type or 
            self.placement_location or 
            self.other_placement_location
        )
        
        # Vérifier si un champ de la catégorie "مكان الإيداع" est rempli
        has_placement_danger = bool(
            self.placement_location_danger or 
            self.other_placement_location_danger
        )
        
        if has_placement_hebergement and has_placement_danger:
            raise ValidationError(
                "❌ الرجاء اختيار مكان الإيواء أو مكان الإيداع فقط، ليس كليهما"
            )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Mesure conventionnelle - {self.child.first_name} {self.child.last_name} - {self.measure_date}"

class MesureUrgente(models.Model):
    """
    Modèle pour les mesures urgentes (التدابير العاجلة المتخذة)
    Pas de limite de nombre par notification
    """
    # Relations
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="mesures_urgentes")
    notification = models.ForeignKey(NouveauNotification, on_delete=models.CASCADE, related_name="mesures_urgentes")
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    
    # تدبير عاجل - numéro séquentiel (auto-incrémenté par notification)
    order = models.PositiveSmallIntegerField("رقم التدبير العاجل", default=1)
    
    # Type de menace (pour séparer l'affichage)
    MENACE_TYPE_CHOICES = [
        ('neglect', 'إهمال وتشرد'),
        ('danger', 'خطر ملم'),
        ('mixed', 'مختلط (إهمال وخطر ملم)'),
    ]
    menace_type = models.CharField(
        "نوع التهديد",
        max_length=20,
        choices=MENACE_TYPE_CHOICES,
        default='mixed',
        help_text="نوع التهديد الموجود في الإشعار"
    )
    
    # اتخاذ تدبير عاجل في حالات الإهمال والتشرد
    urgent_measure_neglect_date = models.DateField("تاريخ اتخاذ التدبير (إهمال وتشرد)", null=True, blank=True)
    court_permission_date = models.DateField("تاريخ الحصول على الإذن القضائي العاجل", null=True, blank=True)
    
    # مكان الإيداع بصفة مؤقتة (حالة الإهمال)
    PLACEMENT_CHOICES = [
        ('rehabilitation', 'مؤسسة إعادة تأهيل'),
        ('family_reception', 'مركز استقبال'),
        ('hospital', 'مؤسسة استشفائية'),
        ('family', 'عائلة'),
        ('authority', 'هيئة'),
        ('sos_village', 'قرى الأطفال س و س'),
        ('inpe', 'المعهد الوطني لرعاية الطفولة'),
        ('social_care', 'مركز الرعاية الاجتماعية للأطفال'),
        ('guidance_center', 'مركز الإحاطة والتوجيه الاجتماعي'),
        ('association', 'جمعية / وحدة عيش'),
        ('youth_center', 'مركز مندمج للشباب والطفولة'),
        ('women_shelter', 'مركز إيواء النساء والأطفال ضحايا العنف'),
        ('international', 'مراكز المنظمات الدولية'),
        ('other', 'أخرى'),
    ]
    
    placement_location = models.CharField(
        "مكان الإيداع بصفة مؤقتة (إهمال)",
        max_length=50,
        choices=PLACEMENT_CHOICES,
        null=True,
        blank=True
    )
    placement_location_other = models.CharField("مكان الإيداع (أخرى إهمال)", max_length=255, blank=True, null=True)
    
    # اتخاذ تدبير عاجل في حالات الخطر الملم
    urgent_measure_danger_date = models.DateField("تاريخ اتخاذ التدبير (خطر ملم)", null=True, blank=True)
    approval_date = models.DateField("تاريخ المصادقة على التدبير", null=True, blank=True)
    
    # مكان الإيداع بصفة مؤقتة (حالة الخطر الملم)
    placement_location_danger = models.CharField(
        "مكان الإيداع بصفة مؤقتة (خطر ملم)",
        max_length=50,
        choices=PLACEMENT_CHOICES,
        null=True,
        blank=True
    )
    placement_location_danger_other = models.CharField("مكان الإيداع (أخرى خطر ملم)", max_length=255, blank=True, null=True)
    
    # إعلام قاضي الأسرة
    judge_informed = models.BooleanField("إعلام قاضي الأسرة", default=False)
    judge_approval = models.BooleanField("إقراره بالصبغة الاستعجالية والضرورية للتدبير", default=False)
    police_assistance = models.BooleanField("الاستنجاد بالقوة العامة", default=False)
    
    # متابعة التدبير العاجل
    FOLLOW_UP_CHOICES = [
        ('follow_situation', 'متابعة وضعية الطفل أثناء فترة الإيواء الوقتي'),
        ('health_social_psych', 'تقديم المساعدة الصحية والرعاية الاجتماعية والنفسية للطفل'),
    ]
    
    follow_up_type = models.CharField(
        "نوع المتابعة",
        max_length=50,
        choices=FOLLOW_UP_CHOICES,
        null=True,
        blank=True
    )
    
    follow_up_date = models.DateField("تاريخ المتابعة", null=True, blank=True)
    follow_up_notes = models.TextField("ملاحظات المتابعة", null=True, blank=True)
    
    class Meta:
        ordering = ['notification', 'order']
        verbose_name = "تدبير عاجل"
        verbose_name_plural = "التدابير العاجلة"
    
    def __str__(self):
        type_display = dict(self.MENACE_TYPE_CHOICES).get(self.menace_type, '')
        return f"تدبير عاجل {self.order} ({type_display}) - {self.child.first_name} {self.child.last_name}"
    
    def save(self, *args, **kwargs):
        if not self.order or self.order == 1:
            last_order = MesureUrgente.objects.filter(notification=self.notification).aggregate(
                models.Max('order')
            )['order__max']
            self.order = (last_order or 0) + 1
        super().save(*args, **kwargs)
    
    def get_placement_location_display(self):
        if self.placement_location == 'other':
            return self.placement_location_other or "أخرى"
        return dict(self.PLACEMENT_CHOICES).get(self.placement_location, "-")
    
    def get_placement_location_danger_display(self):
        if self.placement_location_danger == 'other':
            return self.placement_location_danger_other or "أخرى"
        return dict(self.PLACEMENT_CHOICES).get(self.placement_location_danger, "-")
    
    def get_follow_up_display(self):
        return dict(self.FOLLOW_UP_CHOICES).get(self.follow_up_type, "-")
    
    @property
    def judge_info(self):
        info = []
        if self.judge_informed:
            info.append("📋 إعلام القاضي")
        if self.judge_approval:
            info.append("✅ إقرار القاضي")
        if self.police_assistance:
            info.append("🚓 استنجاد بالقوة العامة")
        return " | ".join(info) if info else "-"
    
    @property
    def is_neglect_only(self):
        """Vérifie si c'est un cas d'إهمال seulement"""
        return self.menace_type == 'neglect'
    
    @property
    def is_danger_only(self):
        """Vérifie si c'est un cas de خطر ملم seulement"""
        return self.menace_type == 'danger'
    
    @property
    def is_mixed(self):
        """Vérifie si c'est un cas mixte"""
        return self.menace_type == 'mixed'

# ==================== MODÈLE TRAFFICKING NOTIFICATION (الاتجار بالأطفال) ====================
class TraffickingNotification(models.Model):
    """إشعارات الاتجار بالأطفال"""
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="trafficking_notifications")
    delegate_ch = models.ForeignKey(Delegate, on_delete=models.CASCADE, null=True, blank=True, related_name="trafficking_notifications")
    
    threat_assessment = models.OneToOneField(
        'ThreatAssessment', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="trafficking_notification"
    )
    
    notification_date = models.DateField("تاريخ الإشعار", auto_now_add=True)
    notifier_number = models.CharField("رقم المبلغ", max_length=50, blank=True, null=True)
    
    # ==================== Méthode d'entrée ====================
    entry_method_regular = models.BooleanField("بطريقة نظامية", default=False)
    entry_method_irregular = models.BooleanField("بطريقة غير نظامية", default=False)
    entry_irregular_sea = models.BooleanField("عن طريق البحر", default=False)
    entry_irregular_land = models.BooleanField("عن طريق البر", default=False)
    
    # ==================== Localisation exploitation ====================
    exploitation_location_abroad = models.BooleanField("خارج البلاد التونسية", default=False)
    exploitation_location_tunisia = models.BooleanField("داخل البلاد التونسية", default=False)
    exploitation_governorate = models.CharField("الولاية", max_length=100, blank=True, null=True)
    
    # ==================== Lieux d'exploitation ====================
    exploitation_home = models.BooleanField("المنزل", default=False)
    exploitation_relatives_home = models.BooleanField("منزل أحد الأقارب", default=False)
    exploitation_other_residence = models.BooleanField("مقر إقامة آخر", default=False)
    exploitation_employer_home = models.BooleanField("منزل المشغل", default=False)
    exploitation_legal_workshop = models.BooleanField("ورشة تشغيل قانونية", default=False)
    exploitation_illegal_workshop = models.BooleanField("ورشة تشغيل غير قانونية", default=False)
    exploitation_private_place = models.BooleanField("مكان خاص يوفره المستغل", default=False)
    exploitation_fields = models.BooleanField("الحقول الفلاحية", default=False)
    exploitation_factories = models.BooleanField("المصانع", default=False)
    exploitation_street = models.BooleanField("الشارع", default=False)
    exploitation_markets = models.BooleanField("الأسواق", default=False)
    exploitation_public_places = models.BooleanField("الأماكن العامة", default=False)
    exploitation_other = models.BooleanField("أخرى", default=False)
    exploitation_other_text = models.CharField("مكان آخر", max_length=255, blank=True, null=True)
    
    # ==================== Auteurs de l'exploitation ====================
    exploiter_parents = models.BooleanField("الوالدين", default=False)
    exploiter_father = models.BooleanField("الأب", default=False)
    exploiter_mother = models.BooleanField("الأم", default=False)
    exploiter_guardian = models.BooleanField("الحاضن/الكافل", default=False)
    exploiter_relative = models.BooleanField("أحد الأقارب", default=False)
    exploiter_outside_family = models.BooleanField("خارج محيط العائلي", default=False)
    exploiter_unknown = models.BooleanField("شخص مجهول", default=False)
    exploiter_employer = models.BooleanField("المشغل", default=False)
    exploiter_other = models.BooleanField("أخرى", default=False)
    exploiter_other_text = models.CharField("جهة أخرى", max_length=255, blank=True, null=True)
    
    # ==================== Formes d'exploitation ====================
    exploitation_sexual = models.BooleanField("الاستغلال الجنسي", default=False)
    exploitation_labor = models.BooleanField("استغلال العمل", default=False)
    exploitation_begging = models.BooleanField("التسول", default=False)
    exploitation_forced_marriage = models.BooleanField("الزواج القسري", default=False)
    exploitation_organ_trafficking = models.BooleanField("الاتجار بالأعضاء", default=False)
    exploitation_drug_trafficking = models.BooleanField("الاتجار بالمخدرات", default=False)
    exploitation_armed_conflict = models.BooleanField("النزاع المسلح", default=False)
    
    # ==================== العناصر المكونة لجريمة الاتجار (استقطاب، تجنيد، نقل، تنقيل، تحويل وجهة، ترحيل، استقبال وإيواء) ====================
    crime_recruitment = models.BooleanField("استقطاب", default=False)
    crime_enlistment = models.BooleanField("تجنيد", default=False)
    crime_transport = models.BooleanField("نقل", default=False)
    crime_relocation = models.BooleanField("تنقيل", default=False)
    crime_diversion = models.BooleanField("تحويل وجهة", default=False)
    crime_deportation = models.BooleanField("ترحيل", default=False)
    crime_reception = models.BooleanField("استقبال وإيواء", default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-notification_date']
        verbose_name = "إشعار اتجار بالأطفال"
        verbose_name_plural = "إشعارات الاتجار بالأطفال"
    
    def has_complete_information(self):
        """
        Vérifie si la notification a des informations détaillées complétées
        """
        # Vérifier si des informations de localisation ont été remplies
        has_location_info = (
            self.exploitation_location_tunisia or 
            self.exploitation_location_abroad
        )
        
        # Vérifier si des lieux d'exploitation ont été sélectionnés
        has_place_info = (
            self.exploitation_home or
            self.exploitation_relatives_home or
            self.exploitation_other_residence or
            self.exploitation_employer_home or
            self.exploitation_legal_workshop or
            self.exploitation_illegal_workshop or
            self.exploitation_private_place or
            self.exploitation_fields or
            self.exploitation_factories or
            self.exploitation_street or
            self.exploitation_markets or
            self.exploitation_public_places or
            self.exploitation_other
        )
        
        # Vérifier si des auteurs d'exploitation ont été identifiés
        has_exploiter_info = (
            self.exploiter_parents or 
            self.exploiter_father or 
            self.exploiter_mother or 
            self.exploiter_guardian or 
            self.exploiter_relative or 
            self.exploiter_outside_family or
            self.exploiter_unknown or
            self.exploiter_employer or
            self.exploiter_other
        )
        
        # Vérifier si des formes d'exploitation ont été sélectionnées
        has_exploitation_type = (
            self.exploitation_sexual or 
            self.exploitation_labor or 
            self.exploitation_begging or
            self.exploitation_forced_marriage or 
            self.exploitation_organ_trafficking or
            self.exploitation_drug_trafficking or
            self.exploitation_armed_conflict
        )
        
        # Vérifier si des éléments de la jratraite ont été sélectionnés
        has_crime_elements = (
            self.crime_recruitment or
            self.crime_enlistment or
            self.crime_transport or
            self.crime_relocation or
            self.crime_diversion or
            self.crime_deportation or
            self.crime_reception
        )
        
        # Vérifier les méthodes d'entrée (pour les enfants étrangers)
        has_entry_method = (
            self.entry_method_regular or
            self.entry_method_irregular or
            self.entry_irregular_sea or
            self.entry_irregular_land
        )
        
        # Considérer comme complet si des informations existent
        # (au moins une catégorie remplie)
        return (
            has_location_info or 
            has_place_info or 
            has_exploiter_info or 
            has_exploitation_type or 
            has_crime_elements or
            has_entry_method
        )
    
    def __str__(self):
        return f"إشعار اتجار - {self.child.first_name} {self.child.last_name} - {self.notification_date}"

class ProductionRequest(models.Model):
    enfant = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="production_requests")
    date_demande = models.DateField()
    mesures = models.JSONField(default=list)   
    delegue = models.ForeignKey(Delegate, on_delete=models.SET_NULL, null=True, blank=True)
    notification = models.OneToOneField(NouveauNotification, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Mطلب حماية - {self.enfant.first_name} {self.enfant.last_name} ({self.date_demande})"
    
    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'مطلب حماية'
        verbose_name_plural = 'مطالب الحماية'


class Production(models.Model):
    enfant = models.ForeignKey(Child, on_delete=models.CASCADE, related_name="production")
    notification = models.OneToOneField(NouveauNotification, on_delete=models.SET_NULL, null=True, blank=True)
    delegue = models.ForeignKey(Delegate, on_delete=models.SET_NULL, null=True, blank=True)
    date_mesure_temporaire = models.DateField(blank=True, null=True)
    lieu_hebergement = models.JSONField(default=list, blank=True, null=True)
    date_affectation = models.DateField(blank=True, null=True)
    procedure_recherche = models.JSONField(default=list, blank=True, null=True)
    date_resultats_recherche = models.DateField(blank=True, null=True)
    date_estimation_situation = models.DateField(blank=True, null=True)
    decision_judge = models.JSONField(default=list, blank=True, null=True)
    date_session_judiciaire = models.DateField(blank=True, null=True)
    moyens_autorises = models.JSONField(default=list, blank=True, null=True)
    lieu_depot = models.JSONField(default=list, blank=True, null=True)
    suivi_situation_enfant = models.JSONField(default=list, blank=True, null=True)
    evaluation_situation_enfant = models.JSONField(default=list, blank=True, null=True)
    resultat_suivi = models.JSONField(default=list, blank=True, null=True)
    accord_protection = models.BooleanField(null=True, blank=True)
    date_accord_protection = models.DateField(blank=True, null=True)
    date_refus_protection = models.DateField(blank=True, null=True)
    decision_protection_judge = models.JSONField(default=list, blank=True, null=True)
    date_execution_decision = models.DateField(blank=True, null=True)
    non_execution_decision = models.JSONField(default=list, blank=True, null=True)
    date_cloture = models.DateField(blank=True, null=True)
    date_transfert_juge = models.DateField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"الحماية القضائية - {self.enfant.first_name} {self.enfant.last_name}"
    
    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'الحماية القضائية'
        verbose_name_plural = 'الحماية القضائية'

    
class ResultatProductionRequest(models.Model):
    production_request = models.OneToOneField(
        "ProductionRequest",
        on_delete=models.CASCADE,
        related_name="resultat"
    )
    delegue = models.ForeignKey(
        "Delegate",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    accord_protection = models.BooleanField(null=True, blank=True)
    date_accord_protection = models.DateField(null=True, blank=True)
    date_refus_protection = models.DateField(null=True, blank=True)
    decision_protection_judge = models.JSONField(default=list, blank=True)
    date_execution_decision = models.DateField(null=True, blank=True)
    non_execution_decision = models.JSONField(default=list, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"مآل مطلب الحماية - {self.production_request.enfant.first_name} {self.production_request.enfant.last_name}"
    
    class Meta:
        ordering = ['-date_creation']
        verbose_name = 'مآل مطلب الحماية'
        verbose_name_plural = 'مآل مطالب الحماية'


class SuiviEnfant(models.Model):


    child = models.ForeignKey(
        'Child',
        on_delete=models.CASCADE,
        related_name='suivis'
    )

    # ==========================
    # COMMUNICATION / RAPPORTS
    # ==========================

    nb_entretiens = models.PositiveIntegerField(default=0)

    avec_enfant = models.PositiveIntegerField(default=0)
    avec_mere = models.PositiveIntegerField(default=0)
    avec_pere = models.PositiveIntegerField(default=0)
    avec_famille_etendue = models.PositiveIntegerField(default=0)
    avec_tuteur_legal = models.PositiveIntegerField(default=0)
    avec_membre_famille = models.PositiveIntegerField(default=0)
    avec_cadre_medical = models.PositiveIntegerField(default=0)
    avec_cadre_educatif = models.PositiveIntegerField(default=0)

    # ==========================
    # APPELS TELEPHONIQUES
    # ==========================

    nb_appels = models.PositiveIntegerField(default=0)

    appel_enfant = models.PositiveIntegerField(default=0)
    appel_mere = models.PositiveIntegerField(default=0)
    appel_pere = models.PositiveIntegerField(default=0)
    appel_famille_etendue = models.PositiveIntegerField(default=0)
    appel_tuteur_legal = models.PositiveIntegerField(default=0)
    appel_membre_famille = models.PositiveIntegerField(default=0)
    appel_cadre_medical = models.PositiveIntegerField(default=0)
    appel_cadre_educatif = models.PositiveIntegerField(default=0)

    # ==========================
    # VISITES DE TERRAIN
    # ==========================

    nb_visites = models.PositiveIntegerField(default=0)

    # Lieux de visite - choix multiples
    visite_institution_educative = models.BooleanField(
        default=False,
        verbose_name="مؤسسة تربوية"
    )

    visite_institution_hospitaliere = models.BooleanField(
        default=False,
        verbose_name="مؤسسة استشفائية"
    )

    visite_institution_depot = models.BooleanField(
        default=False,
        verbose_name="مؤسسة إيداع"
    )

    visite_centre_reforme = models.BooleanField(
        default=False,
        verbose_name="مركز إصلاح الأطفال"
    )

    visite_maison = models.BooleanField(
        default=False,
        verbose_name="المنزل"
    )

    visite_autre = models.BooleanField(
        default=False,
        verbose_name="أخرى"
    )

    autre_lieu_visite = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="تحديد مكان آخر"
    )

    # ==========================
    # EVALUATION
    # ==========================

    STATUS_CHOICES = [
        ('THREAT_CONTINUES', 'تواصل التهديد'),
        ('THREAT_WORSENS', 'تفاقم وضعية التهديد'),
        ('IMPROVEMENT', 'تحسن نسبي في وضعية الطفل'),
        ('THREAT_REMOVED', 'زوال وضعية التهديد'),
    ]

    evaluation = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        blank=True
    )

    observations = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'متابعة الطفل'
        verbose_name_plural = 'متابعة الأطفال'

    def __str__(self):
        return f"متابعة {self.child} - {self.created_at:%Y-%m-%d}"
   

