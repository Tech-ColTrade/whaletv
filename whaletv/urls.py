from django.urls import path

from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # CRUD de televisores
    path('televisores/', views.televisor_list, name='televisor_list'),
    path('televisores/sincronizar-todos/', views.televisor_sincronizar_todos, name='televisor_sincronizar_todos'),
    path('sync/iniciar/', views.sync_iniciar, name='sync_iniciar'),
    path('validacion/iniciar/', views.validacion_iniciar, name='validacion_iniciar'),
    path('sync/cambios/', views.sync_cambios, name='sync_cambios'),
    path('sync/cancelar/', views.sync_cancelar, name='sync_cancelar'),
    path('sync/<int:pk>/cancelar/', views.sync_cancelar, name='sync_cancelar_job'),
    path('sync/<int:pk>/', views.sync_progreso, name='sync_progreso'),
    path('sync/<int:pk>/estado/', views.sync_progreso_api, name='sync_progreso_api'),
    path('sync/<int:pk>/exportar/', views.sync_job_export, name='sync_job_export'),
    path('sincronizaciones/', views.registro_sync_list, name='registro_sync_list'),
    path('sincronizaciones/exportar/', views.registro_sync_export, name='registro_sync_export'),
    path('pincodes/', views.pincode_list, name='pincode_list'),
    path('pincodes/exportar/', views.pincode_export, name='pincode_export'),
    path('detailtv/<str:mac>/', views.registro_sync_tv, name='registro_sync_tv'),
    path('detailtv/<str:mac>/sincronizaciones/', views.registro_sync_tv_records, name='registro_sync_tv_records'),
    path('detailtv/<str:mac>/pincodes/', views.registro_sync_tv_pincodes, name='registro_sync_tv_pincodes'),
    path('detailtv/<str:mac>/pincodes/exportar/', views.registro_sync_tv_pincodes_export, name='registro_sync_tv_pincodes_export'),
    path('detailtv/<str:mac>/exportar/', views.registro_sync_tv_export, name='registro_sync_tv_export'),
    path('detailtv/<str:mac>/habilitar/', views.habilitar_manual, name='habilitar_manual'),
    path('detailtv/<str:mac>/habilitar/sincronizar/', views.habilitar_sincronizar, name='habilitar_sincronizar'),
    path('televisores/importar/', views.televisor_import, name='televisor_import'),
    path('televisores/plantilla/', views.televisor_plantilla, name='televisor_plantilla'),
    path('televisores/nuevo/', views.televisor_create, name='televisor_create'),
    path('televisores/<int:pk>/editar/', views.televisor_update, name='televisor_update'),
    path('televisores/<int:pk>/validar/', views.televisor_validar, name='televisor_validar'),
    path('televisores/<int:pk>/sincronizar/', views.televisor_sincronizar, name='televisor_sincronizar'),
    path('televisores/<int:pk>/historico/', views.televisor_historico, name='televisor_historico'),

    # Inhabilitaciones
    path('inhabilitaciones/importar/', views.inhabilitacion_import, name='inhabilitacion_import'),
    path('inhabilitaciones/plantilla/', views.inhabilitacion_plantilla, name='inhabilitacion_plantilla'),
    path('inhabilitaciones/<int:pk>/eliminar/', views.inhabilitacion_delete, name='inhabilitacion_delete'),
]
