import uuid
from django.db import models
from django.conf import settings
from eventos.models import Evento
from competidores.models import Animal


class Categoria(models.Model):
    class TipoCategoria(models.TextChoices):
        ASPIRANTE = 'ASPIRANTE', 'Aspirante'
        AMADOR = 'AMADOR', 'Amador'
        ABERTA = 'ABERTA', 'Aberta'
        PROFISSIONAL = 'PROFISSIONAL', 'Profissional'
        FEMININA = 'FEMININA', 'Feminina'
        MASTER = 'MASTER', 'Master'
        JOVEM = 'JOVEM', 'Jovem / Mirim'
        DERBY = 'DERBY', 'Derby / Potro'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='categorias')
    tipo = models.CharField(max_length=30, choices=TipoCategoria.choices)
    nome_exibicao = models.CharField(max_length=100, help_text="Ex: Mapa Aberta")
    
    # Valores
    valor_senha = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor unitário (ex: 410.00)")
    valor_boi_tv = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="Valor do opcional de Prêmio Extra + Boi na TV"
    )
    limite_senhas = models.PositiveIntegerField(default=100)
    
    # Regras de Pista
    bois_classificatoria = models.PositiveSmallIntegerField(
        default=2,
        help_text="Quantidade de bois corridos na fase classificatória"
    )
    pontos_para_bater = models.PositiveSmallIntegerField(
        default=20,
        help_text="Pontos necessários para bater a senha e ir para a disputa (ex: 20 pts)"
    )
    ordem_apresentacao = models.PositiveSmallIntegerField(default=1)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Categoria do Evento'
        verbose_name_plural = 'Categorias do Evento'
        unique_together = ('evento', 'tipo')
        ordering = ['ordem_apresentacao', 'nome_exibicao']

    def __str__(self):
        return f"{self.nome_exibicao} - {self.evento.nome}"


class SenhaInscricao(models.Model):
    class StatusSenha(models.TextChoices):
        DISPONIVEL = 'DISPONIVEL', 'Disponível no Mapa'
        RESERVADA = 'RESERVADA', 'Reservada no Checkout'
        PAGA = 'PAGA', 'Paga / Confirmada'
        NA_BOIADA = 'NA_BOIADA', 'Na Boiada / No Brete'
        NA_PISTA = 'NA_PISTA', 'Na Pista Correndo'
        BATIDA = 'BATIDA', 'Senha Batida (Classificada p/ Disputa)'
        ELIMINADA = 'ELIMINADA', 'Eliminada da Matriz (Levou Zero)'
        DESCLASSIFICADA = 'DESCLASSIFICADA', 'Desclassificada por Infração'

    class OrigemVenda(models.TextChoices):
        ONLINE = 'ONLINE', 'Venda Online (Site/App)'
        BALCAO_PRESENCIAL = 'BALCAO_PRESENCIAL', 'Secretaria Presencial (Parque)'

    class FormaPagamento(models.TextChoices):
        PIX = 'PIX', 'Pix'
        DINHEIRO = 'DINHEIRO', 'Dinheiro em Espécie'
        CARTAO_CREDITO = 'CARTAO_CREDITO', 'Cartão de Crédito'
        CARTAO_DEBITO = 'CARTAO_DEBITO', 'Cartão de Débito'
        CORTESIA = 'CORTESIA', 'Cortesia / Convite da Diretoria'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo_autenticidade = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True, help_text="Código único de validação via QR Code na cancela/portaria")
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='senhas')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='senhas')
    numero_senha = models.PositiveIntegerField(db_index=True)
    dia_corrida = models.CharField(max_length=30, blank=True, help_text="Ex: Quinta, Sexta, Sábado")
    
    # Kit / Casadinha
    eh_kit = models.BooleanField(default=False, help_text="Inscrição em Kit / Casadinha")
    numero_segunda_senha = models.PositiveIntegerField(null=True, blank=True, help_text="Número da 2ª senha do Kit (ex: senha + 100)")

    # Atletas e Animais
    vaqueiro_puxador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='inscricoes_como_puxador'
    )
    cavalo_puxador = models.ForeignKey(
        Animal,
        on_delete=models.PROTECT,
        related_name='inscricoes_cavalo_puxador'
    )
    vaqueiro_esteireiro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='inscricoes_como_esteira'
    )
    cavalo_esteireiro = models.ForeignKey(
        Animal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='inscricoes_cavalo_esteira'
    )
    
    # Cartão da Inscrição
    representacao = models.CharField(max_length=150, help_text="Ex: Super Copa de Vaquejada - Geral")
    tem_boi_tv = models.BooleanField(default=False, help_text="Contratou Prêmio Extra + Boi na TV")
    
    # Venda, Caixa e Secretaria
    origem_venda = models.CharField(
        max_length=25,
        choices=OrigemVenda.choices,
        default=OrigemVenda.ONLINE,
        help_text="Canal onde a inscrição foi efetuada"
    )
    forma_pagamento = models.CharField(
        max_length=25,
        choices=FormaPagamento.choices,
        default=FormaPagamento.PIX,
        help_text="Método de liquidação da inscrição"
    )
    operador_secretaria = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='senhas_vendidas_balcao',
        help_text="Operador da secretaria física que realizou o atendimento"
    )
    reservada_ate = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Data/hora limite de retenção temporária para pagamento Pix"
    )

    # Dinâmica de Rodízio na Pista
    status = models.CharField(max_length=25, choices=StatusSenha.choices, default=StatusSenha.PAGA, db_index=True)
    rodizio_bloco = models.PositiveIntegerField(default=1, help_text="Bloco do rodízio (ex: 1, 2, 3...)")
    ordem_fila = models.PositiveIntegerField(default=0, help_text="Ordem de chamada na fila")
    total_pontos = models.PositiveIntegerField(default=0)
    
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pago_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Senha / Inscrição'
        verbose_name_plural = 'Senhas / Inscrições'
        unique_together = ('evento', 'categoria', 'numero_senha')
        ordering = ['categoria', 'numero_senha']

    def __str__(self):
        return f"Senha #{self.numero_senha} ({self.categoria.nome_exibicao}) - {self.vaqueiro_puxador.apelido_locucao or self.vaqueiro_puxador.get_full_name()}"

    @property
    def is_expirada(self):
        from django.utils import timezone
        if self.status == self.StatusSenha.RESERVADA and self.reservada_ate:
            return timezone.now() > self.reservada_ate
        return False
