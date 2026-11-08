from django.contrib import admin
from senhas.models import Categoria, SenhaInscricao


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nome_exibicao', 'evento', 'tipo', 'valor_senha', 'valor_boi_tv', 'limite_senhas', 'pontos_para_bater', 'ativo')
    list_filter = ('evento', 'tipo', 'ativo')
    search_fields = ('nome_exibicao', 'evento__nome')


@admin.register(SenhaInscricao)
class SenhaInscricaoAdmin(admin.ModelAdmin):
    list_display = ('numero_senha', 'categoria', 'vaqueiro_puxador', 'cavalo_puxador', 'vaqueiro_esteireiro', 'cavalo_esteireiro', 'status', 'total_pontos', 'tem_boi_tv', 'dia_corrida')
    list_filter = ('status', 'categoria__evento', 'categoria', 'tem_boi_tv', 'dia_corrida')
    search_fields = ('numero_senha', 'vaqueiro_puxador__first_name', 'vaqueiro_puxador__apelido_locucao', 'cavalo_puxador__nome', 'representacao')
    ordering = ('categoria', 'numero_senha')
