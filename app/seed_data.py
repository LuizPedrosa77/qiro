import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from contas.models import Usuario
from eventos.models import Parque, Evento
from competidores.models import Haras, Animal
from senhas.models import Categoria, SenhaInscricao
from pista.models import BoiPassada, ChatPista

print("==> Criando Superusuário Administrador...")
admin_user, _ = Usuario.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@qiro.com.br',
        'first_name': 'Administrador',
        'last_name': 'QIRO',
        'papel': Usuario.Papel.ADMIN,
        'is_staff': True,
        'is_superuser': True,
    }
)
admin_user.set_password('qiro1234')
admin_user.save()

print("==> Criando Parque Millany...")
parque, _ = Parque.objects.get_or_create(
    nome='Parque Millany',
    defaults={
        'cidade': 'Caruaru',
        'estado': 'PE',
        'responsavel': 'Diretoria Parque Millany',
        'telefone': '(81) 99999-0000',
    }
)

print("==> Criando Haras e Representações...")
haras, _ = Haras.objects.get_or_create(
    nome='Super Copa de Vaquejada',
    defaults={'cidade': 'Caruaru', 'estado': 'PE', 'proprietario': admin_user}
)

print("==> Criando Evento Principal...")
evento, _ = Evento.objects.get_or_create(
    nome='Grande Vaquejada do Parque Millany',
    defaults={
        'parque': parque,
        'edicao': '1ª Edição',
        'data_inicio': date(2026, 11, 10),
        'data_fim': date(2026, 11, 15),
        'premiacao_total': 150000.00,
        'status': Evento.Status.EM_ANDAMENTO,
        'organizador': admin_user
    }
)

print("==> Criando Categorias...")
categorias_data = [
    (Categoria.TipoCategoria.ASPIRANTE, 'Mapa Aspirante', 310.00, 100),
    (Categoria.TipoCategoria.AMADOR, 'Mapa Amador', 380.00, 80),
    (Categoria.TipoCategoria.ABERTA, 'Mapa Aberta', 410.00, 80),
    (Categoria.TipoCategoria.MASTER, 'Mapa Master', 300.00, 50),
    (Categoria.TipoCategoria.JOVEM, 'Mapa Jovem', 200.00, 40),
]

cat_objs = {}
for idx, (tipo, nome, valor, limite) in enumerate(categorias_data, start=1):
    cat, _ = Categoria.objects.get_or_create(
        evento=evento,
        tipo=tipo,
        defaults={
            'nome_exibicao': nome,
            'valor_senha': valor,
            'valor_boi_tv': 100.00,
            'limite_senhas': limite,
            'ordem_apresentacao': idx
        }
    )
    cat_objs[tipo] = cat

print("==> Criando Vaqueiros Competidores...")
vaqueiros_data = [
    ('kleber.leite', 'Kleber', 'Leite', 'Kleber Leite', '055.483.014-30', 'Caruaru', 'PE'),
    ('matheus.leonardo', 'Matheus', 'Leonardo', 'Matheus Leonardo', '123.456.789-00', 'Caruaru', 'PE'),
    ('romulo.emanuel', 'Romulo', 'Emanuel', 'Romulo Emanuel', '098.765.432-11', 'Caruaru', 'PE'),
    ('junior.vaqueiro', 'Junior', 'Silva', 'Junior', '222.333.444-55', 'Bezerros', 'PE'),
    ('carlos.vaqueiro', 'Carlos', 'Eduardo', 'Carlos', '333.444.555-66', 'Gravatá', 'PE'),
    ('renan.vaqueiro', 'Renan', 'Melo', 'Renan', '444.555.666-77', 'Surubim', 'PE'),
]

vaq_objs = {}
for username, fname, lname, apelido, cpf, cid, uf in vaqueiros_data:
    v, _ = Usuario.objects.get_or_create(
        username=username,
        defaults={
            'first_name': fname,
            'last_name': lname,
            'apelido_locucao': apelido,
            'cpf': cpf,
            'cidade': cid,
            'estado': uf,
            'papel': Usuario.Papel.COMPETIDOR
        }
    )
    v.set_password('qiro123')
    v.save()
    vaq_objs[username] = v

print("==> Criando Cavalos...")
cavalo_puxador, _ = Animal.objects.get_or_create(
    nome='Jeck Yease',
    defaults={
        'funcao': Animal.Funcao.PUXADOR,
        'raca': 'Quarto de Milha',
        'haras': haras,
        'proprietario': vaq_objs['kleber.leite']
    }
)

cavalo_esteira, _ = Animal.objects.get_or_create(
    nome='King',
    defaults={
        'funcao': Animal.Funcao.ESTEIRA,
        'raca': 'Quarto de Milha',
        'haras': haras,
        'proprietario': vaq_objs['matheus.leonardo']
    }
)

