from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from datetime import datetime

from eventos.models import Parque, Evento
from senhas.models import Categoria, SenhaInscricao
from contas.models import Usuario


def lista_vaquejadas(request):
    """
    Catálogo Completo de Vaquejadas (Conforme Imagem 2).
    Apresenta a busca por nome/parque/cidade e filtros por estado.
    Grade completa de todas as vaquejadas ativas.
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

    estados_principais = ['AL', 'BA', 'CE', 'PE', 'RN', 'SE']

    return render(request, 'eventos/lista.html', {
        'eventos': eventos,
        'estados_principais': estados_principais,
        'estado_selecionado': estado_filtro,
        'busca': busca,
        'total_eventos': eventos.count(),
    })


@login_required(login_url='/equipe/login/')
def cadastrar_vaquejada(request):
    """
    ÁREA EXCLUSIVA DO ADM (Sua Conta).
    Permite cadastrar Parques, Vaquejadas, Categorias com preços e as FICHAS DE EQUIPE:
    - Coordenador(es) do Evento (Proprietário/Dono com visualização privilegiada)
    - Locutor(es)
    - Juízes de Pista
    Todos são gravados e vinculados no banco de dados PostgreSQL.
    """
    # Restrição estrita: Apenas o Administrador Geral
    if not (request.user.is_superuser or request.user.papel == Usuario.Papel.ADMIN):
        messages.error(request, 'Acesso restrito! Apenas o Administrador Geral tem permissão para cadastrar vaquejadas e gerenciar equipes.')
        return redirect('/equipe/login/')

    parques = Parque.objects.filter(ativo=True).order_by('nome')
    coordenadores_existentes = Usuario.objects.filter(papel=Usuario.Papel.COORDENADOR).order_by('first_name')
    locutores_existentes = Usuario.objects.filter(papel=Usuario.Papel.LOCUTOR).order_by('first_name')
    juizes_existentes = Usuario.objects.filter(papel=Usuario.Papel.JUIZ).order_by('first_name')

    if request.method == 'POST':
        # 1. Parque (Novo ou Existente)
        parque_id = request.POST.get('parque_id')
        nome_parque_novo = request.POST.get('nome_parque_novo', '').strip()
        cidade_parque = request.POST.get('cidade_parque', '').strip()
        estado_parque = request.POST.get('estado_parque', '').strip().upper()

        if parque_id and parque_id != 'novo':
            parque = get_object_or_404(Parque, id=parque_id)
        elif nome_parque_novo:
            parque, _ = Parque.objects.get_or_create(
                nome=nome_parque_novo,
                defaults={
                    'cidade': cidade_parque or 'Caruaru',
                    'estado': estado_parque or 'PE',
                    'responsavel': request.user.get_full_name() or request.user.username,
                }
            )
        else:
            parque = parques.first()

        # 2. Dados do Evento
        nome_evento = request.POST.get('nome_evento', '').strip()
        circuito_chancela = request.POST.get('circuito_chancela', '').strip() or 'Circuito Oficial'
        data_inicio_str = request.POST.get('data_inicio')
        data_fim_str = request.POST.get('data_fim')
        premiacao_str = request.POST.get('premiacao_total', '0').replace('.', '').replace(',', '.')
        descricao = request.POST.get('descricao', '').strip()

        try:
            premiacao_total = float(premiacao_str)
        except ValueError:
            premiacao_total = 0.0

        data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date() if data_inicio_str else datetime.now().date()
        data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date() if data_fim_str else data_inicio

        evento = Evento.objects.create(
            parque=parque,
            nome=nome_evento,
            data_inicio=data_inicio,
            data_fim=data_fim,
            premiacao_total=premiacao_total,
            circuito_chancela=circuito_chancela,
            descricao=descricao,
            status=Evento.Status.INSCRICOES,
            organizador=request.user
        )

        # 3. Categorias Padrão e Preços
        categorias_config = [
            (Categoria.TipoCategoria.ABERTA, 'Aberta', float(request.POST.get('preco_aberta', '800') or 800)),
            (Categoria.TipoCategoria.AMADOR, 'Amador', float(request.POST.get('preco_amador', '600') or 600)),
            (Categoria.TipoCategoria.ASPIRANTE, 'Aspirante', float(request.POST.get('preco_aspirante', '450') or 450)),
        ]

        if request.POST.get('incluir_master') == 'on':
            categorias_config.append((Categoria.TipoCategoria.MASTER, 'Master', float(request.POST.get('preco_master', '400') or 400)))

        if request.POST.get('incluir_jovem') == 'on':
            categorias_config.append((Categoria.TipoCategoria.JOVEM, 'Jovem', float(request.POST.get('preco_jovem', '250') or 250)))

        for tipo, nome, preco in categorias_config:
            Categoria.objects.create(
                evento=evento,
                tipo=tipo,
                nome_exibicao=nome,
                valor_senha=preco,
                valor_boi_tv=50.00,
                limite_senhas=200
            )

        # 4. FICHA DE COORDENADOR(ES)
        coord_existente_ids = request.POST.getlist('coordenador_existente_ids')
        for cid in coord_existente_ids:
            if cid:
                coord_user = Usuario.objects.filter(id=cid).first()
                if coord_user:
                    evento.coordenadores.add(coord_user)

        nome_coord_novo = request.POST.get('nome_coord_novo', '').strip()
        email_coord_novo = request.POST.get('email_coord_novo', '').strip().lower()
        cpf_coord_novo = request.POST.get('cpf_coord_novo', '').strip()
        tel_coord_novo = request.POST.get('tel_coord_novo', '').strip()
        if nome_coord_novo and (email_coord_novo or cpf_coord_novo):
            username_coord = cpf_coord_novo or email_coord_novo.split('@')[0]
            coord_novo, _ = Usuario.objects.get_or_create(
                username=username_coord,
                defaults={
                    'first_name': nome_coord_novo,
                    'email': email_coord_novo,
                    'cpf': cpf_coord_novo or None,
                    'telefone': tel_coord_novo,
                    'papel': Usuario.Papel.COORDENADOR
                }
            )
            coord_novo.papel = Usuario.Papel.COORDENADOR
            coord_novo.set_password('qiro123')
            coord_novo.save()
            evento.coordenadores.add(coord_novo)

        # 5. FICHA DE LOCUTOR(ES)
        locutor_existente_ids = request.POST.getlist('locutor_existente_ids')
        for lid in locutor_existente_ids:
            if lid:
                loc_user = Usuario.objects.filter(id=lid).first()
                if loc_user:
                    evento.locutores.add(loc_user)

        nome_loc_novo = request.POST.get('nome_loc_novo', '').strip()
        email_loc_novo = request.POST.get('email_loc_novo', '').strip().lower()
        apelido_loc_novo = request.POST.get('apelido_loc_novo', '').strip()
        if nome_loc_novo:
            username_loc = email_loc_novo.split('@')[0] if email_loc_novo else f"locutor.{nome_loc_novo.split()[0].lower()}"
            loc_novo, _ = Usuario.objects.get_or_create(
                username=username_loc,
                defaults={
                    'first_name': nome_loc_novo,
                    'email': email_loc_novo,
                    'apelido_locucao': apelido_loc_novo or nome_loc_novo,
                    'papel': Usuario.Papel.LOCUTOR
                }
            )
            loc_novo.papel = Usuario.Papel.LOCUTOR
            loc_novo.set_password('qiro123')
            loc_novo.save()
            evento.locutores.add(loc_novo)

        # 6. FICHA DE JUIZ(ES)
        juiz_existente_ids = request.POST.getlist('juiz_existente_ids')
        for jid in juiz_existente_ids:
            if jid:
                juiz_user = Usuario.objects.filter(id=jid).first()
                if juiz_user:
                    evento.juizes.add(juiz_user)

        nome_juiz_novo = request.POST.get('nome_juiz_novo', '').strip()
        email_juiz_novo = request.POST.get('email_juiz_novo', '').strip().lower()
        if nome_juiz_novo:
            username_juiz = email_juiz_novo.split('@')[0] if email_juiz_novo else f"juiz.{nome_juiz_novo.split()[0].lower()}"
            juiz_novo, _ = Usuario.objects.get_or_create(
                username=username_juiz,
                defaults={
                    'first_name': nome_juiz_novo,
                    'email': email_juiz_novo,
                    'papel': Usuario.Papel.JUIZ
                }
            )
            juiz_novo.papel = Usuario.Papel.JUIZ
            juiz_novo.set_password('qiro123')
            juiz_novo.save()
            evento.juizes.add(juiz_novo)

        messages.success(
            request, 
            f'Vaquejada "{evento.nome}" cadastrada com sucesso! Todas as categorias e as fichas de equipe foram gravadas no banco de dados.'
        )
        return redirect('lista_vaquejadas')

    return render(request, 'eventos/cadastrar.html', {
        'parques': parques,
        'coordenadores_existentes': coordenadores_existentes,
        'locutores_existentes': locutores_existentes,
        'juizes_existentes': juizes_existentes,
    })


@login_required(login_url='/equipe/login/')
def coordenador_dashboard(request):
    """
    PAINEL DO COORDENADOR DO EVENTO (Proprietário do Parque / Dono da Prova).
    Nível de acesso privilegiado: Visualiza relatórios financeiros, lista de inscrições,
    andamento e mapa da prova, sem poder cadastrar outros usuários.
    """
    user = request.user
    if not (user.is_superuser or user.papel in [Usuario.Papel.ADMIN, Usuario.Papel.COORDENADOR, Usuario.Papel.ORGANIZADOR]):
        messages.error(request, 'Acesso negado ao painel de coordenação.')
        return redirect('/equipe/login/')

    if user.is_superuser or user.papel == Usuario.Papel.ADMIN:
        eventos = Evento.objects.all().order_by('-data_inicio')
    else:
        eventos = Evento.objects.filter(
            Q(coordenadores=user) | Q(organizador=user)
        ).distinct().order_by('-data_inicio')

    evento_id = request.GET.get('evento')
    if evento_id:
        evento_selecionado = eventos.filter(id=evento_id).first()
    else:
        evento_selecionado = eventos.first()

    metricas = {
        'faturamento_total': 0.0,
        'total_senhas': 0,
        'senhas_pagas': 0,
        'senhas_pendentes': 0,
    }
    senhas_evento = []

    if evento_selecionado:
        qs = SenhaInscricao.objects.filter(evento=evento_selecionado)
        metricas['total_senhas'] = qs.count()
        metricas['senhas_pagas'] = qs.filter(status__in=[
            SenhaInscricao.StatusSenha.PAGA, 
            SenhaInscricao.StatusSenha.BATIDA, 
            SenhaInscricao.StatusSenha.NA_BOIADA, 
            SenhaInscricao.StatusSenha.NA_PISTA
        ]).count()
        metricas['senhas_pendentes'] = qs.filter(status=SenhaInscricao.StatusSenha.RESERVADA).count()
        faturado = qs.filter(status__in=[
            SenhaInscricao.StatusSenha.PAGA, 
            SenhaInscricao.StatusSenha.BATIDA,
            SenhaInscricao.StatusSenha.NA_BOIADA, 
            SenhaInscricao.StatusSenha.NA_PISTA
        ]).aggregate(total=Sum('valor_total'))['total']
        metricas['faturamento_total'] = faturado or 0.0

        senhas_evento = qs.select_related(
            'categoria', 'vaqueiro_puxador', 'cavalo_puxador', 'cavalo_esteireiro'
        ).order_by('numero_senha')[:100]

    return render(request, 'eventos/coordenador_dashboard.html', {
        'eventos': eventos,
        'evento_selecionado': evento_selecionado,
        'metricas': metricas,
        'senhas_evento': senhas_evento,
    })
