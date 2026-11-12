from django.shortcuts import render
from eventos.models import Evento
from senhas.models import SenhaInscricao


def telao_ao_vivo(request):
    """
    Painel do Telão / Ao Vivo para o público e telões de LED da pista.
    Exibe em tipografia gigante o conjunto em pista, julgamento dos bois e próximos da fila.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    
    conjunto_atual = SenhaInscricao.objects.filter(
        evento=evento,
        status=SenhaInscricao.StatusSenha.NA_PISTA
    ).first()

    proximos = SenhaInscricao.objects.filter(
        evento=evento,
        status__in=[SenhaInscricao.StatusSenha.PAGA, SenhaInscricao.StatusSenha.NA_BOIADA]
    ).exclude(id=conjunto_atual.id if conjunto_atual else None).order_by('ordem_fila', 'numero_senha')[:6]

    return render(request, 'publico/ao_vivo.html', {
        'evento': evento,
        'conjunto_atual': conjunto_atual,
        'proximos': proximos,
    })


def tv_vaqueiro(request):
    """
    Canal Oficial de Transmissão 24H — TV VAQUEIRO (Paywall & Assinatura R$ 39,90/mês).
    Exibe streaming ao vivo, grade de programação 24h, programas veterinários e planos.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    
    grade_programacao = [
        {'hora': '08:00 - 10:00', 'titulo': 'Medicina & Fisioterapia Equina', 'apresentador': 'Dr. Marcos Silva (Médico Veterinário)', 'tipo': 'Veterinária'},
        {'hora': '10:00 - 13:00', 'titulo': 'Bateria Classificatória — Categoria Aberta', 'apresentador': 'Transmissão Ao Vivo com Placar QIRO', 'tipo': 'Ao Vivo'},
        {'hora': '13:00 - 14:00', 'titulo': 'Reprise Histórica: Final da Vaquejada do Milhão', 'apresentador': 'Grandes Momentos da Vaquejada', 'tipo': 'Reprise'},
        {'hora': '14:00 - 19:00', 'titulo': 'Bateria Oficial — Amador e Aspirante', 'apresentador': 'Transmissão Ao Vivo com Placar QIRO', 'tipo': 'Ao Vivo'},
        {'hora': '19:00 - 20:30', 'titulo': 'Resenha dos Campeões & Bastidores dos Bretes', 'apresentador': 'Entrevistas e Análise Técnica', 'tipo': 'Especial'},
        {'hora': '20:30 - 00:00', 'titulo': 'Disputa Final (Mata-Mata) & Shows Musicais', 'apresentador': 'Transmissão Ao Vivo com Placar QIRO', 'tipo': 'Ao Vivo'},
    ]

    return render(request, 'publico/tv_vaqueiro.html', {
        'evento': evento,
        'grade_programacao': grade_programacao,
        'valor_mensal': '39,90',
    })
