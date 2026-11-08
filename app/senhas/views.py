from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from eventos.models import Evento
from senhas.models import Categoria, SenhaInscricao
from competidores.models import Animal
from contas.models import Usuario


def mapa_senhas(request):
    """
    Tela oficial da Secretaria para escolha de senhas e compra (Mockup Imagens 7 e 8).
    Exibe as abas das categorias e a grade de 75 a 100 senhas com cores branco e vermelho.
    """
    evento = Evento.objects.filter(status=Evento.Status.EM_ANDAMENTO).first() or Evento.objects.first()
    categorias = Categoria.objects.filter(evento=evento, ativo=True)
    
    categoria_id = request.GET.get('categoria')
    if categoria_id:
        categoria_atual = get_object_or_404(Categoria, id=categoria_id)
    else:
        categoria_atual = categorias.filter(tipo=Categoria.TipoCategoria.ABERTA).first() or categorias.first()

    dia_selecionado = request.GET.get('dia', 'Quinta')

    # Senhas ocupadas
    senhas_feitas = set(
        SenhaInscricao.objects.filter(categoria=categoria_atual).values_list('numero_senha', flat=True)
    )

    # Grade de 1 a limite_senhas (ou padrão 75 como no mockup)
    total_grid = categoria_atual.limite_senhas if categoria_atual else 75
    grade_senhas = []
    for num in range(1, total_grid + 1):
        grade_senhas.append({
            'numero': num,
            'ocupada': num in senhas_feitas
        })

    # Senha selecionada para compra
    senha_selecionada = int(request.GET.get('senha_num', 10))

    return render(request, 'senhas/mapa.html', {
        'evento': evento,
        'categorias': categorias,
        'categoria_atual': categoria_atual,
        'dia_selecionado': dia_selecionado,
        'grade_senhas': grade_senhas,
        'senha_selecionada': senha_selecionada,
    })


def finalizar_inscricao(request):
    """
    Processa o formulário de cadastro de senha e checkout (Mockup Imagem 8).
    """
    if request.method == 'POST':
        categoria_id = request.POST.get('categoria_id')
        categoria = get_object_or_404(Categoria, id=categoria_id)
        numero_senha = int(request.POST.get('numero_senha', 1))
        
        cpf = request.POST.get('cpf', '').strip()
        nome = request.POST.get('nome', '').strip()
        apelido = request.POST.get('apelido', '').strip()
        estado = request.POST.get('estado', 'PE').strip()
        cidade = request.POST.get('cidade', 'Caruaru').strip()
        
        cavalo_puxador_nome = request.POST.get('cavalo_puxador', 'Cavalo Puxador')
        esteireiro_nome = request.POST.get('esteireiro', 'Esteireiro')
        cavalo_esteira_nome = request.POST.get('cavalo_esteira', 'Cavalo Esteira')
        representacao = request.POST.get('representacao', 'Haras Geral')
        
        tem_boi_tv = request.POST.get('tem_boi_tv') == 'on'

        # Busca ou cria vaqueiro
        puxador, _ = Usuario.objects.get_or_create(
            cpf=cpf if cpf else None,
            defaults={
                'username': f"vaq_{numero_senha}_{cpf.replace('.', '').replace('-', '')}" if cpf else f"vaq_{numero_senha}",
                'first_name': nome,
                'apelido_locucao': apelido,
                'cidade': cidade,
                'estado': estado,
                'papel': Usuario.Papel.COMPETIDOR
            }
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

        valor_total = categoria.valor_senha + (categoria.valor_boi_tv if tem_boi_tv else 0)

        # Cria a inscrição
        senha, created = SenhaInscricao.objects.get_or_create(
            evento=categoria.evento,
            categoria=categoria,
            numero_senha=numero_senha,
            defaults={
                'vaqueiro_puxador': puxador,
                'cavalo_puxador': cav_pux,
                'cavalo_esteireiro': cav_est,
                'representacao': representacao,
                'tem_boi_tv': tem_boi_tv,
                'status': SenhaInscricao.StatusSenha.PAGA,
                'valor_total': valor_total,
                'dia_corrida': request.POST.get('dia_corrida', 'Quinta')
            }
        )

        messages.success(request, f"Senha #{numero_senha} da {categoria.nome_exibicao} confirmada com sucesso!")
        return redirect(f"/senhas/mapa/?categoria={categoria.id}")

    return redirect("/senhas/mapa/")
