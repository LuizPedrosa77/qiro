"""
URL configuration for app project.
"""
from django.contrib import admin
from django.urls import path, include
from eventos.views import lista_vaquejadas, coordenador_dashboard
from publico.views import tv_vaqueiro

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('contas.urls')),
    path('vaquejadas/', lista_vaquejadas, name='lista_vaquejadas'),
    path('tv-vaqueiro/', tv_vaqueiro, name='tv_vaqueiro'),
    path('coordenador/', coordenador_dashboard, name='coordenador_dashboard'),
    path('eventos/', include('eventos.urls')),
    path('pista/', include('pista.urls')),
    path('senhas/', include('senhas.urls')),
    path('publico/', include('publico.urls')),
]
