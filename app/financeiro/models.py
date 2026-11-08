import uuid
from django.db import models
from django.conf import settings
from senhas.models import SenhaInscricao


class Transacao(models.Model):
    class MetodoPagamento(models.TextChoices):
        PIX = 'PIX', 'Pix'
        CARTAO = 'CARTAO', 'Cartão'
        DINHEIRO = 'DINHEIRO', 'Dinheiro na Secretaria'

    class StatusPagamento(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PAGO = 'PAGO', 'Pago / Confirmado'
        CANCELADO = 'CANCELADO', 'Cancelado'
        ESTORNADO = 'ESTORNADO', 'Estornado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    senha = models.ForeignKey(SenhaInscricao, on_delete=models.CASCADE, related_name='transacoes')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transacoes_pagas')
    valor_base = models.DecimalField(max_digits=10, decimal_places=2)
    valor_adicional_tv = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=MetodoPagamento.choices, default=MetodoPagamento.PIX)
    status = models.CharField(max_length=20, choices=StatusPagamento.choices, default=StatusPagamento.PENDENTE, db_index=True)
    comprovante_id = models.CharField(max_length=100, blank=True)
    pago_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transação Financeira'
        verbose_name_plural = 'Transações Financeiras'
        ordering = ['-criado_em']

    def __str__(self):
        return f"Transação #{self.id} - Senha #{self.senha.numero_senha} (R$ {self.valor_total})"
