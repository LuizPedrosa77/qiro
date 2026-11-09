from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

from eventos.models import Evento
from senhas.models import SenhaInscricao
from pista.models import BoiPassada, ChatPista
from auditoria.models import AuditoriaLog


def painel_locutor(request):
    """
    Tela oficial do Locutor de Pista (Mockup Imagens 9, 10, 11).
    Permite apenas julgamento de Retorno ou Zero.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    
    conjunto_atual = SenhaInscricao.objects.filter(
        evento=evento,
        status=SenhaInscricao.StatusSenha.NA_PISTA
    ).first()

    proximos = SenhaInscricao.objects.filter(
        evento=evento,
        status__in=[SenhaInscricao.StatusSenha.PAGA, SenhaInscricao.StatusSenha.NA_BOIADA]
    ).exclude(id=conjunto_atual.id if conjunto_atual else None).order_by('ordem_fila', 'numero_senha')[:8]

    alertas = ChatPista.objects.filter(
        evento=evento,
        tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA
    ).order_by('-criado_em')[:5]

    chat_historico = ChatPista.objects.filter(
        evento=evento
    ).exclude(tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA).order_by('-criado_em')[:6]

    return render(request, 'pista/locutor.html', {
        'evento': evento,
        'conjunto_atual': conjunto_atual,
        'proximos': proximos,
        'alertas': alertas,
        'chat_historico': chat_historico,
        'is_juiz': False
    })


def painel_juiz(request):
    """
    Tela oficial do Juiz de Pista (Mockup Imagem 14).
    Possui os 4 julgamentos: Valeu, TV, Retorno e Zero.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    
    conjunto_atual = SenhaInscricao.objects.filter(
        evento=evento,
        status=SenhaInscricao.StatusSenha.NA_PISTA
    ).first()

    proximos = SenhaInscricao.objects.filter(
        evento=evento,
        status__in=[SenhaInscricao.StatusSenha.PAGA, SenhaInscricao.StatusSenha.NA_BOIADA]
    ).exclude(id=conjunto_atual.id if conjunto_atual else None).order_by('ordem_fila', 'numero_senha')[:8]

    alertas = ChatPista.objects.filter(
        evento=evento,
        tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA
    ).order_by('-criado_em')[:5]

    chat_historico = ChatPista.objects.filter(
        evento=evento
    ).exclude(tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA).order_by('-criado_em')[:6]

    return render(request, 'pista/juiz.html', {
        'evento': evento,
        'conjunto_atual': conjunto_atual,
        'proximos': proximos,
        'alertas': alertas,
        'chat_historico': chat_historico,
        'is_juiz': True
    })


@csrf_exempt
@require_POST
def registrar_julgamento(request):
    """
    Endpoint de alta velocidade para submissão de julgamento via Fetch/Ajax.
    Aplica as regras da transcrição do fundador:
    - Locutor só pode dar Retorno ou Zero.
    - Juiz pode dar Valeu, TV, Retorno ou Zero.
    - Se der Zero: a senha sai da matriz principal!
    """
    try:
        data = json.loads(request.body)
        senha_id = data.get('senha_id')
        numero_boi = int(data.get('numero_boi', 1))
        decisao = data.get('decisao')  # VALEU_BOI, BOI_DE_TV, RETORNO, ZERO
        origem = data.get('origem', 'JUIZ')

        senha = get_object_or_404(SenhaInscricao, id=senha_id)

        # Validação de autonomia do locutor
        if origem == 'LOCUTOR' and decisao not in ['RETORNO', 'ZERO']:
            return JsonResponse({'sucesso': False, 'erro': 'Locutor só pode dar Retorno ou Zero.'}, status=403)

        passada, _ = BoiPassada.objects.get_or_create(
            senha=senha,
            numero_boi=numero_boi,
            defaults={'fase': BoiPassada.Fase.CLASSIFICATORIA}
        )

        dados_anteriores = {
            'julgamento_juiz': passada.julgamento_juiz,
            'pontos': passada.pontos_obtidos,
            'status_senha': senha.status
        }

        if origem == 'LOCUTOR':
            passada.julgamento_locutor = decisao
            if decisao == 'ZERO':
                passada.julgamento_juiz = BoiPassada.JulgamentoJuiz.ZERO
                passada.pontos_obtidos = 0
                senha.status = SenhaInscricao.StatusSenha.ELIMINADA
            elif decisao == 'RETORNO':
                passada.julgamento_juiz = BoiPassada.JulgamentoJuiz.RETORNO
        else:
            passada.julgamento_juiz = decisao
            if decisao == 'VALEU_BOI':
                passada.pontos_obtidos = 10
                pontos_totais = sum(p.pontos_obtidos for p in senha.passadas.exclude(id=passada.id)) + 10
                senha.total_pontos = pontos_totais
                if pontos_totais >= senha.categoria.pontos_para_bater:
                    senha.status = SenhaInscricao.StatusSenha.BATIDA
            elif decisao == 'ZERO':
                passada.pontos_obtidos = 0
                senha.status = SenhaInscricao.StatusSenha.ELIMINADA
            elif decisao in ['BOI_DE_TV', 'RETORNO']:
                passada.pontos_obtidos = 0

        passada.save()
        senha.save()

        # Registro de Auditoria
        AuditoriaLog.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            acao=AuditoriaLog.TipoAcao.JULGAMENTO,
            entidade='BoiPassada',
            registro_id=str(passada.id),
            dados_anteriores=dados_anteriores,
            dados_novos={'julgamento': decisao, 'pontos': passada.pontos_obtidos, 'status_senha': senha.status},
            observacao=f"Julgamento de Boi #{numero_boi} da Senha #{senha.numero_senha} via {origem}"
        )

        return JsonResponse({
            'sucesso': True,
            'decisao': decisao,
            'pontos': passada.pontos_obtidos,
            'status_senha': senha.status,
            'total_pontos': senha.total_pontos
        })
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


