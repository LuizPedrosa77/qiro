from django.urls import path
from eventos import views

urlpatterns = [
    path('', views.lista_vaquejadas, name='lista_vaquejadas'),
    path('cadastrar/', views.cadastrar_vaquejada, name='cadastrar_vaquejada'),
    path('coordenador/', views.coordenador_dashboard, name='coordenador_dashboard'),
]
