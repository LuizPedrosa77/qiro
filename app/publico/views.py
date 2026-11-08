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
