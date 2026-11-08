from django.contrib import admin
from pista.models import BoiPassada, ChatPista


@admin.register(BoiPassada)
class BoiPassadaAdmin(admin.ModelAdmin):
    list_display = ('senha', 'numero_boi', 'fase', 'julgamento_juiz', 'julgamento_locutor', 'pontos_obtidos', 'data_hora')
    list_filter = ('fase', 'julgamento_juiz', 'julgamento_locutor')
    search_fields = ('senha__numero_senha', 'senha__vaqueiro_puxador__first_name')
    ordering = ('-data_hora',)


@admin.register(ChatPista)
class ChatPistaAdmin(admin.ModelAdmin):
    list_display = ('evento', 'remetente', 'tipo', 'mensagem', 'criado_em', 'lido')
    list_filter = ('tipo', 'lido', 'evento')
    search_fields = ('mensagem', 'remetente__username', 'remetente__apelido_locucao')
    ordering = ('-criado_em',)
