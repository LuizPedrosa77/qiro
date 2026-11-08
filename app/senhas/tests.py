from django.test import TestCase, Client
from contas.models import Usuario
from eventos.models import Parque, Evento
from competidores.models import Animal
from senhas.models import Categoria, SenhaInscricao


class SenhasInscricaoTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.organizador = Usuario.objects.create_user(
            username='organizador_senhas',
            password='testpassword',
            papel=Usuario.Papel.ORGANIZADOR
        )
        self.parque = Parque.objects.create(
            nome='Parque Millany',
            cidade='Caruaru',
            estado='PE'
        )
        self.evento = Evento.objects.create(
            parque=self.parque,
            nome='Grande Vaquejada Teste',
            data_inicio='2026-11-08',
            data_fim='2026-11-10',
            status=Evento.Status.EM_ANDAMENTO,
            organizador=self.organizador
        )
        self.categoria = Categoria.objects.create(
            evento=self.evento,
            nome_exibicao='Aspirante',
            tipo=Categoria.TipoCategoria.ASPIRANTE,
            valor_senha=500.00,
            valor_boi_tv=100.00,
            limite_senhas=75,
            pontos_para_bater=20
        )

    def test_grade_senhas_e_carregamento_mapa(self):
        """Verifica se a tela do mapa carrega com a categoria e a grade de 75 senhas."""
        response = self.client.get(f'/senhas/mapa/?categoria={self.categoria.id}')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aspirante')
        self.assertEqual(len(response.context['grade_senhas']), 75)

    def test_checkout_senha_com_boi_tv(self):
        """Verifica formulário de cadastro de senha com opção Boi de TV (+ R$ 100)."""
        dados_formulario = {
            'categoria_id': str(self.categoria.id),
            'numero_senha': 10,
            'cpf': '123.456.789-00',
            'nome': 'Romulo Emanuel',
            'apelido': 'Romulo',
            'estado': 'PE',
            'cidade': 'Caruaru',
            'cavalo_puxador': 'Jeck Yease',
            'esteireiro': 'Junior',
            'cavalo_esteira': 'King',
            'representacao': 'Haras Millany',
            'tem_boi_tv': 'on',
            'dia_corrida': 'Quinta'
        }
        response = self.client.post('/senhas/finalizar-inscricao/', data=dados_formulario)
        self.assertEqual(response.status_code, 302)  # Redirecionamento após salvar

        senha = SenhaInscricao.objects.get(categoria=self.categoria, numero_senha=10)
        self.assertTrue(senha.tem_boi_tv)
        self.assertEqual(senha.valor_total, 600.00)  # 500 + 100 de TV
        self.assertEqual(senha.status, SenhaInscricao.StatusSenha.PAGA)
        self.assertEqual(senha.cavalo_puxador.nome, 'Jeck Yease')
