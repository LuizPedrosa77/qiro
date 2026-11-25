from django.urls import path
from senhas import views

urlpatterns = [
    path('mapa/', views.mapa_senhas, name='mapa_senhas'),
    path('finalizar-inscricao/', views.finalizar_inscricao, name='finalizar_inscricao'),
    path('api/buscar-vaqueiro/', views.api_buscar_vaqueiro, name='api_buscar_vaqueiro'),
    path('recibo/<uuid:codigo_autenticidade>/', views.recibo_balcao, name='recibo_balcao'),
    path('admin/zerar-senhas/', views.admin_zerar_senhas, name='admin_zerar_senhas'),
    path('api/testar-webhook/', views.api_testar_webhook_n8n, name='api_testar_webhook_n8n'),
    path('integracoes/webhook/', views.webhook_central, name='webhook_central'),
]
