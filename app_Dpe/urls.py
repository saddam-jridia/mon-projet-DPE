from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ArabicPasswordResetForm

urlpatterns = [
    # Pages d'accueil
    path('index1/', views.index, name='index1'),
    path('dashboard/', views.other_dashboard, name='dashboard'),
    path('index2/', views.other_dashboard, name='index2'),

    # Auth
    path('login/', views.login, name='login'),
    path('logout/', views.View_logout, name='logout'),

    # Delegate
    path('delegate/create/', views.create_delegate, name='delegate_create'),
    path('ajax/next-delegate-id/', views.ajax_next_delegate_id, name='ajax_next_delegate_id'),

    # Register success
    path('register/success/', views.register_success, name='register_success'),
    path('accounts/tableauboard/', views.home_tableauboard , name='tableauboard'),

    # AJAX: State prefix
    path('get_state_prefix/', views.get_state_prefix, name='get_state_prefix'),

    # Password reset
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='account/password_reset.html',
            form_class=ArabicPasswordResetForm,
            email_template_name='account/password_reset_email.html',
            subject_template_name='account/password_reset_subject.txt',
            success_url='/password_reset/done/',
        ),
        name='password_reset'
    ),
    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='account/password_reset_done.html'
        ),
        name='password_reset_done'
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='account/password_reset_confirm.html'
        ),
        name='password_reset_confirm'
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='account/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # Dashboard pages
    path('child-threatened/', views.child_threatened, name='child_threatened'),
    path('child-delinquent/', views.child_delinquent, name='child_delinquent'),
    path('investigation/', views.investigation, name='investigation'),
    path('trafficking/', views.trafficking, name='trafficking'),
]
