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

    def test_locutor_nao_pode_dar_valeu_boi(self):
        """Regra Fundador: Locutor NÃO pode dar Valeu Boi (apenas Retorno ou Zero)."""
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
        self.assertEqual(response.status_code, 403)
        self.senha.refresh_from_db()
        self.assertEqual(self.senha.total_pontos, 0)

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
