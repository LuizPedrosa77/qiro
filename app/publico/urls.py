from django.urls import path
from publico import views

urlpatterns = [
    path('ao-vivo/', views.telao_ao_vivo, name='telao_ao_vivo'),
]
