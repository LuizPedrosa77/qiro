from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from datetime import datetime

from contas.models import Usuario
from eventos.models import Evento
from senhas.models import Categoria, SenhaInscricao
from competidores.models import Animal


def tela_inicial(request):
    """
    Vitrine Oficial de Vaquejadas do Brasil — QIRO.
    Exibe todas as vaquejadas disponíveis com filtros por estado e busca,
    com visual profissional e autêntico de vaquejada nordestina (sem cara de IA).
    """
    busca = request.GET.get('busca', '').strip()
    estado_filtro = request.GET.get('estado', '').strip().upper()

    eventos = Evento.objects.filter(
        status__in=[Evento.Status.INSCRICOES, Evento.Status.EM_ANDAMENTO]
    ).select_related('parque').prefetch_related('categorias').order_by('data_inicio')

    if busca:
        eventos = eventos.filter(
            Q(nome__icontains=busca) |
            Q(parque__nome__icontains=busca) |
            Q(parque__cidade__icontains=busca) |
            Q(circuito_chancela__icontains=busca)
        )

    if estado_filtro and estado_filtro != 'TODOS':
        eventos = eventos.filter(parque__estado=estado_filtro)

    # Estados com vaquejadas ativas
    estados_disponiveis = Evento.objects.filter(
        status__in=[Evento.Status.INSCRICOES, Evento.Status.EM_ANDAMENTO]
    ).values_list('parque__estado', flat=True).distinct().order_by('parque__estado')

    return render(request, 'home.html', {
        'eventos': eventos,
        'estados_disponiveis': estados_disponiveis,
        'estado_selecionado': estado_filtro,
        'busca': busca,
        'total_vaquejadas': eventos.count(),
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
    Login de acesso restrito da Equipe (Locutores, Juízes, Secretaria Geral, Organizador).
    """
    if request.method == 'POST':
        usuario_str = request.POST.get('usuario', '').strip()
        senha = request.POST.get('senha', '')

        user = authenticate(request, username=usuario_str, password=senha)
        if user is not None and user.papel in [
            Usuario.Papel.LOCUTOR, Usuario.Papel.JUIZ, Usuario.Papel.SECRETARIA,
            Usuario.Papel.ORGANIZADOR, Usuario.Papel.ADMIN
        ]:
            login(request, user)
            if user.papel == Usuario.Papel.LOCUTOR:
                return redirect('/pista/locutor/')
            elif user.papel == Usuario.Papel.JUIZ:
                return redirect('/pista/juiz/')
            else:
                return redirect('/senhas/mapa/')
        else:
            messages.error(request, 'Credenciais inválidas ou você não possui permissão de equipe.')

    return render(request, 'equipe/login.html')


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
    """
    evento_id = request.GET.get('evento') or request.POST.get('evento_id')
    if evento_id:
        evento = get_object_or_404(Evento, id=evento_id)
    else:
        evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()

    categorias = Categoria.objects.filter(evento=evento, ativo=True)

    # Categoria selecionada
    cat_id = request.GET.get('categoria')
    if cat_id:
        categoria_atual = categorias.filter(id=cat_id).first() or categorias.first()
    else:
        categoria_atual = categorias.filter(tipo=Categoria.TipoCategoria.AMADOR).first() or categorias.first()

    dia_selecionado = request.GET.get('dia', 'Quarta')

    # Senhas já compradas na categoria desse evento
    senhas_feitas = set(
        SenhaInscricao.objects.filter(evento=evento, categoria=categoria_atual).values_list('numero_senha', flat=True)
    )

    # Simula a ocupação visual clássica para demonstração se a categoria tiver poucas senhas
    if len(senhas_feitas) < 10:
        senhas_feitas.update(range(1, 148))
        senhas_feitas.update([160, 162, 165, 166, 168, 169, 175, 180, 181, 182, 184])

    total_grid = 200
    grade_senhas = []
    for num in range(1, total_grid + 1):
        grade_senhas.append({
            'numero': num,
            'ocupada': num in senhas_feitas
        })

    if request.method == 'POST':
        categoria_id = request.POST.get('categoria_id')
        categoria = get_object_or_404(Categoria, id=categoria_id, evento=evento)
        
        numero_senha_str = request.POST.get('numero_senha', '').strip()
        if not numero_senha_str:
            messages.error(request, 'Por favor, selecione um número disponível no Mapa de Senhas.')
            return redirect(f"/cliente/comprar/?evento={evento.id}&categoria={categoria.id}&dia={dia_selecionado}")

        numero_senha = int(numero_senha_str)

        # Checagem de disponibilidade
        if SenhaInscricao.objects.filter(evento=evento, categoria=categoria, numero_senha=numero_senha).exists():
            messages.error(request, f'A senha #{numero_senha} já está ocupada. Por favor, escolha outro número.')
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

        valor_total = categoria.valor_senha + (categoria.valor_boi_tv if tem_boi_tv else 0)

        senha = SenhaInscricao.objects.create(
            evento=evento,
            categoria=categoria,
            numero_senha=numero_senha,
            vaqueiro_puxador=request.user,
            cavalo_puxador=cav_pux,
            cavalo_esteireiro=cav_est,
            representacao=representacao,
            tem_boi_tv=tem_boi_tv,
            status=SenhaInscricao.StatusSenha.PAGA,
            valor_total=valor_total,
            dia_corrida=dia_corrida
        )

        messages.success(request, f'Parabéns! Senha #{numero_senha} garantida com sucesso na {categoria.nome_exibicao} ({evento.nome})!')
        return redirect('cliente_secretaria')

    return render(request, 'cliente/comprar.html', {
        'evento': evento,
        'categorias': categorias,
        'categoria_atual': categoria_atual,
        'dia_selecionado': dia_selecionado,
        'grade_senhas': grade_senhas,
        'senhas_feitas_total': len(senhas_feitas),
        'senhas_livres_total': total_grid - len(senhas_feitas),
    })
