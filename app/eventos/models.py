import uuid
from django.db import models
from django.conf import settings


class Parque(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150, help_text="Ex: Parque Millany")
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    cnpj = models.CharField(max_length=20, blank=True)
    responsavel = models.CharField(max_length=150, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Parque de Vaquejada'
        verbose_name_plural = 'Parques de Vaquejada'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.estado}"


class Evento(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        INSCRICOES = 'INSCRICOES', 'Inscrições Abertas'
        EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento na Pista'
        DISPUTA_FINAL = 'DISPUTA_FINAL', 'Disputa Final (Mata-Mata)'
        ENCERRADO = 'ENCERRADO', 'Encerrado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parque = models.ForeignKey(Parque, on_delete=models.PROTECT, related_name='eventos')
    nome = models.CharField(max_length=200, help_text="Ex: 1ª Grande Vaquejada Parque Millany")
    edicao = models.CharField(max_length=50, blank=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    premiacao_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.INSCRICOES, db_index=True)
    
    # Cartaz oficial, chancela e programação
    cartaz = models.ImageField(upload_to='cartazes/', blank=True, null=True, help_text="Arte oficial ou foto do parque")
    banner_url = models.URLField(max_length=500, blank=True, help_text="Link direto da imagem do cartaz/flyer")
    circuito_chancela = models.CharField(max_length=100, blank=True, default="Circuito Oficial", help_text="Ex: Campeonato Portal, Circuito PE/PB, ABQM")
    descricao = models.TextField(blank=True, help_text="Programação de shows e informações gerais")

    exige_gta = models.BooleanField(default=True, help_text="Exige conferência de GTA e sanidade animal")
    permite_casadinha = models.BooleanField(default=True, help_text="Permite pacotes promocionais de senhas casadas")
    organizador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='eventos_organizados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento de Vaquejada'
        verbose_name_plural = 'Eventos de Vaquejada'
        ordering = ['-data_inicio']

    def __str__(self):
        return f"{self.nome} ({self.parque.nome})"
