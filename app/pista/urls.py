from django.urls import path
from pista import views

urlpatterns = [
    path('locutor/', views.painel_locutor, name='painel_locutor'),
    path('juiz/', views.painel_juiz, name='painel_juiz'),
    path('julgamento/', views.registrar_julgamento, name='registrar_julgamento'),
    path('chat/', views.enviar_mensagem_chat, name='enviar_mensagem_chat'),
    path('status-atual/', views.status_atual, name='status_atual'),
]
