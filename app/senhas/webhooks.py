import json
import logging
import threading
import urllib.request
import urllib.error
from django.conf import settings

logger = logging.getLogger(__name__)


def montar_payload_inscricao(senha, evento_tipo='INSCRICAO_CONFIRMADA'):
    """
    Estrutura o JSON completo com todos os dados da inscrição para envio ao n8n.
    Ideal para: WhatsApp da coordenação, Google Sheets, Notificações e ERP.
    """
    evento = senha.evento
    categoria = senha.categoria
    puxador = senha.vaqueiro_puxador
    esteira = senha.vaqueiro_esteireiro

    payload = {
        'evento_tipo': evento_tipo,
        'sistema': 'QIRO — Gestão de Vaquejada',
        'versao': '2.0',
        'inscricao': {
            'id': str(senha.id),
            'codigo_autenticidade': str(senha.codigo_autenticidade),
            'numero_senha': senha.numero_senha,
            'dia_corrida': senha.dia_corrida,
            'eh_kit': senha.eh_kit,
            'numero_segunda_senha': senha.numero_segunda_senha,
            'tem_boi_tv': senha.tem_boi_tv,
            'status': senha.status,
            'status_descricao': senha.get_status_display(),
            'origem_venda': senha.origem_venda,
            'origem_venda_descricao': senha.get_origem_venda_display(),
            'forma_pagamento': senha.forma_pagamento,
            'forma_pagamento_descricao': senha.get_forma_pagamento_display(),
            'valor_total': float(senha.valor_total),
            'data_hora': senha.criado_em.strftime('%d/%m/%Y %H:%M:%S') if senha.criado_em else '',
            'link_recibo': f"/senhas/recibo/{senha.codigo_autenticidade}/",
        },
        'evento': {
            'id': str(evento.id) if evento else '',
            'nome': evento.nome if evento else 'Vaquejada Oficial QIRO',
            'parque': evento.parque.nome if (evento and evento.parque) else '',
            'cidade': evento.parque.cidade if (evento and evento.parque) else '',
            'estado': evento.parque.estado if (evento and evento.parque) else '',
            'circuito_chancela': evento.circuito_chancela if (evento and hasattr(evento, 'circuito_chancela')) else '',
        },
        'categoria': {
            'id': str(categoria.id) if categoria else '',
            'nome': categoria.nome_exibicao if categoria else '',
            'tipo': categoria.tipo if categoria else '',
            'valor_unitario': float(categoria.valor_senha) if categoria else 0.0,
            'valor_boi_tv': float(categoria.valor_boi_tv) if categoria else 0.0,
        },
        'atleta_puxador': {
            'id': str(puxador.id) if puxador else '',
            'nome': puxador.get_full_name() or puxador.first_name or puxador.username if puxador else 'Competidor',
            'apelido_locucao': puxador.apelido_locucao if (puxador and hasattr(puxador, 'apelido_locucao')) else '',
            'cpf': puxador.cpf if (puxador and puxador.cpf) else '',
            'telefone_whatsapp': puxador.telefone if (puxador and hasattr(puxador, 'telefone')) else '',
            'email': puxador.email if puxador else '',
            'cidade': puxador.cidade if (puxador and hasattr(puxador, 'cidade')) else '',
            'estado': puxador.estado if (puxador and hasattr(puxador, 'estado')) else '',
        },
        'atleta_esteireiro': {
            'id': str(esteira.id) if esteira else None,
            'nome': (esteira.get_full_name() or esteira.first_name) if esteira else 'Esteireiro',
            'apelido_locucao': esteira.apelido_locucao if (esteira and hasattr(esteira, 'apelido_locucao')) else '',
        },
        'animais': {
            'cavalo_puxador': senha.cavalo_puxador.nome if senha.cavalo_puxador else '',
            'cavalo_esteira': senha.cavalo_esteireiro.nome if getattr(senha, 'cavalo_esteireiro', None) else '',
        },
        'equipe': {
            'representacao': senha.representacao,
        },
        'secretaria': {
            'operador': senha.operador_secretaria.username if senha.operador_secretaria else None,
        }
    }
    return payload


def _enviar_post_http(url, payload):
    """
    Executa a requisição HTTP POST para o endpoint do n8n com timeout seguro de 4 segundos.
    """
    try:
        dados_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=dados_json,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'User-Agent': 'QIRO-Vaquejada-Webhook/2.0'
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            status_code = response.getcode()
            logger.info(f"[QIRO Webhook] n8n respondeu com status {status_code} para {url}")
            return status_code
    except Exception as e:
        logger.warning(f"[QIRO Webhook] Erro ao disparar para n8n ({url}): {e}")
        return None


def disparar_webhook_n8n(senha, evento_tipo='INSCRICAO_CONFIRMADA', assincrono=True):
    """
    Dispara o webhook para o n8n.
    Por padrão roda em uma Thread em background para nunca travar a tela do usuário.
    """
    if not getattr(settings, 'N8N_WEBHOOK_ATIVO', True):
        return None

    url = getattr(settings, 'N8N_WEBHOOK_URL', '')
    if not url:
        return None

    payload = montar_payload_inscricao(senha, evento_tipo=evento_tipo)

    if assincrono:
        thread = threading.Thread(
            target=_enviar_post_http,
            args=(url, payload),
            daemon=True
        )
        thread.start()
        return True
    else:
        return _enviar_post_http(url, payload)