print("==> Criando Senha Atual #3026 (Conjunto Atual dos Mockups)...")
cat_aberta = cat_objs[Categoria.TipoCategoria.ABERTA]

senha_atual, _ = SenhaInscricao.objects.get_or_create(
    evento=evento,
    categoria=cat_aberta,
    numero_senha=3026,
    defaults={
        'vaqueiro_puxador': vaq_objs['kleber.leite'],
        'cavalo_puxador': cavalo_puxador,
        'vaqueiro_esteireiro': vaq_objs['matheus.leonardo'],
        'cavalo_esteireiro': cavalo_esteira,
        'representacao': 'Super Copa de Vaquejada - Geral',
        'tem_boi_tv': True,
        'status': SenhaInscricao.StatusSenha.NA_PISTA,
        'rodizio_bloco': 1,
        'ordem_fila': 1,
        'total_pontos': 30,
        'valor_total': 510.00
    }
)

# 4 Bois da Senha 3026 (3 Valeu Boi e 1 Zero)
for num, julg, pts in [
    (1, BoiPassada.JulgamentoJuiz.VALEU_BOI, 10),
    (2, BoiPassada.JulgamentoJuiz.VALEU_BOI, 10),
    (3, BoiPassada.JulgamentoJuiz.VALEU_BOI, 10),
    (4, BoiPassada.JulgamentoJuiz.ZERO, 0)
]:
    BoiPassada.objects.get_or_create(
        senha=senha_atual,
        numero_boi=num,
        defaults={'julgamento_juiz': julg, 'pontos_obtidos': pts}
    )

print("==> Criando Próximos Conjuntos (Senhas #3027 e #3028)...")
for num_s, pts in [(3027, 20), (3028, 20)]:
    s, _ = SenhaInscricao.objects.get_or_create(
        evento=evento,
        categoria=cat_aberta,
        numero_senha=num_s,
        defaults={
            'vaqueiro_puxador': vaq_objs['kleber.leite'],
            'cavalo_puxador': cavalo_puxador,
            'vaqueiro_esteireiro': vaq_objs['matheus.leonardo'],
            'cavalo_esteireiro': cavalo_esteira,
            'representacao': 'Super Copa de Vaquejada - Geral',
            'status': SenhaInscricao.StatusSenha.PAGA,
            'rodizio_bloco': 1,
            'ordem_fila': num_s - 3025,
            'total_pontos': pts,
            'valor_total': 410.00
        }
    )
    for b_num in [1, 2]:
        BoiPassada.objects.get_or_create(
            senha=s,
            numero_boi=b_num,
            defaults={'julgamento_juiz': BoiPassada.JulgamentoJuiz.VALEU_BOI, 'pontos_obtidos': 10}
        )

print("==> Criando Bloco de Rodízio Atual (Senhas 3040 a 3050)...")
pares = [
    (3040, 'romulo.emanuel', 'junior.vaqueiro'),
    (3041, 'junior.vaqueiro', 'kleber.leite'),
    (3042, 'matheus.leonardo', 'carlos.vaqueiro'),
    (3043, 'kleber.leite', 'junior.vaqueiro'),
    (3044, 'romulo.emanuel', 'matheus.leonardo'),
    (3045, 'carlos.vaqueiro', 'renan.vaqueiro'),
    (3046, 'carlos.vaqueiro', 'romulo.emanuel'),
    (3047, 'junior.vaqueiro', 'romulo.emanuel'),
    (3048, 'matheus.leonardo', 'kleber.leite'),
    (3049, 'kleber.leite', 'junior.vaqueiro'),
    (3050, 'renan.vaqueiro', 'romulo.emanuel'),
]

for num_s, pux_user, est_user in pares:
    SenhaInscricao.objects.get_or_create(
        evento=evento,
        categoria=cat_aberta,
        numero_senha=num_s,
        defaults={
            'vaqueiro_puxador': vaq_objs[pux_user],
            'cavalo_puxador': cavalo_puxador,
            'vaqueiro_esteireiro': vaq_objs[est_user],
            'cavalo_esteireiro': cavalo_esteira,
            'representacao': 'Haras e Parque Millany',
            'status': SenhaInscricao.StatusSenha.PAGA,
            'rodizio_bloco': 2,
            'ordem_fila': num_s - 3039,
            'total_pontos': 0,
            'valor_total': 410.00
        }
    )

print("==> Criando Mensagens de Atenção da Secretaria...")
alertas = [
    "Incluir a senha 1023 no próximo rodízio",
    "A senha 1524 foi desclassificada",
    "A senha 2536 está com boi na alternativa",
]
for msg in alertas:
    ChatPista.objects.get_or_create(
        evento=evento,
        remetente=admin_user,
        tipo=ChatPista.TipoMensagem.ALERTA_SECRETARIA,
        mensagem=msg
    )

print("\n=======================================================")
print("  BANCO QIRO POPULADO COM SUCESSO NO POSTGRESQL! ")
print("=======================================================")
