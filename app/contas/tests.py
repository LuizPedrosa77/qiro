from django.test import TestCase, Client
from contas.models import Usuario
from eventos.models import Parque, Evento
from senhas.models import Categoria, SenhaInscricao


class ClienteFluxoTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.parque = Parque.objects.create(
            nome='Parque Millany',
            cidade='Caruaru',
            estado='PE'
        )
        self.admin = Usuario.objects.create_user(
            username='admin_evento',
            password='testpassword',
            papel=Usuario.Papel.ADMIN
        )
        self.evento = Evento.objects.create(
            parque=self.parque,
            nome='1ª Grande Vaquejada Parque Millany',
            data_inicio='2026-11-09',
            data_fim='2026-11-12',
            status=Evento.Status.EM_ANDAMENTO,
            organizador=self.admin,
            premiacao_total=200000.00
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

    def test_tela_inicial_carrega_com_dois_botoes(self):
        """Verifica se a tela inicial carrega a vitrine de vaquejadas e botões de acesso."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vaquejadas com Inscrições Abertas')
        self.assertContains(response, 'Minhas Senhas / Secretaria')
        self.assertContains(response, 'Área da Pista')
        self.assertContains(response, '1ª Grande Vaquejada Parque Millany')

    def test_cadastro_completo_vaqueiro(self):
        """Testa o cadastro completo com nome, cpf, data de nascimento, endereço e telefone."""
        dados = {
            'nome': 'João',
            'sobrenome': 'Silva Vaqueiro',
            'data_nascimento': '1995-05-15',
            'cpf': '123.456.789-01',
            'email': 'joao.vaqueiro@teste.com',
            'telefone': '(81) 98888-7777',
            'cep': '55000-000',
            'endereco': 'Rua do Parque',
            'numero': '100',
            'bairro': 'Centro',
            'cidade': 'Caruaru',
            'estado': 'PE',
            'senha': 'senhaForte123',
            'confirmar_senha': 'senhaForte123'
        }
        response = self.client.post('/cliente/cadastro/', data=dados)
        self.assertEqual(response.status_code, 302)  # Redireciona para /cliente/secretaria/
        
        user = Usuario.objects.get(email='joao.vaqueiro@teste.com')
        self.assertEqual(user.first_name, 'João')
        self.assertEqual(user.cpf, '12345678901')
        self.assertEqual(user.cidade, 'Caruaru')
        self.assertEqual(user.papel, Usuario.Papel.COMPETIDOR)

    def test_login_com_cpf_e_com_email(self):
        """Verifica se o vaqueiro consegue logar usando CPF ou usando E-mail."""
        user = Usuario.objects.create(
            username='carlos_vaq',
            first_name='Carlos',
            email='carlos@teste.com',
            cpf='98765432100',
            papel=Usuario.Papel.COMPETIDOR
        )
        user.set_password('senha123')
        user.save()

        # Login com E-mail
        res_email = self.client.post('/cliente/login/', {
            'identificador': 'carlos@teste.com',
            'senha': 'senha123'
        })
        self.assertEqual(res_email.status_code, 302)

        self.client.logout()

        # Login com CPF (com máscara)
        res_cpf = self.client.post('/cliente/login/', {
            'identificador': '987.654.321-00',
            'senha': 'senha123'
        })
        self.assertEqual(res_cpf.status_code, 302)

    def test_secretaria_e_compra_de_senha_do_cliente(self):
        """Testa o acesso à Secretaria e a compra de mais senhas pelo cliente logado."""
        vaqueiro = Usuario.objects.create(
            username='renan_vaq',
            first_name='Renan',
            email='renan@teste.com',
            cpf='11122233344',
            papel=Usuario.Papel.COMPETIDOR
        )
        vaqueiro.set_password('senha123')
        vaqueiro.save()

        self.client.login(username='renan@teste.com', password='senha123')

        # Secretaria
        res_sec = self.client.get('/cliente/secretaria/')
        self.assertEqual(res_sec.status_code, 200)
        self.assertContains(res_sec, 'Secretaria do Vaqueiro')
        self.assertContains(res_sec, 'Comprar Mais Senhas')

        # Compra de Senha
        res_compra = self.client.post('/cliente/comprar/', {
            'evento_id': str(self.evento.id),
            'categoria_id': str(self.categoria.id),
            'numero_senha': '155',
            'dia_corrida': 'Sexta',
            'cavalo_puxador': 'Tornado Ouro',
            'esteireiro': 'Junior',
            'cavalo_esteira': 'Prateado',
            'representacao': 'Haras Renan',
            'tem_boi_tv': 'on'
        })
        self.assertEqual(res_compra.status_code, 302)

        # Verifica se a senha foi salva com Boi de TV (+ R$ 100)
        senha = SenhaInscricao.objects.get(vaqueiro_puxador=vaqueiro)
        self.assertTrue(senha.tem_boi_tv)
        self.assertEqual(senha.valor_total, 600.00)
        self.assertEqual(senha.cavalo_puxador.nome, 'Tornado Ouro')
