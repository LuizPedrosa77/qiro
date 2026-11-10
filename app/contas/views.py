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
    Tela Inicial QIRO (Hero Premium Minimalista - Opção 1).
    Exibe o evento ativo e os dois botões centrais: 'Área do Cliente' e 'Área Interna'.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    return render(request, 'home.html', {
        'evento': evento
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
    Exibe as senhas compradas pelo vaqueiro e um botão de destaque para 'Comprar Mais'.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()

    # Busca as senhas do vaqueiro logado
    cpf_numeros = ''.join(filter(str.isdigit, request.user.cpf or ''))
    senhas_usuario = SenhaInscricao.objects.filter(
        Q(vaqueiro_puxador=request.user) |
        Q(vaqueiro_puxador__cpf=request.user.cpf) |
        Q(vaqueiro_puxador__cpf=cpf_numeros)
    ).select_related('categoria', 'cavalo_puxador', 'cavalo_esteireiro').order_by('-criado_em')

    return render(request, 'cliente/secretaria.html', {
        'evento': evento,
        'senhas': senhas_usuario,
        'total_senhas': senhas_usuario.count(),
    })


@login_required(login_url='/cliente/login/')
def cliente_comprar(request):
    """
    Fluxo de compra rápida de nova senha para o cliente logado.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    categorias = Categoria.objects.filter(evento=evento, ativo=True)

    if request.method == 'POST':
        categoria_id = request.POST.get('categoria_id')
        categoria = get_object_or_404(Categoria, id=categoria_id)
        
        dia_corrida = request.POST.get('dia_corrida', 'Quinta')
        cavalo_puxador_nome = request.POST.get('cavalo_puxador', '').strip() or 'Cavalo Puxador'
        esteireiro_nome = request.POST.get('esteireiro', '').strip() or 'Esteireiro'
        cavalo_esteira_nome = request.POST.get('cavalo_esteira', '').strip() or 'Cavalo Esteira'
        representacao = request.POST.get('representacao', '').strip() or 'Haras Independente'
        tem_boi_tv = request.POST.get('tem_boi_tv') == 'on'

        # Próximo número disponível na categoria
        maior_senha = SenhaInscricao.objects.filter(categoria=categoria).order_by('-numero_senha').first()
        novo_numero = (maior_senha.numero_senha + 1) if maior_senha else 1

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
            numero_senha=novo_numero,
            vaqueiro_puxador=request.user,
            cavalo_puxador=cav_pux,
            cavalo_esteireiro=cav_est,
            representacao=representacao,
            tem_boi_tv=tem_boi_tv,
            status=SenhaInscricao.StatusSenha.PAGA,
            valor_total=valor_total,
            dia_corrida=dia_corrida
        )

        messages.success(request, f'Senha #{novo_numero} comprada com sucesso na {categoria.nome_exibicao}!')
        return redirect('cliente_secretaria')

    return render(request, 'cliente/comprar.html', {
        'evento': evento,
        'categorias': categorias
    })
