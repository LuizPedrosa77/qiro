from django.urls import path
from eventos import views

urlpatterns = [
    path('cadastrar/', views.cadastrar_vaquejada, name='cadastrar_vaquejada'),
]
