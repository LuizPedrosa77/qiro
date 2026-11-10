from django.urls import path
from contas import views

urlpatterns = [
    path('', views.tela_inicial, name='tela_inicial'),
    path('cliente/login/', views.cliente_login, name='cliente_login'),
    path('cliente/cadastro/', views.cliente_cadastro, name='cliente_cadastro'),
    path('cliente/logout/', views.cliente_logout, name='cliente_logout'),
    path('cliente/secretaria/', views.cliente_secretaria, name='cliente_secretaria'),
    path('cliente/comprar/', views.cliente_comprar, name='cliente_comprar'),
    path('equipe/login/', views.equipe_login, name='equipe_login'),
]
