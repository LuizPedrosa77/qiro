from django.contrib import admin
from auditoria.models import AuditoriaLog


@admin.register(AuditoriaLog)
class AuditoriaLogAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'usuario', 'acao', 'entidade', 'registro_id', 'ip_origem')
    list_filter = ('acao', 'entidade', 'criado_em')
    search_fields = ('registro_id', 'observacao', 'usuario__username')
    readonly_fields = ('criado_em', 'usuario', 'acao', 'entidade', 'registro_id', 'ip_origem', 'dados_anteriores', 'dados_novos', 'observacao')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
