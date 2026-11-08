from django.contrib import admin
from eventos.models import Parque, Evento


@admin.register(Parque)
class ParqueAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cidade', 'estado', 'responsavel', 'telefone', 'ativo')
    search_fields = ('nome', 'cidade', 'estado', 'responsavel')
    list_filter = ('estado', 'ativo')


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'parque', 'data_inicio', 'data_fim', 'status', 'exige_gta', 'permite_casadinha')
    list_filter = ('status', 'exige_gta', 'permite_casadinha', 'data_inicio')
    search_fields = ('nome', 'parque__nome')
