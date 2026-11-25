import uuid
import csv
import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDate

from eventos.models import Evento
from senhas.models import Categoria, SenhaInscricao
from competidores.models import Animal
from contas.models import Usuario
from financeiro.models import Transacao
from senhas.webhooks import disparar_webhook_n8n


def mapa_senhas(request):
    """
    Tela oficial da Secretaria para escolha de senhas e Balcão Presencial (PDV da Vaquejada).
    Exibe:
    - Métricas em tempo real do Caixa do Balcão (Dinheiro, Cartão, Pix, Cortesia e Total)
    - Abas das categorias e grade interativa com os 4 estados visuais
    - Formulário express com busca automática por CPF e seleção tátil da forma de pagamento
    - Histórico recente das senhas emitidas hoje com atalho para reimpressão de recibo
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    categorias = Categoria.objects.filter(evento=evento, ativo=True) if evento else Categoria.objects.none()
    
    categoria_id = request.GET.get('categoria')
    if categoria_id:
        categoria_atual = get_object_or_404(Categoria, id=categoria_id)
    else:
        categoria_atual = categorias.filter(tipo=Categoria.TipoCategoria.ABERTA).first() or categorias.first()

    dia_selecionado = request.GET.get('dia', 'Quinta')

    # Senhas ocupadas e reservadas
    agora = timezone.now()
    senhas_pagas = set()
    senhas_reservadas = set()

    if categoria_atual:
        senhas_qs = SenhaInscricao.objects.filter(categoria=categoria_atual)
        for s in senhas_qs:
            if s.status == SenhaInscricao.StatusSenha.PAGA:
                senhas_pagas.add(s.numero_senha)
            elif s.status == SenhaInscricao.StatusSenha.RESERVADA:
                if s.reservada_ate and s.reservada_ate < agora:
                    pass
                else:
                    senhas_reservadas.add(s.numero_senha)

    # Grade de 1 a limite_senhas (ou padrão 75 conforme teste/mockup)
    total_grid = categoria_atual.limite_senhas if (categoria_atual and categoria_atual.limite_senhas) else 75
    grade_senhas = []
    total_disponiveis = 0
    total_reservadas_count = 0
    total_pagas_count = 0

    for num in range(1, total_grid + 1):
        if num in senhas_pagas:
            estado = 'paga'
            total_pagas_count += 1
        elif num in senhas_reservadas:
            estado = 'reservada'
            total_reservadas_count += 1
        else:
            estado = 'disponivel'
            total_disponiveis += 1

        grade_senhas.append({
            'numero': num,
            'estado': estado,
            'ocupada': estado in ['paga', 'reservada'],
        })

    # Senha selecionada para compra inicial
    senha_selecionada = int(request.GET.get('senha_num', 10))

    # ── MÉTRICAS DO CAIXA DO BALCÃO HOJE (AUDITORIA DO OPERADOR) ──
    hoje_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    senhas_balcao_hoje = SenhaInscricao.objects.filter(
        origem_venda=SenhaInscricao.OrigemVenda.BALCAO_PRESENCIAL,
        criado_em__gte=hoje_inicio
    )
    if evento:
        senhas_balcao_hoje = senhas_balcao_hoje.filter(evento=evento)

    total_dinheiro = senhas_balcao_hoje.filter(forma_pagamento=SenhaInscricao.FormaPagamento.DINHEIRO).aggregate(tot=Sum('valor_total'))['tot'] or Decimal('0.00')
    total_debito = senhas_balcao_hoje.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CARTAO_DEBITO).aggregate(tot=Sum('valor_total'))['tot'] or Decimal('0.00')
    total_credito = senhas_balcao_hoje.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CARTAO_CREDITO).aggregate(tot=Sum('valor_total'))['tot'] or Decimal('0.00')
    total_pix = senhas_balcao_hoje.filter(forma_pagamento=SenhaInscricao.FormaPagamento.PIX).aggregate(tot=Sum('valor_total'))['tot'] or Decimal('0.00')
    total_cortesias = senhas_balcao_hoje.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CORTESIA).count()
    total_geral_balcao = total_dinheiro + total_debito + total_credito + total_pix
    qtd_senhas_balcao = senhas_balcao_hoje.count()

    ultimas_senhas_balcao = senhas_balcao_hoje.select_related('vaqueiro_puxador', 'categoria').order_by('-criado_em')[:6]

    return render(request, 'senhas/mapa.html', {
        'evento': evento,
        'categorias': categorias,
        'categoria_atual': categoria_atual,
        'dia_selecionado': dia_selecionado,
        'grade_senhas': grade_senhas,
        'senha_selecionada': senha_selecionada,
        'total_disponiveis': total_disponiveis,
        'total_reservadas': total_reservadas_count,
        'total_pagas': total_pagas_count,
        # Métricas do Balcão
        'total_geral_balcao': total_geral_balcao,
        'total_dinheiro': total_dinheiro,
        'total_debito': total_debito,
        'total_credito': total_credito,
        'total_pix': total_pix,
        'total_cortesias': total_cortesias,
        'qtd_senhas_balcao': qtd_senhas_balcao,
        'ultimas_senhas_balcao': ultimas_senhas_balcao,
    })


def api_buscar_vaqueiro(request):
    """
    Busca rápida de competidor por CPF para preenchimento ágil no balcão da secretaria.
    Retorna os dados cadastrais e animais habituais da última inscrição.
    """
    cpf = request.GET.get('cpf', '').strip()
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    
    if not cpf_limpo:
        return JsonResponse({'sucesso': False, 'mensagem': 'CPF não informado.'})

    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf_limpo
        
    usuario = Usuario.objects.filter(
        Q(cpf=cpf) | Q(cpf=cpf_limpo) | Q(cpf=cpf_formatado)
    ).first()
    
    if not usuario:
        return JsonResponse({'sucesso': False, 'mensagem': 'Competidor não encontrado.'})
        
    # Recupera última inscrição para animais habituais
    ultima = SenhaInscricao.objects.filter(
        vaqueiro_puxador=usuario
    ).select_related('cavalo_puxador', 'vaqueiro_esteireiro', 'cavalo_esteireiro').order_by('-criado_em').first()
    
    dados = {
        'sucesso': True,
        'nome': usuario.get_full_name() or usuario.username,
        'apelido': usuario.apelido_locucao or usuario.first_name or usuario.username,
        'cidade': usuario.cidade or '',
        'estado': usuario.estado or 'PE',
        'telefone': usuario.telefone or '',
        'cavalo_puxador': ultima.cavalo_puxador.nome if (ultima and ultima.cavalo_puxador) else '',
        'esteireiro': ultima.vaqueiro_esteireiro.get_full_name() or ultima.vaqueiro_esteireiro.first_name if (ultima and ultima.vaqueiro_esteireiro) else '',
        'cavalo_esteira': ultima.cavalo_esteireiro.nome if (ultima and ultima.cavalo_esteireiro) else '',
        'representacao': ultima.representacao if ultima else '',
    }
    return JsonResponse(dados)


def finalizar_inscricao(request):
    """
    Processa o formulário de cadastro de senha e emissão no Balcão da Secretaria (Presencial).
    Suporta Dinheiro, Cartão de Débito, Cartão de Crédito, Cortesia e Pix presencial.
    """
    if request.method == 'POST':
        categoria_id = request.POST.get('categoria_id')
        categoria = get_object_or_404(Categoria, id=categoria_id)
        numero_senha = int(request.POST.get('numero_senha', 1))
        
        cpf = request.POST.get('cpf', '').strip()
        cpf_clean = ''.join(filter(str.isdigit, cpf))
        nome = request.POST.get('nome', '').strip() or 'Competidor'
        apelido = request.POST.get('apelido', '').strip() or nome
        estado = request.POST.get('estado', 'PE').strip()[:2].upper()
        cidade = request.POST.get('cidade', 'Caruaru').strip()
        telefone = request.POST.get('telefone', '').strip()
        
        cavalo_puxador_nome = request.POST.get('cavalo_puxador', '').strip() or 'Cavalo Puxador'
        esteireiro_nome = request.POST.get('esteireiro', '').strip() or 'Esteireiro'
        cavalo_esteira_nome = request.POST.get('cavalo_esteira', '').strip() or 'Cavalo Esteira'
        representacao = request.POST.get('representacao', '').strip() or 'Haras Geral'
        
        tem_boi_tv = request.POST.get('tem_boi_tv') == 'on'
        forma_pagamento_raw = request.POST.get('forma_pagamento', SenhaInscricao.FormaPagamento.DINHEIRO).strip().upper()
        
        # Mapeamento seguro da forma de pagamento
        formas_validas = dict(SenhaInscricao.FormaPagamento.choices)
        if forma_pagamento_raw not in formas_validas:
            forma_pagamento = SenhaInscricao.FormaPagamento.DINHEIRO
        else:
            forma_pagamento = forma_pagamento_raw

        # Casadinha / 2ª Senha (se marcado)
        eh_kit = request.POST.get('eh_kit') == 'on'
        numero_segunda_senha = None
        if eh_kit:
            segunda_raw = request.POST.get('numero_segunda_senha', '').strip()
            if segunda_raw.isdigit():
                numero_segunda_senha = int(segunda_raw)

        # Checagem de disponibilidade
        if SenhaInscricao.objects.filter(
            categoria=categoria, 
            numero_senha=numero_senha,
            status=SenhaInscricao.StatusSenha.PAGA
        ).exists():
            messages.error(request, f"A senha #{numero_senha} da {categoria.nome_exibicao} já foi paga e não pode ser reemitida.")
            return redirect(f"/senhas/mapa/?categoria={categoria.id}")

        if eh_kit and numero_segunda_senha:
            if SenhaInscricao.objects.filter(
                categoria=categoria, 
                numero_senha=numero_segunda_senha,
                status=SenhaInscricao.StatusSenha.PAGA
            ).exists():
                messages.error(request, f"A 2ª senha #{numero_segunda_senha} do kit já está ocupada.")
                return redirect(f"/senhas/mapa/?categoria={categoria.id}")

        # Busca ou cria vaqueiro puxador
        puxador = None
        cpf_formatado = f"{cpf_clean[:3]}.{cpf_clean[3:6]}.{cpf_clean[6:9]}-{cpf_clean[9:]}" if len(cpf_clean) == 11 else cpf_clean
        if cpf_clean:
            puxador = Usuario.objects.filter(Q(cpf=cpf) | Q(cpf=cpf_clean) | Q(cpf=cpf_formatado)).first()
            
        if not puxador:
            username_base = f"vaq_{numero_senha}_{cpf_clean}" if cpf_clean else f"vaq_balcao_{numero_senha}_{uuid.uuid4().hex[:6]}"
            puxador = Usuario.objects.create(
                username=username_base,
                cpf=cpf if cpf else None,
                first_name=nome.split()[0],
                last_name=' '.join(nome.split()[1:]) if len(nome.split()) > 1 else '',
                apelido_locucao=apelido,
                cidade=cidade,
                estado=estado,
                telefone=telefone,
                papel=Usuario.Papel.COMPETIDOR
            )
        else:
            # Atualiza dados rápidos se informados
            if nome and not puxador.first_name:
                puxador.first_name = nome.split()[0]
                puxador.last_name = ' '.join(nome.split()[1:]) if len(nome.split()) > 1 else ''
            if apelido and not puxador.apelido_locucao:
                puxador.apelido_locucao = apelido
            if telefone and not puxador.telefone:
                puxador.telefone = telefone
            puxador.save()

        # Vaqueiro esteireiro
        vaq_esteira = None
        if esteireiro_nome:
            vaq_esteira = Usuario.objects.filter(first_name=esteireiro_nome.split()[0]).first()
            if not vaq_esteira:
                vaq_esteira = Usuario.objects.create(
                    username=f"est_{uuid.uuid4().hex[:8]}",
                    first_name=esteireiro_nome.split()[0],
                    last_name=' '.join(esteireiro_nome.split()[1:]) if len(esteireiro_nome.split()) > 1 else '',
                    papel=Usuario.Papel.COMPETIDOR
                )

        # Cavalos
        cav_pux, _ = Animal.objects.get_or_create(
            nome=cavalo_puxador_nome,
            defaults={'funcao': Animal.Funcao.PUXADOR, 'proprietario': puxador}
        )
        cav_est, _ = Animal.objects.get_or_create(
            nome=cavalo_esteira_nome,
            defaults={'funcao': Animal.Funcao.ESTEIRA, 'proprietario': puxador}
        )

        # Cálculo do valor
        if forma_pagamento == SenhaInscricao.FormaPagamento.CORTESIA:
            valor_total = Decimal('0.00')
            valor_base = Decimal('0.00')
            valor_tv = Decimal('0.00')
        else:
            valor_base = categoria.valor_senha
            valor_tv = categoria.valor_boi_tv if tem_boi_tv else Decimal('0.00')
            valor_total = valor_base + valor_tv

        operador = request.user if request.user.is_authenticated else None

        # Cria ou atualiza a SenhaInscricao principal
        senha, created = SenhaInscricao.objects.update_or_create(
            evento=categoria.evento,
            categoria=categoria,
            numero_senha=numero_senha,
            defaults={
                'vaqueiro_puxador': puxador,
                'cavalo_puxador': cav_pux,
                'vaqueiro_esteireiro': vaq_esteira,
                'cavalo_esteireiro': cav_est,
                'representacao': representacao,
                'tem_boi_tv': tem_boi_tv,
                'status': SenhaInscricao.StatusSenha.PAGA,
                'valor_total': valor_total,
                'dia_corrida': request.POST.get('dia_corrida', 'Quinta'),
                'origem_venda': SenhaInscricao.OrigemVenda.BALCAO_PRESENCIAL,
                'forma_pagamento': forma_pagamento,
                'operador_secretaria': operador,
                'eh_kit': eh_kit,
                'numero_segunda_senha': numero_segunda_senha,
            }
        )

        # Se for casadinha, cria também a segunda senha
        if eh_kit and numero_segunda_senha:
            SenhaInscricao.objects.update_or_create(
                evento=categoria.evento,
                categoria=categoria,
                numero_senha=numero_segunda_senha,
                defaults={
                    'vaqueiro_puxador': puxador,
                    'cavalo_puxador': cav_pux,
                    'vaqueiro_esteireiro': vaq_esteira,
                    'cavalo_esteireiro': cav_est,
                    'representacao': representacao,
                    'tem_boi_tv': tem_boi_tv,
                    'status': SenhaInscricao.StatusSenha.PAGA,
                    'valor_total': valor_total,
                    'dia_corrida': request.POST.get('dia_corrida', 'Quinta'),
                    'origem_venda': SenhaInscricao.OrigemVenda.BALCAO_PRESENCIAL,
                    'forma_pagamento': forma_pagamento,
                    'operador_secretaria': operador,
                    'eh_kit': True,
                    'numero_segunda_senha': numero_senha,
                }
            )

        # Registra Transação financeira no sistema
        metodo_transacao = Transacao.MetodoPagamento.DINHEIRO
        if forma_pagamento in [SenhaInscricao.FormaPagamento.CARTAO_DEBITO, SenhaInscricao.FormaPagamento.CARTAO_CREDITO]:
            metodo_transacao = Transacao.MetodoPagamento.CARTAO
        elif forma_pagamento == SenhaInscricao.FormaPagamento.PIX:
            metodo_transacao = Transacao.MetodoPagamento.PIX

        Transacao.objects.create(
            senha=senha,
            usuario=puxador,
            valor_base=valor_base,
            valor_adicional_tv=valor_tv,
            valor_total=valor_total,
            metodo=metodo_transacao,
            status=Transacao.StatusPagamento.PAGO,
            comprovante_id=f"BALCAO-{senha.codigo_autenticidade.hex[:8].upper()}",
            pago_em=timezone.now()
        )

        # Dispara automação assíncrona para o n8n (WhatsApp / Google Sheets / Alertas)
        disparar_webhook_n8n(senha, evento_tipo='INSCRICAO_CONFIRMADA')

        # Mensagem rica para o operador
        troco_info = ""
        valor_recebido_str = request.POST.get('valor_recebido', '').replace(',', '.').strip()
        if forma_pagamento == SenhaInscricao.FormaPagamento.DINHEIRO and valor_recebido_str:
            try:
                val_rec = Decimal(valor_recebido_str)
                if val_rec > valor_total:
                    troco = val_rec - valor_total
                    troco_info = f" | Troco a devolver: R$ {troco:.2f}"
            except Exception:
                pass

        if eh_kit and numero_segunda_senha:
            msg = f"Casadinha emitida no balcão: Senhas #{numero_senha} e #{numero_segunda_senha} ({categoria.nome_exibicao}) confirmadas via {senha.get_forma_pagamento_display()}!{troco_info}"
        elif forma_pagamento == SenhaInscricao.FormaPagamento.CORTESIA:
            msg = f"Cortesia autorizada: Senha #{numero_senha} ({categoria.nome_exibicao}) emitida com sucesso!"
        else:
            msg = f"Senha #{numero_senha} confirmada com sucesso via {senha.get_forma_pagamento_display()}! Total: R$ {valor_total:.2f}{troco_info}"

        messages.success(request, msg)

        # Se o operador marcou "imprimir_recibo", abre o recibo
        if request.POST.get('imprimir_recibo') == 'on':
            return redirect(f"/senhas/recibo/{senha.codigo_autenticidade}/?auto_print=1")

        return redirect(f"/senhas/mapa/?categoria={categoria.id}")

    return redirect("/senhas/mapa/")


def recibo_balcao(request, codigo_autenticidade):
    """
    Exibe a 2ª via / comprovante de atendimento da Secretaria pronto para impressão térmica (58mm/80mm) ou A4.
    """
    senha = get_object_or_404(
        SenhaInscricao.objects.select_related(
            'evento', 'evento__parque', 'categoria', 
            'vaqueiro_puxador', 'cavalo_puxador', 'vaqueiro_esteireiro', 'cavalo_esteireiro', 
            'operador_secretaria'
        ),
        codigo_autenticidade=codigo_autenticidade
    )
    auto_print = request.GET.get('auto_print') == '1'
    return render(request, 'senhas/recibo_balcao.html', {
        'senha': senha,
        'auto_print': auto_print,
    })


def admin_zerar_senhas(request):
    """
    Ação exclusiva do Administrador Geral / Secretaria do Parque para reiniciar
    as senhas do evento ou de uma categoria específica (limpeza de testes ou reabertura de lotes).
    Exige confirmação digitando a palavra ZERAR.
    """
    if request.method == 'POST':
        evento_id = request.POST.get('evento_id')
        categoria_id = request.POST.get('categoria_id')
        escopo = request.POST.get('escopo', 'TODAS')  # 'TODAS' ou 'RESERVAS_EXPIRADAS'
        confirmacao = request.POST.get('confirmacao', '').strip().upper()

        if confirmacao != 'ZERAR':
            messages.error(request, 'Operação cancelada: para confirmar a limpeza, você deve digitar exatamente a palavra ZERAR.')
            redirect_url = f"/senhas/mapa/?categoria={categoria_id}" if categoria_id and categoria_id != 'TODAS' else "/senhas/mapa/"
            return redirect(redirect_url)

        senhas_qs = SenhaInscricao.objects.all()
        if evento_id:
            senhas_qs = senhas_qs.filter(evento_id=evento_id)
        if categoria_id and categoria_id != 'TODAS':
            senhas_qs = senhas_qs.filter(categoria_id=categoria_id)

        if escopo == 'RESERVAS_EXPIRADAS':
            senhas_qs = senhas_qs.filter(
                status=SenhaInscricao.StatusSenha.RESERVADA,
                reservada_ate__lt=timezone.now()
            )
            qtd = senhas_qs.count()
            senhas_qs.delete()
            messages.success(request, f'Limpeza concluída: {qtd} reserva(s) expirada(s) foram canceladas e seus números liberados.')
        else:
            qtd = senhas_qs.count()
            # Deleta transações financeiras vinculadas antes para evitar erro de integridade relacional
            Transacao.objects.filter(senha__in=senhas_qs).delete()
            senhas_qs.delete()
            messages.success(request, f'Grade reiniciada com sucesso! {qtd} senha(s) foram zeradas e todos os números estão 100% livres para comercialização.')

        redirect_url = f"/senhas/mapa/?categoria={categoria_id}" if categoria_id and categoria_id != 'TODAS' else "/senhas/mapa/"
        return redirect(redirect_url)

    return redirect("/senhas/mapa/")


def api_testar_webhook_n8n(request):
    """
    Endpoint de teste para verificar a conectividade do webhook do Django com o n8n.
    Envia um payload simulado e retorna a resposta do n8n em JSON.
    """
    from senhas.webhooks import _enviar_post_http
    from django.conf import settings

    url = getattr(settings, 'N8N_WEBHOOK_URL', '')
    if not url:
        return JsonResponse({'sucesso': False, 'erro': 'N8N_WEBHOOK_URL não configurada no settings.'}, status=400)

    payload_teste = {
        'evento_tipo': 'TESTE_CONEXAO_QIRO',
        'sistema': 'QIRO — Gestão de Vaquejada',
        'mensagem': 'Teste de conectividade bem-sucedido entre o QIRO e o n8n!',
        'timestamp': timezone.now().isoformat(),
        'exemplo_inscricao': {
            'numero_senha': 10,
            'categoria': 'Aberta',
            'vaqueiro': 'Competidor de Teste',
            'cpf': '000.000.000-00',
            'whatsapp': '(81) 99999-9999',
            'valor_total': 410.00,
            'status': 'PAGA'
        }
    }

    status_code = _enviar_post_http(url, payload_teste)
    if status_code and 200 <= status_code < 300:
        return JsonResponse({
            'sucesso': True,
            'status_code': status_code,
            'mensagem': f'Webhook recebido pelo n8n com sucesso (HTTP {status_code})!',
            'url': url
        })
    else:
        return JsonResponse({
            'sucesso': False,
            'status_code': status_code,
            'mensagem': f'n8n não respondeu ou retornou código de erro ({status_code}). Verifique se o n8n está ativo e escutando a rota.',
            'url': url
        }, status=502 if not status_code else 400)


@login_required(login_url='/equipe/login/')
def webhook_central(request):
    """
    Central de Webhooks e Automações (n8n, WhatsApp e Planilhas).
    Disponível para o Administrador Geral e Organizadores.
    Exibe guia passo a passo, modelo de payload JSON, templates prontos para WhatsApp e disparador de teste.
    """
    user = request.user
    if not (user.is_superuser or user.papel in [Usuario.Papel.ADMIN, Usuario.Papel.ORGANIZADOR]):
        messages.error(request, 'Acesso restrito ao Administrador Geral.')
        return redirect('/equipe/hub/')

    from django.conf import settings
    webhook_url = getattr(settings, 'N8N_WEBHOOK_URL', 'http://localhost:5678/webhook/nova-inscricao-qiro')
    webhook_ativo = getattr(settings, 'N8N_WEBHOOK_ATIVO', True)

    import json
    exemplo_payload = {
        "evento_tipo": "INSCRICAO_CONFIRMADA",
        "sistema": "QIRO — Gestão de Vaquejada",
        "versao": "2.0",
        "inscricao": {
            "id": "e4f8b912-32a1-43e8-9bc7-111122223333",
            "codigo_autenticidade": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "numero_senha": 42,
            "dia_corrida": "Sexta",
            "eh_kit": False,
            "numero_segunda_senha": None,
            "tem_boi_tv": True,
            "status": "PAGA",
            "status_descricao": "Inscrição Paga & Confirmada",
            "origem_venda": "ONLINE",
            "origem_venda_descricao": "Venda Online (Site)",
            "forma_pagamento": "PIX",
            "forma_pagamento_descricao": "Pix Instantâneo",
            "valor_total": 510.00,
            "data_hora": timezone.now().strftime("%d/%m/%Y %H:%M:%S"),
            "link_recibo": "/senhas/recibo/a1b2c3d4-e5f6-7890-abcd-ef1234567890/"
        },
        "evento": {
            "id": "99b1a2c3-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
            "nome": "Grande Vaquejada do Milhão",
            "parque": "Parque Millany",
            "cidade": "Caruaru",
            "estado": "PE",
            "circuito_chancela": "Campeonato Portal Vaquejada"
        },
        "categoria": {
            "id": "88c2b3a4-5d6e-7f8a-9b0c-1d2e3f4a5b6c",
            "nome": "Profissional",
            "tipo": "PROFISSIONAL",
            "valor_unitario": 450.00,
            "valor_boi_tv": 60.00
        },
        "atleta_puxador": {
            "id": "77d3c4b5-6e7f-8a9b-0c1d-2e3f4a5b6c7d",
            "nome": "Junior Vaqueiro",
            "apelido_locucao": "O Furacão das Pistas",
            "cpf": "123.456.789-00",
            "telefone_whatsapp": "(81) 98888-7777",
            "email": "junior@email.com",
            "cidade": "Caruaru",
            "estado": "PE"
        },
        "atleta_esteireiro": {
            "id": "66e4d5c6-7f8a-9b0c-1d2e-3f4a5b6c7d8e",
            "nome": "Beto Esteira",
            "apelido_locucao": "Beto da Esteira"
        },
        "animais": {
            "cavalo_puxador": "Iron Man Ease",
            "cavalo_esteira": "Don Diego Bar"
        },
        "equipe": {
            "representacao": "Haras Estrela do Norte"
        },
        "secretaria": {
            "operador": "secretaria_presencial"
        }
    }
    exemplo_payload_json = json.dumps(exemplo_payload, indent=2, ensure_ascii=False)

    exemplo_whatsapp = (
        "📢 *NOVA INSCRIÇÃO CONFIRMADA — QIRO*\n\n"
        "🐎 *Vaquejada:* Grande Vaquejada do Milhão\n"
        "📍 *Parque:* Parque Millany (Caruaru - PE)\n"
        "🏷️ *Categoria:* Profissional\n"
        "🔢 *Senha Nº:* #42 (Sexta)\n\n"
        "🤠 *Puxador:* Junior Vaqueiro (O Furacão das Pistas)\n"
        "🤝 *Esteireiro:* Beto Esteira\n"
        "🐴 *Cavalos:* Iron Man Ease x Don Diego Bar\n"
        "🏡 *Representação:* Haras Estrela do Norte\n\n"
        "💰 *Valor:* R$ 510,00 (Pix Instantâneo)\n"
        "📺 *Boi de TV:* Sim\n"
        "📅 *Data:* " + timezone.now().strftime("%d/%m/%Y %H:%M:%S") + "\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Inscrição garantida no sistema QIRO!"
    )

    return render(request, 'senhas/webhook_central.html', {
        'usuario': user,
        'webhook_url': webhook_url,
        'webhook_ativo': webhook_ativo,
        'exemplo_payload_json': exemplo_payload_json,
        'exemplo_whatsapp': exemplo_whatsapp,
    })


@login_required(login_url='/equipe/login/')
def senhas_dashboard(request):
    """
    Dashboard Analítico Completo de Senhas e Vendas do Evento.
    Exibe:
    - KPIs Gerais: Total vendido, taxa de ocupação, faturamento total, ticket médio
    - Boi de TV vs Sem Boi de TV: quantidades, porcentagens e faturamento extra de vídeo
    - Gráfico de Torres (Colunas): Senhas vendidas vs vagas por categoria (Aberta, Amador, etc.)
    - Gráfico de Pizza / Donut: Proporção Boi de TV e Formas de Pagamento (Pix, Cartão, Dinheiro)
    - Gráfico de Linhas com Área: Ritmo diário de vendas (evolução temporal)
    - Gráfico de Barras Horizontais: Distribuição das corridas por dia da semana (Quinta a Domingo)
    - Gráfico de Origem: Vendas Online vs Balcão da Secretaria
    - Tabela analítica completa com barra de progresso por categoria
    """
    user = request.user
    if not (user.is_superuser or user.papel in [
        Usuario.Papel.ADMIN, Usuario.Papel.COORDENADOR, Usuario.Papel.ORGANIZADOR, Usuario.Papel.SECRETARIA
    ]):
        messages.error(request, 'Acesso não autorizado ao Dashboard de Senhas.')
        return redirect('/equipe/hub/')

    # Evento selecionado
    evento_id = request.GET.get('evento')
    if evento_id:
        evento = Evento.objects.filter(id=evento_id).first()
    else:
        evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()

    eventos = Evento.objects.all().order_by('-data_inicio')
    if not evento:
        return render(request, 'senhas/dashboard.html', {'evento': None, 'eventos': []})

    # Categoria selecionada para filtro
    categoria_id = request.GET.get('categoria', '').strip()
    categorias_qs = Categoria.objects.filter(evento=evento, ativo=True).order_by('ordem_apresentacao')

    # Status considerados válidos / confirmados
    status_vendidas = [
        SenhaInscricao.StatusSenha.PAGA,
        SenhaInscricao.StatusSenha.NA_BOIADA,
        SenhaInscricao.StatusSenha.NA_PISTA,
        SenhaInscricao.StatusSenha.BATIDA,
        SenhaInscricao.StatusSenha.ELIMINADA,
        SenhaInscricao.StatusSenha.DESCLASSIFICADA,
    ]

    # Query base
    senhas_evento = SenhaInscricao.objects.filter(evento=evento)
    senhas_filtradas = senhas_evento
    if categoria_id and categoria_id != 'TODAS':
        senhas_filtradas = senhas_filtradas.filter(categoria_id=categoria_id)

    senhas_pagas = senhas_filtradas.filter(status__in=status_vendidas)
    senhas_reservadas = senhas_filtradas.filter(status=SenhaInscricao.StatusSenha.RESERVADA)

    # 1. KPIs Gerais
    total_vendidas = senhas_pagas.count()
    total_reservadas = senhas_reservadas.count()
    faturamento_total = senhas_pagas.aggregate(tot=Sum('valor_total'))['tot'] or Decimal('0.00')

    if categoria_id and categoria_id != 'TODAS':
        cat_filtro = categorias_qs.filter(id=categoria_id).first()
        limite_total_vagas = cat_filtro.limite_senhas if cat_filtro else 0
    else:
        limite_total_vagas = sum(c.limite_senhas for c in categorias_qs)

    total_livres = max(0, limite_total_vagas - total_vendidas - total_reservadas)
    taxa_ocupacao = round((total_vendidas / limite_total_vagas * 100), 1) if limite_total_vagas > 0 else 0
    ticket_medio = round(faturamento_total / total_vendidas, 2) if total_vendidas > 0 else Decimal('0.00')

    # 2. Métricas de Boi de TV
    qtd_com_boi_tv = senhas_pagas.filter(tem_boi_tv=True).count()
    qtd_sem_boi_tv = max(0, total_vendidas - qtd_com_boi_tv)
    pct_com_boi_tv = round((qtd_com_boi_tv / total_vendidas * 100), 1) if total_vendidas > 0 else 0
    pct_sem_boi_tv = round((qtd_sem_boi_tv / total_vendidas * 100), 1) if total_vendidas > 0 else 0

    receita_boi_tv = sum(
        (s.categoria.valor_boi_tv for s in senhas_pagas.filter(tem_boi_tv=True).select_related('categoria')),
        Decimal('0.00')
    )

    # 3. Origem da Venda: Online vs Secretaria Balcão
    vendas_online = senhas_pagas.filter(origem_venda=SenhaInscricao.OrigemVenda.ONLINE).count()
    vendas_balcao = senhas_pagas.filter(origem_venda=SenhaInscricao.OrigemVenda.BALCAO_PRESENCIAL).count()
    pct_online = round((vendas_online / total_vendidas * 100), 1) if total_vendidas > 0 else 0
    pct_balcao = round((vendas_balcao / total_vendidas * 100), 1) if total_vendidas > 0 else 0

    # 4. Formas de Pagamento
    pagamentos_data = {
        'Pix': senhas_pagas.filter(forma_pagamento=SenhaInscricao.FormaPagamento.PIX).count(),
        'Cartão de Crédito': senhas_pagas.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CARTAO_CREDITO).count(),
        'Cartão de Débito': senhas_pagas.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CARTAO_DEBITO).count(),
        'Dinheiro': senhas_pagas.filter(forma_pagamento=SenhaInscricao.FormaPagamento.DINHEIRO).count(),
        'Cortesia': senhas_pagas.filter(forma_pagamento=SenhaInscricao.FormaPagamento.CORTESIA).count(),
    }

    # 5. Dias de Corrida
    dias_ordenados = ['Quinta', 'Sexta', 'Sábado', 'Domingo', 'A Definir']
    dias_counts = {d: 0 for d in dias_ordenados}
    for s in senhas_pagas:
        d = s.dia_corrida.strip() if s.dia_corrida else 'A Definir'
        if d in dias_counts:
            dias_counts[d] += 1
        else:
            dias_counts['A Definir'] += 1

    # 6. Detalhamento por Categoria (Tabela + Gráficos de Torre)
    detalhes_tabela = []
    torre_labels = []
    torre_vendidas = []
    torre_livres = []
    torre_receita = []

    for cat in categorias_qs:
        pagas_cat = senhas_evento.filter(categoria=cat, status__in=status_vendidas)
        qtd_cat_vend = pagas_cat.count()
        qtd_cat_tv = pagas_cat.filter(tem_boi_tv=True).count()
        tot_cat_rec = pagas_cat.aggregate(t=Sum('valor_total'))['t'] or Decimal('0.00')
        livres_cat = max(0, cat.limite_senhas - qtd_cat_vend)
        ocup_cat = round((qtd_cat_vend / cat.limite_senhas * 100), 1) if cat.limite_senhas > 0 else 0

        detalhes_tabela.append({
            'id': str(cat.id),
            'nome': cat.nome_exibicao,
            'tipo': cat.get_tipo_display(),
            'valor_unitario': cat.valor_senha,
            'limite': cat.limite_senhas,
            'vendidas': qtd_cat_vend,
            'livres': livres_cat,
            'ocupacao': ocup_cat,
            'com_boi_tv': qtd_cat_tv,
            'faturamento': tot_cat_rec,
        })

        torre_labels.append(cat.nome_exibicao)
        torre_vendidas.append(qtd_cat_vend)
        torre_livres.append(livres_cat)
        torre_receita.append(float(tot_cat_rec))

    # 7. Timeline de Vendas (Evolução por dia - Gráfico de Linha)
    timeline_qs = (
        senhas_pagas.filter(criado_em__isnull=False)
        .annotate(data_venda=TruncDate('criado_em'))
        .values('data_venda')
        .annotate(total=Count('id'))
        .order_by('data_venda')
    )
    linha_labels = [item['data_venda'].strftime('%d/%m') for item in timeline_qs if item['data_venda']]
    linha_valores = [item['total'] for item in timeline_qs if item['data_venda']]

    if not linha_labels:
        linha_labels = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Hoje']
        linha_valores = [0, 0, 0, 0, 0, 0, total_vendidas]

    contexto = {
        'usuario': user,
        'evento': evento,
        'eventos': eventos,
        'categorias': categorias_qs,
        'categoria_id_selecionada': categoria_id,
        # KPIs
        'total_vendidas': total_vendidas,
        'total_reservadas': total_reservadas,
        'total_livres': total_livres,
        'limite_total_vagas': limite_total_vagas,
        'taxa_ocupacao': taxa_ocupacao,
        'faturamento_total': faturamento_total,
        'ticket_medio': ticket_medio,
        # TV
        'qtd_com_boi_tv': qtd_com_boi_tv,
        'qtd_sem_boi_tv': qtd_sem_boi_tv,
        'pct_com_boi_tv': pct_com_boi_tv,
        'pct_sem_boi_tv': pct_sem_boi_tv,
        'receita_boi_tv': receita_boi_tv,
        # Origem
        'vendas_online': vendas_online,
        'vendas_balcao': vendas_balcao,
        'pct_online': pct_online,
        'pct_balcao': pct_balcao,
        # Tabela
        'detalhes_tabela': detalhes_tabela,
        # Dados serializados em JSON para o Chart.js
        'chart_torre_labels': json.dumps(torre_labels),
        'chart_torre_vendidas': json.dumps(torre_vendidas),
        'chart_torre_livres': json.dumps(torre_livres),
        'chart_torre_receita': json.dumps(torre_receita),
        'chart_tv_data': json.dumps([qtd_com_boi_tv, qtd_sem_boi_tv]),
        'chart_pagamentos_labels': json.dumps(list(pagamentos_data.keys())),
        'chart_pagamentos_data': json.dumps(list(pagamentos_data.values())),
        'chart_dias_labels': json.dumps(list(dias_counts.keys())),
        'chart_dias_data': json.dumps(list(dias_counts.values())),
        'chart_origem_data': json.dumps([vendas_online, vendas_balcao]),
        'chart_linha_labels': json.dumps(linha_labels),
        'chart_linha_valores': json.dumps(linha_valores),
    }

    return render(request, 'senhas/dashboard.html', contexto)


@login_required(login_url='/equipe/login/')
def exportar_relatorio_senhas_csv(request):
    """
    Exportação rápida das senhas do evento em formato CSV para Excel/Google Sheets.
    """
    user = request.user
    if not (user.is_superuser or user.papel in [
        Usuario.Papel.ADMIN, Usuario.Papel.COORDENADOR, Usuario.Papel.ORGANIZADOR, Usuario.Papel.SECRETARIA
    ]):
        return HttpResponse('Acesso negado', status=403)

    evento_id = request.GET.get('evento')
    evento = Evento.objects.filter(id=evento_id).first() if evento_id else Evento.objects.first()
    if not evento:
        return HttpResponse('Evento não encontrado', status=404)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="senhas_{evento.id}.csv"'
    response.write(u'\ufeff'.encode('utf8'))  # BOM para o Excel no Windows abrir com acentuação correta

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Senha', 'Dia', 'Categoria', 'Status', 'Puxador', 'CPF Puxador', 'WhatsApp',
        'Esteireiro', 'Cavalo Puxador', 'Cavalo Esteira', 'Representacao',
        'Boi TV', 'Valor Total', 'Forma Pagamento', 'Origem Venda', 'Data Emissao'
    ])

    senhas = SenhaInscricao.objects.filter(evento=evento).select_related(
        'categoria', 'vaqueiro_puxador', 'vaqueiro_esteireiro', 'cavalo_puxador', 'cavalo_esteireiro'
    ).order_by('categoria__ordem_apresentacao', 'numero_senha')

    for s in senhas:
        writer.writerow([
            s.numero_senha,
            s.dia_corrida or 'A Definir',
            s.categoria.nome_exibicao,
            s.get_status_display(),
            s.vaqueiro_puxador.get_full_name() or s.vaqueiro_puxador.username,
            s.vaqueiro_puxador.cpf if hasattr(s.vaqueiro_puxador, 'cpf') else '',
            getattr(s.vaqueiro_puxador, 'telefone', ''),
            s.vaqueiro_esteireiro.get_full_name() if s.vaqueiro_esteireiro else '',
            s.cavalo_puxador.nome if s.cavalo_puxador else '',
            s.cavalo_esteireiro.nome if s.cavalo_esteireiro else '',
            s.representacao,
            'SIM' if s.tem_boi_tv else 'NAO',
            f"{s.valor_total:.2f}".replace('.', ','),
            s.get_forma_pagamento_display(),
            s.get_origem_venda_display(),
            s.criado_em.strftime('%d/%m/%Y %H:%M') if s.criado_em else ''
        ])

    return response


