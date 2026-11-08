import uuid
from django.db import models
from django.conf import settings


class AuditoriaLog(models.Model):
    class TipoAcao(models.TextChoices):
        CRIACAO = 'CRIACAO', 'Criação'
        EDICAO = 'EDICAO', 'Edição de Dados'
        EXCLUSAO = 'EXCLUSAO', 'Exclusão'
        JULGAMENTO = 'JULGAMENTO', 'Julgamento de Pista'
        DESCLASSIFICACAO = 'DESCLASSIFICACAO', 'Desclassificação'
        FINANCEIRO = 'FINANCEIRO', 'Movimentação Financeira'
        RACHA = 'RACHA', 'Acordo de Racha'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='logs_auditoria')
    acao = models.CharField(max_length=30, choices=TipoAcao.choices, db_index=True)
    entidade = models.CharField(max_length=50, db_index=True, help_text="Tabela ou modelo auditado")
    registro_id = models.CharField(max_length=100, db_index=True)
    ip_origem = models.GenericIPAddressField(null=True, blank=True)
    dados_anteriores = models.JSONField(null=True, blank=True)
    dados_novos = models.JSONField(null=True, blank=True)
    observacao = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-criado_em']

    def __str__(self):
        return f"[{self.criado_em:%d/%m/%Y %H:%M}] {self.acao} em {self.entidade} por {self.usuario}"
