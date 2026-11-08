import uuid
from django.db import models
from django.conf import settings


class Haras(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=150, help_text="Ex: Super Copa de Vaquejada / Haras Millany")
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='haras_propriedades'
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Haras / Equipe'
        verbose_name_plural = 'Haras e Equipes'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Animal(models.Model):
    class Funcao(models.TextChoices):
        PUXADOR = 'PUXADOR', 'Cavalo de Puxada'
        ESTEIRA = 'ESTEIRA', 'Cavalo de Esteira'
        AMBOS = 'AMBOS', 'Puxada e Esteira'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=120, help_text="Ex: Jeck Yease, King")
    registro_abqm = models.CharField(max_length=50, blank=True)
    funcao = models.CharField(max_length=20, choices=Funcao.choices, default=Funcao.PUXADOR)
    raca = models.CharField(max_length=50, default='Quarto de Milha')
    pelagem = models.CharField(max_length=50, blank=True)
    haras = models.ForeignKey(Haras, on_delete=models.SET_NULL, null=True, blank=True, related_name='plantel')
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='animais_proprios'
    )
    limite_senhas_por_evento = models.PositiveSmallIntegerField(
        default=2,
        help_text="Teto regulamentar de participações por evento para bem-estar animal"
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Animal (Cavalo)'
        verbose_name_plural = 'Animais (Cavalos)'
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} ({self.get_funcao_display()})"
