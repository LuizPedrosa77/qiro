import uuid
from django.db import models
from django.conf import settings
from eventos.models import Evento
from senhas.models import SenhaInscricao


class BoiPassada(models.Model):
    class Fase(models.TextChoices):
        CLASSIFICATORIA = 'CLASSIFICATORIA', 'Classificatória'
        REPESCAGEM = 'REPESCAGEM', 'Repescagem / Teimosinha'
        DISPUTA = 'DISPUTA', 'Disputa Final (Mata-Mata)'

    class JulgamentoJuiz(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Aguardando Corrida'
        VALEU_BOI = 'VALEU_BOI', 'Valeu Boi (✓ Verde - 10 pts)'
        BOI_DE_TV = 'BOI_DE_TV', 'Boi de TV / Alternativa'
        RETORNO = 'RETORNO', 'Retorno (R Amarelo - Boi Devolvido)'
        ZERO = 'ZERO', 'Zero (✗ Vermelho - Desclassificado)'

    class JulgamentoLocutor(models.TextChoices):
        NENHUM = 'NENHUM', 'Sem Intervenção'
        RETORNO = 'RETORNO', 'Retorno (R)'
        ZERO = 'ZERO', 'Zero (X)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    senha = models.ForeignKey(SenhaInscricao, on_delete=models.CASCADE, related_name='passadas')
    fase = models.CharField(max_length=25, choices=Fase.choices, default=Fase.CLASSIFICATORIA)
    numero_boi = models.PositiveSmallIntegerField(default=1, help_text="1º boi, 2º boi, 3º boi...")
    
    # Decisões de Julgamento
    julgamento_juiz = models.CharField(
        max_length=25,
        choices=JulgamentoJuiz.choices,
        default=JulgamentoJuiz.PENDENTE,
        db_index=True
    )
    julgamento_locutor = models.CharField(
        max_length=25,
        choices=JulgamentoLocutor.choices,
        default=JulgamentoLocutor.NENHUM
    )
    pontos_obtidos = models.PositiveSmallIntegerField(default=0)
    
    juiz = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='julgamentos_realizados'
    )
    locutor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locucoes_realizadas'
    )
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Passada de Boi'
        verbose_name_plural = 'Passadas de Boi'
        ordering = ['senha', 'numero_boi']

    def __str__(self):
        return f"Boi #{self.numero_boi} da Senha #{self.senha.numero_senha} -> {self.get_julgamento_juiz_display()}"


class ChatPista(models.Model):
    class TipoMensagem(models.TextChoices):
        RAPIDO_LOCUTOR = 'RAPIDO_LOCUTOR', 'Botão Rápido do Locutor'
        LIVRE = 'LIVRE', 'Mensagem Livre de Texto'
        ALERTA_SECRETARIA = 'ALERTA_SECRETARIA', 'Alerta da Secretaria'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='mensagens_chat')
    remetente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='mensagens_enviadas'
    )
    tipo = models.CharField(max_length=25, choices=TipoMensagem.choices, default=TipoMensagem.LIVRE)
    mensagem = models.CharField(max_length=255)
    senha_referencia = models.ForeignKey(
        SenhaInscricao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mensagens_chat'
    )
    lido = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Mensagem da Pista'
        verbose_name_plural = 'Mensagens da Pista'
        ordering = ['criado_em']

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.remetente}: {self.mensagem}"
