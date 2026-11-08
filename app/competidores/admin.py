from django.contrib import admin
from competidores.models import Haras, Animal


@admin.register(Haras)
class HarasAdmin(admin.ModelAdmin):
    list_display = ('nome', 'proprietario', 'cidade', 'estado', 'ativo')
    search_fields = ('nome', 'proprietario__username', 'proprietario__first_name', 'cidade')
    list_filter = ('estado', 'ativo')


@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'registro_abqm', 'funcao', 'raca', 'proprietario', 'haras', 'ativo')
    list_filter = ('funcao', 'raca', 'ativo')
    search_fields = ('nome', 'registro_abqm', 'proprietario__first_name', 'proprietario__username')
