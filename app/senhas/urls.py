from django.urls import path
from senhas import views

urlpatterns = [
    path('mapa/', views.mapa_senhas, name='mapa_senhas'),
    path('finalizar-inscricao/', views.finalizar_inscricao, name='finalizar_inscricao'),
    path('api/buscar-vaqueiro/', views.api_buscar_vaqueiro, name='api_buscar_vaqueiro'),
    path('recibo/<uuid:codigo_autenticidade>/', views.recibo_balcao, name='recibo_balcao'),
]
