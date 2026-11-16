import json
from django.test import TestCase, Client
from django.urls import reverse
from contas.models import Usuario
from eventos.models import Parque, Evento
from competidores.models import Animal
from senhas.models import Categoria, SenhaInscricao
from pista.models import BoiPassada, ChatPista


class PistaRegrasTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.organizador = Usuario.objects.create_user(
            username='organizador_teste',
            password='testpassword',
            papel=Usuario.Papel.ORGANIZADOR
        )
        self.parque = Parque.objects.create(
            nome='Parque Teste',
            cidade='Caruaru',
            estado='PE'
        )
        self.evento = Evento.objects.create(
            parque=self.parque,
            nome='Vaquejada Teste',
            data_inicio='2026-11-08',
            data_fim='2026-11-10',
            status=Evento.Status.EM_ANDAMENTO,
            organizador=self.organizador
        )
        self.categoria = Categoria.objects.create(
            evento=self.evento,
            nome_exibicao='Aberta',
            tipo=Categoria.TipoCategoria.ABERTA,
            valor_senha=800.00,
            valor_boi_tv=100.00,
            limite_senhas=75,
            pontos_para_bater=20
        )
        self.vaqueiro = Usuario.objects.create_user(
            username='vaqueiro_1',
            password='testpassword',
            papel=Usuario.Papel.COMPETIDOR,
            first_name='Vaqueiro Teste'
        )
        self.cavalo = Animal.objects.create(
            nome='Cavalo Veloz',
            proprietario=self.vaqueiro
        )
        self.senha = SenhaInscricao.objects.create(
            evento=self.evento,
            categoria=self.categoria,
            numero_senha=1001,
            vaqueiro_puxador=self.vaqueiro,
            cavalo_puxador=self.cavalo,
            status=SenhaInscricao.StatusSenha.NA_PISTA,
            valor_total=800.00
        )

    def test_locutor_pode_dar_valeu_boi_com_pontuacao_atualizada(self):
        """Regra Atualizada: Locutor pode registrar Valeu Boi (+10 pontos atualizados)."""
        response = self.client.post(
            '/pista/julgamento/',
            data=json.dumps({
                'senha_id': str(self.senha.id),
                'numero_boi': 1,
                'decisao': 'VALEU_BOI',
                'origem': 'LOCUTOR'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.senha.refresh_from_db()
        self.assertEqual(self.senha.total_pontos, 10)
        passada = BoiPassada.objects.get(senha=self.senha, numero_boi=1)
        self.assertEqual(passada.julgamento_locutor, 'VALEU_BOI')
        self.assertEqual(passada.pontos_obtidos, 10)

    def test_locutor_pode_dar_zero_e_elimina(self):
        """Regra Atualizada: Locutor pode registrar Zero (elimina senha)."""
        response = self.client.post(
            '/pista/julgamento/',
            data=json.dumps({
                'senha_id': str(self.senha.id),
                'numero_boi': 1,
                'decisao': 'ZERO',
                'origem': 'LOCUTOR'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.senha.refresh_from_db()
        self.assertEqual(self.senha.status, SenhaInscricao.StatusSenha.ELIMINADA)

    def test_locutor_pode_dar_retorno(self):
        """Regra Fundador: Locutor pode dar Retorno."""
        response = self.client.post(
            '/pista/julgamento/',
            data=json.dumps({
                'senha_id': str(self.senha.id),
                'numero_boi': 1,
                'decisao': 'RETORNO',
                'origem': 'LOCUTOR'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        passada = BoiPassada.objects.get(senha=self.senha, numero_boi=1)
        self.assertEqual(passada.julgamento_locutor, 'RETORNO')

    def test_zero_elimina_senha_da_matriz(self):
        """Regra Fundador: Se der Zero, a senha é desclassificada/eliminada da matriz."""
        response = self.client.post(
            '/pista/julgamento/',
            data=json.dumps({
                'senha_id': str(self.senha.id),
                'numero_boi': 1,
                'decisao': 'ZERO',
                'origem': 'JUIZ'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.senha.refresh_from_db()
        self.assertEqual(self.senha.status, SenhaInscricao.StatusSenha.ELIMINADA)

    def test_juiz_valeu_boi_soma_pontos(self):
        """Regra Fundador: Juiz concede 10 pontos ao Valeu Boi."""
        response = self.client.post(
            '/pista/julgamento/',
            data=json.dumps({
                'senha_id': str(self.senha.id),
                'numero_boi': 1,
                'decisao': 'VALEU_BOI',
                'origem': 'JUIZ'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.senha.refresh_from_db()
        self.assertEqual(self.senha.total_pontos, 10)

    def test_painel_locutor_deck_e_permissoes(self):
        """Verifica se a tela do locutor requer login e renderiza o baralho e botões."""
        # Não logado -> redireciona para login da equipe
        resp_unauth = self.client.get('/pista/locutor/')
        self.assertEqual(resp_unauth.status_code, 302)
        self.assertIn('/equipe/login/', resp_unauth.url)

        # Logado como Locutor
        locutor_user = Usuario.objects.create_user(
            username='locutor_oficial',
            password='testpassword',
            papel=Usuario.Papel.LOCUTOR
        )
        self.client.login(username='locutor_oficial', password='testpassword')
        resp = self.client.get('/pista/locutor/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Cabine de Locução Oficial', content)
        self.assertIn('Puxar Novo Cartão', content)
        self.assertIn('Puxar Cartão Anterior', content)
        self.assertIn('VALEU BOI!', content)
        self.assertIn('ZERO', content)
        self.assertIn('RETORNO', content)
