from django.contrib import admin
from financeiro.models import Transacao


@admin.register(Transacao)
class TransacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'senha', 'metodo', 'valor_total', 'status', 'criado_em')
    list_filter = ('metodo', 'status', 'criado_em')
    search_fields = ('comprovante_id', 'senha__numero_senha')
