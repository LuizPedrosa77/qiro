from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import datetime

from eventos.models import Parque, Evento
from senhas.models import Categoria


def cadastrar_vaquejada(request):
    """
    Permite o cadastro manual de novos Parques e Vaquejadas (Eventos),
    com definição de premiação, datas, regras e categorias com preços individuais.
    """
    parques = Parque.objects.filter(ativo=True).order_by('nome')

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
                    'responsavel': request.user.get_full_name() if request.user.is_authenticated else 'Organização',
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

        organizador = request.user if request.user.is_authenticated else None
        if not organizador:
            from contas.models import Usuario
            organizador = Usuario.objects.filter(is_superuser=True).first() or Usuario.objects.first()

        evento = Evento.objects.create(
            parque=parque,
            nome=nome_evento,
            data_inicio=data_inicio,
            data_fim=data_fim,
            premiacao_total=premiacao_total,
            circuito_chancela=circuito_chancela,
            descricao=descricao,
            status=Evento.Status.INSCRICOES,
            organizador=organizador
        )

        # 3. Categorias Padrão ou Customizadas
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

        messages.success(request, f'Vaquejada "{evento.nome}" cadastrada com sucesso com todas as categorias!')
        return redirect(f"/cliente/comprar/?evento={evento.id}")

    return render(request, 'eventos/cadastrar.html', {
        'parques': parques
    })
