from django.urls import path
from senhas import views

urlpatterns = [
    path('mapa/', views.mapa_senhas, name='mapa_senhas'),
    path('finalizar-inscricao/', views.finalizar_inscricao, name='finalizar_inscricao'),
]
