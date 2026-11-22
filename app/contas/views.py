from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import datetime
from django.utils import timezone

from contas.models import Usuario
from eventos.models import Evento
from senhas.models import Categoria, SenhaInscricao
from competidores.models import Animal


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
    """
    Menu 'Secretaria' do Cliente:
    Exibe as senhas compradas pelo vaqueiro agrupadas por Vaquejada, com opção de comprar mais.
    """
    cpf_numeros = ''.join(filter(str.isdigit, request.user.cpf or ''))
    senhas_usuario = SenhaInscricao.objects.filter(
        Q(vaqueiro_puxador=request.user) |
        Q(vaqueiro_puxador__cpf=request.user.cpf) |
        Q(vaqueiro_puxador__cpf=cpf_numeros)
    ).select_related('evento', 'evento__parque', 'categoria', 'cavalo_puxador', 'cavalo_esteireiro').order_by('-criado_em')

    # Agrupa por evento
    eventos_com_senhas = {}
    for s in senhas_usuario:
        if s.evento not in eventos_com_senhas:
            eventos_com_senhas[s.evento] = []
        eventos_com_senhas[s.evento].append(s)

    return render(request, 'cliente/secretaria.html', {
        'senhas': senhas_usuario,
        'eventos_com_senhas': eventos_com_senhas,
        'total_senhas': senhas_usuario.count(),
    })


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

    # Simulação para demonstração visual se a categoria tiver poucas senhas no banco
    if len(senhas_pagas) + len(senhas_reservadas) < 10:
        senhas_pagas.update(range(1, 140))
        senhas_reservadas.update([142, 145, 148, 150])

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

        # Cavalos
        cav_pux, _ = Animal.objects.get_or_create(
            nome=cavalo_puxador_nome,
            defaults={'funcao': Animal.Funcao.PUXADOR, 'proprietario': request.user}
        )
        cav_est, _ = Animal.objects.get_or_create(
            nome=cavalo_esteira_nome,
            defaults={'funcao': Animal.Funcao.ESTEIRA, 'proprietario': request.user}
        )

        valor_total_unidade = categoria.valor_senha + (categoria.valor_boi_tv if tem_boi_tv else 0)

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
