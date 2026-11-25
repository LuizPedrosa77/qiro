from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from datetime import datetime
import uuid
from django.utils import timezone

from contas.models import Usuario
from eventos.models import Evento
from senhas.models import Categoria, SenhaInscricao
from competidores.models import Animal
from financeiro.models import Transacao
from senhas.webhooks import disparar_webhook_n8n


def tela_inicial(request):
    """
    Tela Inicial QIRO (Conforme Imagem 1 do Usuário).
    - Topbar com Início, Quem Somos, Vaquejada, Comprar Senha e botões destacados Login / Cadastrar.
    - Seletor de Estado no Centro: AL, BA, CE, PE, RN, SE e TODOS ESTADOS.
    - Vitrine com exatamente 3 vaquejadas em destaque.
    - Botão verde 'Mais vaquejadas' levando para o catálogo completo.
    - Rodapé com botão destacado 'Área restrita ao Parque'.
    """
    estado_filtro = request.GET.get('estado', '').strip().upper()

    eventos_qs = Evento.objects.filter(
        status__in=[Evento.Status.INSCRICOES, Evento.Status.EM_ANDAMENTO]
    ).select_related('parque').prefetch_related('categorias').order_by('data_inicio')

    if estado_filtro and estado_filtro != 'TODOS':
        eventos_qs = eventos_qs.filter(parque__estado=estado_filtro)

    eventos_destaque = eventos_qs[:3]
    estados_principais = ['AL', 'BA', 'CE', 'PE', 'RN', 'SE']

    return render(request, 'home.html', {
        'eventos_destaque': eventos_destaque,
        'estados_principais': estados_principais,
        'estado_selecionado': estado_filtro,
        'total_vaquejadas': Evento.objects.filter(status__in=[Evento.Status.INSCRICOES, Evento.Status.EM_ANDAMENTO]).count(),
    })


def cliente_login(request):
    """
    Login do Cliente com flexibilidade: CPF ou E-mail + Senha.
    """
    if request.user.is_authenticated:
        return redirect('cliente_secretaria')

    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        senha = request.POST.get('senha', '')

        if not identificador or not senha:
            messages.error(request, 'Por favor, informe seu CPF ou E-mail e sua senha.')
            return render(request, 'cliente/login.html')

        user = authenticate(request, username=identificador, password=senha)
        if user is not None:
            login(request, user)
            messages.success(request, f'Bem-vindo de volta, {user.first_name or user.username}!')
            return redirect('cliente_secretaria')
        else:
            messages.error(request, 'CPF/E-mail ou senha incorretos. Verifique e tente novamente.')

    return render(request, 'cliente/login.html')