@csrf_exempt
@require_POST
def enviar_mensagem_chat(request):
    """
    Envia mensagem do bate-papo rápido ou texto livre entre locutor e juiz.
    """
    try:
        data = json.loads(request.body)
        texto = data.get('mensagem', '').strip()
        tipo = data.get('tipo', ChatPista.TipoMensagem.LIVRE)
        
        evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
        usuario = request.user if request.user.is_authenticated else evento.organizador

        if texto:
            chat = ChatPista.objects.create(
                evento=evento,
                remetente=usuario,
                tipo=tipo,
                mensagem=texto
            )
            return JsonResponse({
                'sucesso': True,
                'mensagem': chat.mensagem,
                'remetente': chat.remetente.apelido_locucao or chat.remetente.username,
                'hora': chat.criado_em.strftime('%H:%M')
            })
        return JsonResponse({'sucesso': False, 'erro': 'Mensagem vazia'}, status=400)
    except Exception as e:
        return JsonResponse({'sucesso': False, 'erro': str(e)}, status=500)


def status_atual(request):
    """
    Endpoint JSON de alta performance para sincronização dinâmica sem reload (Polling a cada 3s).
    Retorna o conjunto atual em pista, suas passadas e as últimas mensagens de chat/alertas.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    if not evento:
        return JsonResponse({'sucesso': False, 'erro': 'Nenhum evento ativo'})

    conjunto_atual = SenhaInscricao.objects.filter(
        evento=evento,
        status=SenhaInscricao.StatusSenha.NA_PISTA
    ).first()

    dados_conjunto = None
    if conjunto_atual:
        passadas = []
        for p in conjunto_atual.passadas.all().order_by('numero_boi'):
            passadas.append({
                'numero_boi': p.numero_boi,
                'julgamento_juiz': p.julgamento_juiz or '',
                'julgamento_locutor': p.julgamento_locutor or '',
                'pontos': p.pontos_obtidos
            })

        dados_conjunto = {
            'id': str(conjunto_atual.id),
            'numero_senha': conjunto_atual.numero_senha,
            'categoria': conjunto_atual.categoria.nome_exibicao,
            'total_pontos': conjunto_atual.total_pontos,
            'status': conjunto_atual.status,
            'vaqueiro_puxador': conjunto_atual.vaqueiro_puxador.apelido_locucao or conjunto_atual.vaqueiro_puxador.get_full_name(),
            'cavalo_puxador': conjunto_atual.cavalo_puxador.nome if conjunto_atual.cavalo_puxador else '',
            'vaqueiro_esteireiro': (conjunto_atual.vaqueiro_esteireiro.apelido_locucao or conjunto_atual.vaqueiro_esteireiro.get_full_name()) if conjunto_atual.vaqueiro_esteireiro else '',
            'cavalo_esteireiro': conjunto_atual.cavalo_esteireiro.nome if conjunto_atual.cavalo_esteireiro else '',
            'representacao': conjunto_atual.representacao,
            'passadas': passadas
        }

    chat_historico = []
    for c in ChatPista.objects.filter(evento=evento).exclude(tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA).order_by('-criado_em')[:8]:
        chat_historico.append({
            'remetente': c.remetente.apelido_locucao or c.remetente.username,
            'mensagem': c.mensagem,
            'hora': c.criado_em.strftime('%H:%M')
        })

    alertas = []
    for a in ChatPista.objects.filter(evento=evento, tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA).order_by('-criado_em')[:5]:
        alertas.append({
            'mensagem': a.mensagem,
            'hora': a.criado_em.strftime('%H:%M')
        })

    return JsonResponse({
        'sucesso': True,
        'conjunto_atual': dados_conjunto,
        'chat': chat_historico,
        'alertas': alertas
    })
