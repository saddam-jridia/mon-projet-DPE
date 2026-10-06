"""
URL configuration for projet_Dpe project.
"""
from django.contrib import admin
from django.urls import path, include
from app_Dpe import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # ==================== ADMIN URLs PERSONNALISÉES ====================

    # Dashboard Admin
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Gestion des délégués
    path('admin/delegates/', views.admin_delegate_list, name='admin_delegate_list'),
    path('admin/delegates/add/', views.admin_register_delegate, name='admin_register_delegate'),
    path('admin/delegates/add/success/', views.admin_register_success, name='admin_register_success'),
    path('admin/delegate/edit/<int:pk>/', views.admin_delegate_edit, name='admin_delegate_edit'),
    path('admin/delegate/delete/<int:pk>/', views.admin_delegate_delete, name='admin_delegate_delete'),

    # Gestion des enfants
    path('admin/children/', views.admin_child_list, name='admin_child_list'),
    path('admin/child/edit/<int:pk>/', views.admin_child_edit, name='admin_child_edit'),
    path('admin/child/delete/<int:pk>/', views.admin_child_delete, name='admin_child_delete'),

    # ==================== DJANGO ADMIN NATIF ====================
    path('admin/', admin.site.urls),

    # ==================== REDIRECTION POUR LOGIN ====================
    path('accounts/login/', views.login_delegate, name='login'),

    # ==================== APPLICATION PRINCIPALE ====================
    path('', include('app_Dpe.urls')),
]