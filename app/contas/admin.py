from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from contas.models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'first_name', 'last_name', 'cpf', 'papel', 'apelido_locucao', 'telefone', 'is_staff')
    list_filter = ('papel', 'is_staff', 'is_active', 'estado')
    search_fields = ('username', 'first_name', 'last_name', 'cpf', 'apelido_locucao', 'email')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Dados Vaquejada QIRO', {
            'fields': ('cpf', 'papel', 'apelido_locucao', 'telefone', 'cidade', 'estado', 'foto_perfil')
        }),
    )
