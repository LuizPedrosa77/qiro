import uuid
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum

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