def cliente_cadastro(request):
    """
    Cadastro completo do Vaqueiro / Cliente.
    Coleta Nome, Data de Nascimento, E-mail, CPF, Endereço Completo, Telefone/WhatsApp e Senha.
    """
    if request.user.is_authenticated:
        return redirect('cliente_secretaria')

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        sobrenome = request.POST.get('sobrenome', '').strip()
        data_nasc_str = request.POST.get('data_nascimento', '').strip()
        cpf = request.POST.get('cpf', '').strip()
        email = request.POST.get('email', '').strip().lower()
        telefone = request.POST.get('telefone', '').strip()
        
        # Endereço
        cep = request.POST.get('cep', '').strip()
        endereco = request.POST.get('endereco', '').strip()
        numero = request.POST.get('numero', '').strip()
        bairro = request.POST.get('bairro', '').strip()
        cidade = request.POST.get('cidade', '').strip()
        estado = request.POST.get('estado', '').strip().upper()

        senha = request.POST.get('senha', '')
        confirmar_senha = request.POST.get('confirmar_senha', '')

        # Validações
        if senha != confirmar_senha:
            messages.error(request, 'As senhas digitadas não conferem.')
            return render(request, 'cliente/cadastro.html', {'dados': request.POST})

        if len(senha) < 6:
            messages.error(request, 'A senha deve ter no mínimo 6 caracteres.')
            return render(request, 'cliente/cadastro.html', {'dados': request.POST})

        cpf_clean = ''.join(filter(str.isdigit, cpf))
        if Usuario.objects.filter(Q(cpf=cpf) | Q(cpf=cpf_clean)).exists():
            messages.error(request, 'Este CPF já está cadastrado. Faça login ou recupere seu acesso.')
            return render(request, 'cliente/cadastro.html', {'dados': request.POST})

        if Usuario.objects.filter(email=email).exists():
            messages.error(request, 'Este e-mail já está em uso.')
            return render(request, 'cliente/cadastro.html', {'dados': request.POST})

        data_nasc = None
        if data_nasc_str:
            try:
                data_nasc = datetime.strptime(data_nasc_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        username = cpf_clean if cpf_clean else f"user_{email.split('@')[0]}"

        # Criação do usuário
        user = Usuario.objects.create(
            username=username,
            first_name=nome,
            last_name=sobrenome,
            email=email,
            cpf=cpf_clean,
            data_nascimento=data_nasc,
            telefone=telefone,
            cep=cep,
            endereco=endereco,
            numero=numero,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            papel=Usuario.Papel.COMPETIDOR
        )
        user.set_password(senha)
        user.save()

        # Autentica e loga automaticamente
        login(request, user, backend='contas.backends.EmailOrCPFBackend')
        messages.success(request, f'Cadastro realizado com sucesso! Bem-vindo ao QIRO, {user.first_name}.')
        return redirect('cliente_secretaria')

    return render(request, 'cliente/cadastro.html')


def cliente_logout(request):
    logout(request)
    messages.info(request, 'Você saiu da sua conta.')
    return redirect('tela_inicial')


def equipe_login(request):
    """
    Login de acesso restrito da Equipe e Administração:
    - Autentica e direciona todos os perfis autorizados (ADM, Coordenador, Locutor, Juiz, Secretaria)
      para o Hub Operacional Central da Área Restrita (/equipe/hub/).
    """
    if request.method == 'POST':
        usuario_str = request.POST.get('usuario', '').strip()
        senha = request.POST.get('senha', '')

        user = authenticate(request, username=usuario_str, password=senha)
        if user is not None and (
            user.is_superuser or user.papel in [
                Usuario.Papel.ADMIN, Usuario.Papel.COORDENADOR, Usuario.Papel.ORGANIZADOR,
                Usuario.Papel.LOCUTOR, Usuario.Papel.JUIZ, Usuario.Papel.SECRETARIA
            ]
        ):
            login(request, user)
            return redirect('/equipe/hub/')
        else:
            messages.error(request, 'Credenciais inválidas ou você não possui permissão de acesso restrito.')

    return render(request, 'equipe/login.html')


@login_required(login_url='/equipe/login/')
def equipe_hub(request):
    """
    Console Central da Área Restrita (Hub Operacional).
    Exibe os cartões de controle e cabines baseados estritamente no papel do usuário:
    - ADM Geral: Controle total (Vaquejadas, Auditoria, Locução, Juiz, Secretaria, Telão, TV Vaqueiro).
    - Coordenador: Painel de relatórios financeiros e auditoria de inscrições do seu evento.
    - Locutor: Acesso à Cabine Oficial de Locução.
    - Juiz: Acesso ao Terminal de Julgamento da Bateria Oficial.
    - Secretaria: Mapa e emissão de senhas na portaria.
    """
    user = request.user
    if not (user.is_superuser or user.papel in [
        Usuario.Papel.ADMIN, Usuario.Papel.COORDENADOR, Usuario.Papel.ORGANIZADOR,
        Usuario.Papel.LOCUTOR, Usuario.Papel.JUIZ, Usuario.Papel.SECRETARIA
    ]):
        messages.error(request, 'Você não possui permissão de acesso à Área Restrita.')
        return redirect('tela_inicial')

    evento_ativo = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()

    return render(request, 'equipe/hub.html', {
        'usuario': user,
        'evento_ativo': evento_ativo,
    })


@login_required(login_url='/cliente/login/')
def cliente_secretaria(request):
    """Visão geral do vaqueiro (a rota legada /secretaria/ permanece compatível)."""
    cpf_numeros = ''.join(filter(str.isdigit, request.user.cpf or ''))
    senhas_usuario = SenhaInscricao.objects.filter(
        Q(vaqueiro_puxador=request.user) |
        Q(vaqueiro_puxador__cpf=request.user.cpf) |
        Q(vaqueiro_puxador__cpf=cpf_numeros)
    ).select_related('evento', 'evento__parque', 'categoria').order_by('-criado_em')
    pagamentos = Transacao.objects.filter(usuario=request.user).select_related('senha', 'senha__evento')
    hoje = timezone.localdate()
    proxima = senhas_usuario.filter(
        evento__data_inicio__gte=hoje,
        status__in=[SenhaInscricao.StatusSenha.PAGA, SenhaInscricao.StatusSenha.RESERVADA]
    ).order_by('evento__data_inicio').first()

    return render(request, 'cliente/visao_geral.html', {
        'senhas_recentes': senhas_usuario[:4],
        'total_senhas': senhas_usuario.count(),
        'pagamentos_pendentes': pagamentos.filter(status=Transacao.StatusPagamento.PENDENTE).count(),
        'proxima_senha': proxima,
        'total_investido': pagamentos.filter(status=Transacao.StatusPagamento.PAGO).aggregate(total=Sum('valor_total'))['total'] or 0,
        'pagamento_pendente': pagamentos.filter(status=Transacao.StatusPagamento.PENDENTE).order_by('-criado_em').first(),
    })


@login_required(login_url='/cliente/login/')
def cliente_minhas_senhas(request):
    """Lista pesquisável das inscrições pertencentes ao vaqueiro logado."""
    busca = request.GET.get('busca', '').strip()
    status = request.GET.get('status', '').strip()
    cpf_numeros = ''.join(filter(str.isdigit, request.user.cpf or ''))
    senhas = SenhaInscricao.objects.filter(
        Q(vaqueiro_puxador=request.user) |
        Q(vaqueiro_puxador__cpf=request.user.cpf) |
        Q(vaqueiro_puxador__cpf=cpf_numeros)
    ).select_related('evento', 'evento__parque', 'categoria', 'cavalo_puxador', 'cavalo_esteireiro').prefetch_related('passadas').order_by('-criado_em')
    if busca:
        senhas = senhas.filter(
            Q(evento__nome__icontains=busca) |
            Q(categoria__nome_exibicao__icontains=busca) |
            Q(numero_senha__icontains=busca)
        )
    if status:
        senhas = senhas.filter(status=status)
    return render(request, 'cliente/minhas_senhas.html', {
        'senhas': senhas,
        'busca': busca,
        'status_selecionado': status,
        'status_opcoes': SenhaInscricao.StatusSenha.choices,
    })


@login_required(login_url='/cliente/login/')
def cliente_pagamentos(request):
    """Histórico financeiro do cliente, separado dos dados de inscrição."""
    status = request.GET.get('status', '').strip()
    pagamentos = Transacao.objects.filter(usuario=request.user).select_related(
        'senha', 'senha__evento', 'senha__categoria'
    ).order_by('-criado_em')
    if status:
        pagamentos = pagamentos.filter(status=status)
    return render(request, 'cliente/pagamentos.html', {
        'pagamentos': pagamentos,
        'status_selecionado': status,
        'status_opcoes': Transacao.StatusPagamento.choices,
    })


@login_required(login_url='/cliente/login/')
def cliente_perfil(request):
    """Atualiza os dados de contato do cliente; CPF permanece imutável."""
    user = request.user
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if email and Usuario.objects.exclude(pk=user.pk).filter(email=email).exists():
            messages.error(request, 'Este e-mail já está sendo usado por outra conta.')
        else:
            user.first_name = request.POST.get('nome', '').strip()
            user.last_name = request.POST.get('sobrenome', '').strip()
            user.email = email
            user.telefone = request.POST.get('telefone', '').strip()
            user.cidade = request.POST.get('cidade', '').strip()
            user.estado = request.POST.get('estado', '').strip().upper()[:2]
            user.endereco = request.POST.get('endereco', '').strip()
            user.numero = request.POST.get('numero', '').strip()
            user.bairro = request.POST.get('bairro', '').strip()
            user.cep = request.POST.get('cep', '').strip()
            user.save()
            messages.success(request, 'Seus dados foram atualizados.')
            return redirect('cliente_perfil')
    return render(request, 'cliente/perfil.html', {'estados': ['AL', 'BA', 'CE', 'PE', 'PB', 'PI', 'RN', 'SE']})


@login_required(login_url='/cliente/login/')
def cliente_comprar(request):
    """
    Fluxo de compra de senha com Mapa Interativo (Grade 1 a 200) e Tabela de Preços,
    selecionando especificamente a Vaquejada e Categoria desejada.
    Suporta os 4 estados visuais: Disponível, Reservada (Aguardando Pix), Paga e No Carrinho.
    """
    evento_id = request.GET.get('evento') or request.POST.get('evento_id')
    if evento_id:
        evento = get_object_or_404(Evento, id=evento_id)
    else:
        evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()

    categorias = Categoria.objects.filter(evento=evento, ativo=True) if evento else Categoria.objects.none()

    # Categoria selecionada
    cat_id = request.GET.get('categoria')
    if cat_id:
        categoria_atual = categorias.filter(id=cat_id).first() or categorias.first()
    else:
        categoria_atual = categorias.filter(tipo=Categoria.TipoCategoria.AMADOR).first() or categorias.first()

    dia_selecionado = request.GET.get('dia', 'Quinta')

    # Senhas já compradas ou reservadas
    agora = timezone.now()
    senhas_pagas = set()
    senhas_reservadas = set()

    if evento and categoria_atual:
        senhas_qs = SenhaInscricao.objects.filter(evento=evento, categoria=categoria_atual)
        for s in senhas_qs:
            if s.status == SenhaInscricao.StatusSenha.PAGA:
                senhas_pagas.add(s.numero_senha)
            elif s.status == SenhaInscricao.StatusSenha.RESERVADA:
                if s.reservada_ate and s.reservada_ate < agora:
                    # Reserva expirada, considera livre
                    pass
                else:
                    senhas_reservadas.add(s.numero_senha)

    total_grid = categoria_atual.limite_senhas if (categoria_atual and categoria_atual.limite_senhas) else 200
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

    if request.method == 'POST':
        categoria_id = request.POST.get('categoria_id')
        categoria = get_object_or_404(Categoria, id=categoria_id, evento=evento)
        
        numero_senha_str = request.POST.get('numero_senha', '').strip()
        if not numero_senha_str:
            messages.error(request, 'Por favor, selecione ao menos um número disponível no Mapa de Senhas.')
            return redirect(f"/cliente/comprar/?evento={evento.id}&categoria={categoria.id}&dia={dia_selecionado}")

        # Suporta número único ou lista separada por vírgula (carrinho multi-senhas)
        numeros_selecionados = []
        for pedaco in numero_senha_str.split(','):
            pedaco = pedaco.strip()
            if pedaco.isdigit():
                numeros_selecionados.append(int(pedaco))

        if not numeros_selecionados:
            messages.error(request, 'Nenhum número válido foi selecionado.')
            return redirect(f"/cliente/comprar/?evento={evento.id}&categoria={categoria.id}&dia={dia_selecionado}")

        # Checagem de disponibilidade
        conflitos = SenhaInscricao.objects.filter(
            evento=evento,
            categoria=categoria,
            numero_senha__in=numeros_selecionados,
            status=SenhaInscricao.StatusSenha.PAGA
        ).values_list('numero_senha', flat=True)

        if conflitos:
            messages.error(request, f'A(s) senha(s) #{", #".join(map(str, conflitos))} já foi(ram) comprada(s). Por favor, escolha outros números.')
            return redirect(f"/cliente/comprar/?evento={evento.id}&categoria={categoria.id}&dia={dia_selecionado}")

        dia_corrida = request.POST.get('dia_corrida', dia_selecionado)
        cavalo_puxador_nome = request.POST.get('cavalo_puxador', '').strip() or 'Cavalo Puxador'
        esteireiro_nome = request.POST.get('esteireiro', '').strip() or 'Esteireiro'
        cavalo_esteira_nome = request.POST.get('cavalo_esteira', '').strip() or 'Cavalo Esteira'
        representacao = request.POST.get('representacao', '').strip() or 'Haras Independente'
        tem_boi_tv = request.POST.get('tem_boi_tv') == 'on'

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
            defaults={'funcao': Animal.Funcao.PUXADOR, 'proprietario': request.user}
        )
        cav_est, _ = Animal.objects.get_or_create(
            nome=cavalo_esteira_nome,
            defaults={'funcao': Animal.Funcao.ESTEIRA, 'proprietario': request.user}
        )

        valor_base = categoria.valor_senha
        valor_tv = categoria.valor_boi_tv if tem_boi_tv else Decimal('0.00')
        valor_total_unidade = valor_base + valor_tv

        senhas_geradas = []
        eh_kit_casadinha = len(numeros_selecionados) >= 2
        segunda_num = numeros_selecionados[1] if eh_kit_casadinha else None

        for idx, num_s in enumerate(numeros_selecionados):
            senha_obj = SenhaInscricao.objects.create(
                evento=evento,
                categoria=categoria,
                numero_senha=num_s,
                vaqueiro_puxador=request.user,
                cavalo_puxador=cav_pux,
                vaqueiro_esteireiro=vaq_esteira,
                cavalo_esteireiro=cav_est,
                representacao=representacao,
                tem_boi_tv=tem_boi_tv,
                status=SenhaInscricao.StatusSenha.PAGA,
                valor_total=valor_total_unidade,
                dia_corrida=dia_corrida,
                origem_venda=SenhaInscricao.OrigemVenda.ONLINE,
                forma_pagamento=SenhaInscricao.FormaPagamento.PIX,
                eh_kit=eh_kit_casadinha,
                numero_segunda_senha=segunda_num if idx == 0 else None
            )
            senhas_geradas.append(senha_obj)

            # Registra a Transação financeira da senha
            Transacao.objects.create(
                senha=senha_obj,
                usuario=request.user,
                valor_base=valor_base,
                valor_adicional_tv=valor_tv,
                valor_total=valor_total_unidade,
                metodo=Transacao.MetodoPagamento.PIX,
                status=Transacao.StatusPagamento.PAGO,
                comprovante_id=f"ONLINE-{senha_obj.codigo_autenticidade.hex[:8].upper()}",
                pago_em=timezone.now()
            )

            # Dispara automação assíncrona para n8n (WhatsApp / Planilhas)
            disparar_webhook_n8n(senha_obj, evento_tipo='INSCRICAO_CONFIRMADA')

        if len(senhas_geradas) == 1:
            messages.success(request, f'Parabéns! Senha #{numeros_selecionados[0]} garantida com sucesso na {categoria.nome_exibicao} ({evento.nome})!')
        else:
            nums_txt = ", ".join(f"#{s.numero_senha}" for s in senhas_geradas)
            messages.success(request, f'Parabéns! {len(senhas_geradas)} senhas ({nums_txt}) garantidas com sucesso na {categoria.nome_exibicao} ({evento.nome})!')

        return redirect('cliente_secretaria')

    return render(request, 'cliente/comprar.html', {
        'evento': evento,
        'categorias': categorias,
        'categoria_atual': categoria_atual,
        'dia_selecionado': dia_selecionado,
        'grade_senhas': grade_senhas,
        'total_disponiveis': total_disponiveis,
        'total_reservadas': total_reservadas_count,
        'total_pagas': total_pagas_count,
        'senhas_feitas_total': total_pagas_count + total_reservadas_count,
        'senhas_livres_total': total_disponiveis,
        'total_grid': total_grid,
    })
