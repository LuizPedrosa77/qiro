from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from contas.models import Usuario
from eventos.models import Parque, Evento
from senhas.models import Categoria


class EventosETeamTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. Usuário ADM Supremo
        self.adm = Usuario.objects.create_superuser(
            username='adm.geral',
            email='adm@qiro.com.br',
            password='senha_segura_adm',
            papel=Usuario.Papel.ADMIN
        )

        # 2. Usuário Competidor Comum
        self.vaqueiro = Usuario.objects.create_user(
            username='vaqueiro.ze',
            email='ze@vaquejada.com',
            password='senha_vaqueiro',
            papel=Usuario.Papel.COMPETIDOR
        )

        # 3. Usuário Coordenador
        self.coordenador = Usuario.objects.create_user(
            username='dono.parque',
            email='dono@parque.com',
            password='senha_dono',
            papel=Usuario.Papel.COORDENADOR
        )

        # 4. Parque e Evento
        self.parque = Parque.objects.create(
            nome='Parque das Palmeiras',
            cidade='Lagarto',
            estado='SE'
        )

        self.evento = Evento.objects.create(
            parque=self.parque,
            nome='10ª Vaquejada de Lagarto',
            data_inicio=date.today(),
            data_fim=date.today() + timedelta(days=4),
            premiacao_total=300000.00,
            organizador=self.adm,
            status=Evento.Status.INSCRICOES
        )
        self.evento.coordenadores.add(self.coordenador)

    def test_catalogo_completo_vaquejadas_imagem_2(self):
        """Verifica se a tela /vaquejadas/ exibe o título VAQUEJADAS, busca e filtros."""
        res = self.client.get('/vaquejadas/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'VAQUEJADAS')
        self.assertContains(res, 'Digite qual vaquejada você procura')
        self.assertContains(res, 'TODOS ESTADOS')
        self.assertContains(res, '10ª Vaquejada de Lagarto')

    def test_bloqueio_cadastro_evento_para_competidor(self):
        """Competidor comum ou anônimo NÃO PODE acessar o cadastro de evento (exclusivo do ADM)."""
        # Anônimo
        res_anon = self.client.get('/eventos/cadastrar/')
        self.assertEqual(res_anon.status_code, 302)

        # Logado como competidor
        self.client.login(username='vaqueiro.ze', password='senha_vaqueiro')
        res_comp = self.client.get('/eventos/cadastrar/')
        self.assertEqual(res_comp.status_code, 302) # Redireciona com erro

    def test_adm_acessa_e_cadastra_evento_com_fichas_equipe(self):
        """ADM cria evento e aloca Coordenador, Locutor e Juiz salvando tudo no banco de dados."""
        self.client.login(username='adm.geral', password='senha_segura_adm')
        res_get = self.client.get('/eventos/cadastrar/')
        self.assertEqual(res_get.status_code, 200)
        self.assertContains(res_get, 'FICHA 1')
        self.assertContains(res_get, 'FICHA 2')
        self.assertContains(res_get, 'FICHA 3')

        post_data = {
            'parque_id': self.parque.id,
            'nome_evento': '1ª Vaquejada do ADM',
            'circuito_chancela': 'Circuito PE/PB',
            'data_inicio': str(date.today()),
            'data_fim': str(date.today() + timedelta(days=3)),
            'premiacao_total': '150000',
            'preco_aberta': '900',
            'preco_amador': '700',
            'preco_aspirante': '500',
            'incluir_master': 'on',
            'nome_coord_novo': 'Coronel Manoel',
            'cpf_coord_novo': '999.888.777-66',
            'email_coord_novo': 'coronel@parque.com',
            'tel_coord_novo': '(87) 99999-0000',
            'nome_loc_novo': 'Locutor Zezinho',
            'email_loc_novo': 'zezinho@locucao.com',
            'nome_juiz_novo': 'Dr. Juiz Silva',
            'email_juiz_novo': 'juiz.silva@tribunal.com',
        }

        res_post = self.client.post('/eventos/cadastrar/', post_data, follow=True)
        self.assertEqual(res_post.status_code, 200)

        # Confere se o novo evento foi gerado
        evento_novo = Evento.objects.filter(nome='1ª Vaquejada do ADM').first()
        self.assertIsNotNone(evento_novo)

        # Confere se os 3 profissionais foram criados e vinculados no banco de dados
        self.assertTrue(evento_novo.coordenadores.filter(first_name='Coronel Manoel').exists())
        self.assertTrue(evento_novo.locutores.filter(first_name='Locutor Zezinho').exists())
        self.assertTrue(evento_novo.juizes.filter(first_name='Dr. Juiz Silva').exists())

    def test_coordenador_dashboard_privilegiado(self):
        """Coordenador acessa seu painel financeiro e de inscrições."""
        self.client.login(username='dono.parque', password='senha_dono')
        res = self.client.get('/coordenador/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'PAINEL DO COORDENADOR')
        self.assertContains(res, 'Visualização Privilegiada do Proprietário')
        self.assertContains(res, 'Faturamento Arrecadado')
