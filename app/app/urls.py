"""
URL configuration for app project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('contas.urls')),
    path('eventos/', include('eventos.urls')),
    path('pista/', include('pista.urls')),
    path('senhas/', include('senhas.urls')),
    path('publico/', include('publico.urls')),
]
