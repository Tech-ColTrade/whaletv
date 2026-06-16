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
    path('sync/cambios/', views.sync_cambios, name='sync_cambios'),
    path('sync/cancelar/', views.sync_cancelar, name='sync_cancelar'),
    path('sync/<int:pk>/cancelar/', views.sync_cancelar, name='sync_cancelar_job'),
    path('sync/<int:pk>/', views.sync_progreso, name='sync_progreso'),
    path('sync/<int:pk>/estado/', views.sync_progreso_api, name='sync_progreso_api'),
    path('sincronizaciones/', views.registro_sync_list, name='registro_sync_list'),
    path('pincodes/', views.pincode_list, name='pincode_list'),
    path('detailtv/<str:mac>/', views.registro_sync_tv, name='registro_sync_tv'),
    path('detailtv/<str:mac>/sincronizaciones/', views.registro_sync_tv_records, name='registro_sync_tv_records'),
    path('detailtv/<str:mac>/pincodes/', views.registro_sync_tv_pincodes, name='registro_sync_tv_pincodes'),
    path('detailtv/<str:mac>/pincodes/exportar/', views.registro_sync_tv_pincodes_export, name='registro_sync_tv_pincodes_export'),
    path('detailtv/<str:mac>/exportar/', views.registro_sync_tv_export, name='registro_sync_tv_export'),
    path('detailtv/<str:mac>/desbloquear/', views.desbloquear_manual, name='desbloquear_manual'),
    path('detailtv/<str:mac>/desbloquear/sincronizar/', views.desbloquear_sincronizar, name='desbloquear_sincronizar'),
    path('televisores/importar/', views.televisor_import, name='televisor_import'),
    path('televisores/plantilla/', views.televisor_plantilla, name='televisor_plantilla'),
    path('televisores/nuevo/', views.televisor_create, name='televisor_create'),
    path('televisores/<int:pk>/editar/', views.televisor_update, name='televisor_update'),
    path('televisores/<int:pk>/eliminar/', views.televisor_delete, name='televisor_delete'),
    path('televisores/<int:pk>/validar/', views.televisor_validar, name='televisor_validar'),
    path('televisores/<int:pk>/sincronizar/', views.televisor_sincronizar, name='televisor_sincronizar'),
    path('televisores/<int:pk>/historico/', views.televisor_historico, name='televisor_historico'),

    # Facturas
    path('facturas/importar/', views.factura_import, name='factura_import'),
    path('facturas/plantilla/', views.factura_plantilla, name='factura_plantilla'),
    path('facturas/<int:pk>/editar/', views.factura_update, name='factura_update'),
    path('facturas/<int:pk>/pagar/', views.factura_toggle, name='factura_toggle'),
    path('facturas/<int:pk>/eliminar/', views.factura_delete, name='factura_delete'),
]
