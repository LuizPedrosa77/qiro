"""
URL configuration for app project.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda request: redirect('/pista/locutor/')),
    path('pista/', include('pista.urls')),
    path('senhas/', include('senhas.urls')),
    path('publico/', include('publico.urls')),
]
