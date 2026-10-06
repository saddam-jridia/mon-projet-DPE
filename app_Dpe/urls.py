from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ArabicPasswordResetForm

urlpatterns = [
    # Page d'accueil / dashboard
    path('', views.index1, name='index'),
    path('index1/', views.index, name='index1'),
    path('dashboard/', views.other_dashboard, name='dashboard'),
    path('index2/', views.other_dashboard, name='index2'),
    path('other-dashboard/', views.other_dashboard, name='other_dashboard'),
    path('header/', views.header, name='header1'),
    
    # Authentification
    path("login/", views.login_delegate, name="login_delegate"),
    path('logout/', views.View_logout, name='logout'),

    # Delegate
    path('delegate/register/', views.register_delegate, name='register_delegate'),
    path('delegate/create/', views.create_delegate, name='delegate_create'),
    path('ajax/next-delegate-id/', views.ajax_next_delegate_id, name='ajax_next_delegate_id'),
    path('delegates/', views.delegate_list, name='delegate_list'),
    path('delegates/<int:pk>/edit/', views.delegate_edit, name='delegate_edit'),
    path('delegates/<int:pk>/delete/', views.delegate_delete, name='delegate_delete'),
    path('clear-messages/', views.clear_messages, name='clear_messages'),
    path('register/success/', views.register_success_view, name='register_success'),

    # Tableau de bord
    path('accounts/tableauboard/', views.home_tableauboard, name='tableauboard'),
    path('accounts/tableauboard_mandoub_jihawi/', views.home_mandoub_jihawi, name='tableauboard_mandoub_jihawi'),
    path('accounts/admindashboard/', views.admindashboard, name='admindashboard'),
    path('accounts/tableauboardstatistique/', views.home_tableauboardstatistique, name='tableauboardstatistique'),
    path('statistiques/tableauboardstatistique/', views.notifications_tableauboardstatistique, name='notifications_tableauboardstatistique'),



    # Enfants menacés
    path('accounts/child/new/', views.child_create, name='child_create'),
    path('child/update/<int:pk>/', views.child_update, name='child_update'),
    path('child/delete/<int:pk>/', views.child_delete, name='child_delete'),
    path('child/<int:child_id>/', views.child_detail, name='child_detail'),  # ✅ Détails enfant menacé
    path('child/menaced/<int:child_id>/', views.child_menaced_detail, name='child_menaced_detail'), 
    path('enfant/delinquent/<int:enfant_id>/', views.enfant_delinquent_detail, name='enfant_delinquent_detail'),
    path("child/<int:child_id>/send-email/", views.send_child_by_email, name="send_child_by_email"),
    path('accounts/children/institutions/', views.child_list_institutions, name='child_list_institutions'),
    path('accounts/export_children_excel_institution/', views.export_children_excel_institution, name='export_children_excel_institution'),
    path('children/', views.recherche_child_list, name='recherche_child_list'),
    path('investigation/search/', views.recherche_investigation_list, name='recherche_investigation_list'),
    path('children/unmarried/', views.unmarried_children_list, name='unmarried_children_list'),
    path('foreign-children/', views.foreign_child_list, name='foreign_child_list'),
    path('child/<int:child_id>/set-status/', views.set_child_status, name='set_child_status'),
   
    
    # ==================== SOCIAL FILE PDF (details enfants) ====================
    path('enfant/<int:child_id>/social-file-pdf/', views.download_social_file_pdf, name='download_social_file_pdf'),

    # Notifications
    path("notification/new/<int:child_id>/", views.new_notification, name="new_notification"),
    path('notification/list/<int:child_id>/', views.list_notification, name='list_notification'),
    path('notification/update/<int:notif_id>/', views.update_notification, name='update_notification'),
    
    # Enregistrement enfants (mixte)
    path('child/registration/', views.child_registration, name='child_registration'),
    
    # Listes spécifiques
    path("children/foreign/irregular/", views.foreign_irregular_children_list, name="foreign_irregular_children_list"),
    path("children/abandoned-outside-marriage/", views.children_abandoned_outside_marriage, name="children_abandoned_outside_marriage"),
    
    path('accounts/children/Investigation/', views.child_list_Investigation, name='child_list_Investigation'),
    path('investigation/create/<int:notif_id>/', views.create_investigation, name='create_investigation'),
    path('child/<int:child_id>/investigations/', views.investigation_list, name='investigation_list'),
    path('investigation/<int:investigation_id>/edit/', views.investigation_edit_form, name='investigation_edit_form'),
    
    path('threat-assessment/', views.child_list_threat_assessment, name='child_list_threat_assessment'),
    path('threat-assessment/create/<int:notif_id>/', views.create_threat_assessment, name='create_threat_assessment'),
    path('threat-assessment/list/<int:child_id>/', views.threat_assessment_list, name='threat_assessment_list'),
    path('threat-assessment/edit-form/<int:assessment_id>/', views.threat_assessment_edit_form, name='threat_assessment_edit_form'),
    path('threat-assessment/search/', views.recherche_threat_assessment_list, name='recherche_threat_assessment_list'),



    path('social-file/children/', views.child_list_social_file, name='child_list_social_file'),
    path('social-file/create/<int:notif_id>/', views.create_social_file, name='create_social_file'),
    path('social-file/list/<int:child_id>/', views.social_file_list, name='social_file_list'),


    path("powerbi/", views.dashboard_powerbi, name="dashboard_powerbi"),
  
    # AJAX
    path('get_state_prefix/', views.get_state_prefix, name='get_state_prefix'),  # ✅ Une seule fois

    # Password reset
    path('password_reset/', auth_views.PasswordResetView.as_view(
        template_name='account/password_reset.html',
        form_class=ArabicPasswordResetForm,
        email_template_name='account/password_reset_email.html',
        subject_template_name='account/password_reset_subject.txt',
        success_url='/password_reset/done/',
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='account/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='account/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='account/password_reset_complete.html'), name='password_reset_complete'),
    
    # Autres pages
    path('child-threatened/', views.child_threatened, name='child_threatened'),
    path('investigation/', views.investigation, name='investigation'),
    path('trafficking/', views.trafficking, name='trafficking'),

    # Gestion des enfants délinquants
    path('enfants/', views.enfant_list, name='enfant_list'),
    path('enfants/create/', views.enfant_create, name='enfant_create'),
    path('enfants/update/<int:pk>/', views.enfant_update, name='enfant_update'),
    path('enfants/delete/<int:pk>/', views.enfant_delete, name='enfant_delete'),
    path('enfant/<int:enfant_id>/detail/', views.enfant_delinquent_detail, name='enfant_delinquent_detail'),  # ✅ Optionnel
    
     # production
    path("enfants/<int:enfant_id>/demande_production/", views.production_request, name="production_request"),
    path("enfants/<int:enfant_id>/demandes/", views.production_request_list, name="production_request_list"),
    path("production-request/<int:pk>/edit/", views.production_request_edit, name="production_request_edit"),    
    path("enfants/<int:enfant_id>/<int:notification_id>/production/", views.production, name="production"),
    path("enfants/<int:enfant_id>/<int:notification_id>/production_juridique/", views.production_judicial, name="production_judicial"),
    path("production-request/<int:pk>/resultat/",views.resultat_production_request,name="resultat_production_request"),
    
 # ==================== PRODUCTION JUDICIAL ====================
    path('production/', views.production, name='production'),
    path('production/list-notifications/', views.production_list_notification_production, name='production_list_notification'),
    path('production/notifications/production/',views.production_list_notification_production,name='production_list_notification_production'),
    path('notifications/production/list/', views.production_list_notification_production, name='list_notifications_production'),
    path('production-requests/all/', views.all_production_requests, name='all_production_requests'),

    # Social files
    path("enfants/<int:enfant_id>/social_file/", views.social_file, name="social_file"),
    
    # Recherche
    path('recherche-enfants/', views.recherche_enfants, name='recherche_enfants'),
    
    # Interventions
    path("interventions/<int:enfant_id>/", views.intervention_list, name="intervention_list"),
    path("intervention/create/<int:enfant_id>/", views.intervention_create, name="intervention_create"),
    path("intervention/edit/<int:id>/", views.intervention_edit, name="intervention_edit"),
    path("intervention/delete/<int:id>/", views.intervention_delete, name="intervention_delete"),
    
    # Central dashboards
    path('central/enfants/menaces/', views.central_enfants_menaces, name='central_enfants_menaces'),
    path('central/enfants/juveniles/', views.central_enfants_juveniles, name='central_enfants_juveniles'),
    path('enfants/etrangers/', views.central_enfants_etrangers, name='central_enfants_etrangers'),
    path('enfants-etrangers/delete/<int:pk>/', views.delete_enfant_etranger, name="delete_enfant_etranger"),
    path('enfants/hors-mariage/', views.central_enfants_hors_mariage, name='central_enfants_hors_mariage'),
    
    # Suppressions (central)
    path('central/enfants/menaces/delete/<int:pk>/', views.enfant_menace_delete, name='enfant_menace_delete'),
    path('central/enfants/juveniles/delete/<int:pk>/', views.enfant_juvenile_delete, name='enfant_juvenile_delete'),
    path('enfants/hors-mariage/delete/<int:pk>/', views.enfant_hors_mariage_delete, name='enfant_hors_mariage_delete'),


    path(
        "export-word/",
        views.export_word,
        name="export_word"
    ),


# Ajoutez ces URLs si ce n'est pas déjà fait
    path('dashboard/echarts/', views.echarts_dashboard, name='echarts_dashboard'),
    path('dashboard/powerbi/', views.dashboard_powerbi, name='dashboard_powerbi'),

       # ==================== MESURES CONVENTIONNELLES ====================
    path('mesure-convenue/list/', views.mesure_convenue_list, name='mesure_convenue_list'),
    path('mesure-convenue/create/<int:child_id>/<int:notif_id>/', views.mesure_convenue_create, name='mesure_convenue_create'),
    path('mesure-convenue/edit/<int:pk>/', views.mesure_convenue_edit, name='mesure_convenue_edit'),
    path('mesure-convenue/delete/<int:pk>/', views.mesure_convenue_delete, name='mesure_convenue_delete'),
    path('mesure-convenue/followup/<int:pk>/', views.mesure_convenue_update_followup, name='mesure_convenue_update_followup'),
    path('mesure-convenue-update-status/<int:pk>/', views.mesure_convenue_update_status_ajax, name='mesure_convenue_update_status_ajax'),
    
        # ==================== MESURES URGENTES ====================
    path('mesure-urgente/list/', views.mesure_urgente_list_all, name='mesure_urgente_list'),
    path('mesure-urgente/list/<int:child_id>/', views.mesure_urgente_list, name='mesure_urgente_list_by_child'),
    path('mesure-urgente/create/<int:child_id>/<int:notif_id>/', views.mesure_urgente_create, name='mesure_urgente_create'),
    path('mesure-urgente/edit/<int:pk>/', views.mesure_urgente_edit, name='mesure_urgente_edit'),
    path('mesure-urgente/delete/<int:pk>/', views.mesure_urgente_delete, name='mesure_urgente_delete'),

    path('trafficking/list/', views.trafficking_notification_list, name='trafficking_notification_list'),
    path('trafficking/create/<int:child_id>/', views.trafficking_notification_create, name='trafficking_notification_create'),
    path('trafficking/detail/<int:pk>/', views.trafficking_notification_detail, name='trafficking_notification_detail'),
    path('trafficking/complete/<int:notification_id>/', views.trafficking_notification_complete, name='trafficking_notification_complete'),
    path('trafficking/edit/<int:pk>/', views.trafficking_notification_edit, name='trafficking_notification_edit'),
    path('trafficking/delete/<int:pk>/', views.trafficking_notification_delete, name='trafficking_notification_delete'),

    path('enfant/<int:enfant_id>/delinquent-pdf/', views.download_enfant_delinquent_pdf, name='download_enfant_delinquent_pdf'),


    path(
    "enfant/suivi/",
    views.liste_enfants_suivi,
    name="liste_enfants_suivi"
    ),
    path(
        'enfant/<int:child_id>/ajouter-suivi/',
        views.ajouter_suivi,
        name='ajouter_suivi'
    ),

    path(
        'enfant/<int:child_id>/suivi/<int:suivi_id>/resume/',
        views.resume_suivi,
        name='resume_suivi'
    ),
]