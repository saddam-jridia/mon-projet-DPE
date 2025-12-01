from django.contrib import admin
from django.urls import path, include
from app_Dpe import views

urlpatterns = [
    path('', views.index, name='index'),
    path('admin/', admin.site.urls),
    path('', include('app_Dpe.urls')),
    path('other-dashboard/', views.other_dashboard, name='other_dashboard'),
]
