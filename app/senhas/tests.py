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
        self.operador = Usuario.objects.create_user(
            username='operador_balcao',
            password='testpassword',
            first_name='Claudio',
            papel=Usuario.Papel.SECRETARIA
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

    def test_venda_balcao_presencial_dinheiro_e_recibo(self):
        """Verifica emissão presencial de balcão com Dinheiro e emissão de comprovante térmico."""
        self.client.login(username='operador_balcao', password='testpassword')
        dados = {
            'categoria_id': str(self.categoria.id),
            'numero_senha': 25,
            'cpf': '444.555.666-77',
            'nome': 'Severino Vaqueiro',
            'apelido': 'Biu',
            'estado': 'PB',
            'cidade': 'Campina Grande',
            'telefone': '(83) 98888-7777',
            'cavalo_puxador': 'Apollo Steel',
            'esteireiro': 'Zé',
            'cavalo_esteira': 'Barão',
            'representacao': 'Haras Borborema',
            'forma_pagamento': 'DINHEIRO',
            'valor_recebido': '600.00',
            'tem_boi_tv': 'on',
            'dia_corrida': 'Sexta',
            'imprimir_recibo': 'on'
        }
        res = self.client.post('/senhas/finalizar-inscricao/', data=dados)
        self.assertEqual(res.status_code, 302)

        senha = SenhaInscricao.objects.get(categoria=self.categoria, numero_senha=25)
        self.assertEqual(senha.origem_venda, SenhaInscricao.OrigemVenda.BALCAO_PRESENCIAL)
        self.assertEqual(senha.forma_pagamento, SenhaInscricao.FormaPagamento.DINHEIRO)
        self.assertEqual(senha.status, SenhaInscricao.StatusSenha.PAGA)
        self.assertEqual(senha.operador_secretaria, self.operador)

        # Testa visualização do recibo
        res_recibo = self.client.get(f'/senhas/recibo/{senha.codigo_autenticidade}/')
        self.assertEqual(res_recibo.status_code, 200)
        self.assertContains(res_recibo, 'Severino Vaqueiro')
        self.assertContains(res_recibo, 'Apollo Steel')
        self.assertContains(res_recibo, 'Dinheiro em Espécie')

    def test_venda_balcao_cortesia(self):
        """Verifica emissão de senha cortesia com valor total zerado."""
        dados = {
            'categoria_id': str(self.categoria.id),
            'numero_senha': 30,
            'cpf': '888.999.000-11',
            'nome': 'Convidado Especial',
            'apelido': 'Convidado',
            'estado': 'PE',
            'cidade': 'Recife',
            'cavalo_puxador': 'Trovão',
            'forma_pagamento': 'CORTESIA',
            'autorizado_por': 'Diretoria de Prova',
            'dia_corrida': 'Sábado'
        }
        res = self.client.post('/senhas/finalizar-inscricao/', data=dados)
        self.assertEqual(res.status_code, 302)

        senha = SenhaInscricao.objects.get(categoria=self.categoria, numero_senha=30)
        self.assertEqual(senha.forma_pagamento, SenhaInscricao.FormaPagamento.CORTESIA)
        self.assertEqual(senha.valor_total, 0.00)

    def test_venda_balcao_casadinha(self):
        """Verifica emissão de casadinha (duas senhas vinculadas no balcão)."""
        dados = {
            'categoria_id': str(self.categoria.id),
            'numero_senha': 41,
            'numero_segunda_senha': 42,
            'eh_kit': 'on',
            'cpf': '333.222.111-00',
            'nome': 'Carlos Eduardo',
            'apelido': 'Cadu',
            'estado': 'AL',
            'cidade': 'Maceió',
            'cavalo_puxador': 'Flash Bryan',
            'forma_pagamento': 'CARTAO_DEBITO',
            'dia_corrida': 'Quinta'
        }
        res = self.client.post('/senhas/finalizar-inscricao/', data=dados)
        self.assertEqual(res.status_code, 302)

        s1 = SenhaInscricao.objects.get(categoria=self.categoria, numero_senha=41)
        s2 = SenhaInscricao.objects.get(categoria=self.categoria, numero_senha=42)

        self.assertTrue(s1.eh_kit)
        self.assertEqual(s1.numero_segunda_senha, 42)
        self.assertTrue(s2.eh_kit)
        self.assertEqual(s2.numero_segunda_senha, 41)

    def test_api_buscar_vaqueiro(self):
        """Verifica a busca rápida de vaqueiro por CPF."""
        Usuario.objects.create(
            username='vaq_cadastrado_teste',
            cpf='999.888.777-66',
            first_name='Manoel',
            apelido_locucao='Manoel Vaqueiro',
            cidade='Bezerros',
            estado='PE',
            telefone='81987654321',
            papel=Usuario.Papel.COMPETIDOR
        )
        res = self.client.get('/senhas/api/buscar-vaqueiro/?cpf=99988877766')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['sucesso'])
        self.assertEqual(data['nome'], 'Manoel')
        self.assertEqual(data['apelido'], 'Manoel Vaqueiro')
        self.assertEqual(data['cidade'], 'Bezerros')

    def test_webhook_payload_structure(self):
        """Verifica se o payload gerado para o n8n contém todos os campos necessários."""
        from senhas.webhooks import montar_payload_inscricao
        senha = SenhaInscricao.objects.create(
            evento=self.evento,
            categoria=self.categoria,
            numero_senha=55,
            vaqueiro_puxador=self.operador,
            cavalo_puxador=Animal.objects.create(nome='Cavalo Teste Webhook', funcao=Animal.Funcao.PUXADOR),
            representacao='Haras Webhook N8N',
            valor_total=500.00,
            forma_pagamento=SenhaInscricao.FormaPagamento.PIX,
            status=SenhaInscricao.StatusSenha.PAGA
        )
        payload = montar_payload_inscricao(senha)
        self.assertEqual(payload['evento_tipo'], 'INSCRICAO_CONFIRMADA')
        self.assertEqual(payload['inscricao']['numero_senha'], 55)
        self.assertEqual(payload['atleta_puxador']['nome'], 'Claudio')
        self.assertEqual(payload['animais']['cavalo_puxador'], 'Cavalo Teste Webhook')
        self.assertEqual(payload['equipe']['representacao'], 'Haras Webhook N8N')
        self.assertIn('link_recibo', payload['inscricao'])

    def test_admin_zerar_senhas_com_confirmacao(self):
        """Verifica a segurança do zeramento de senhas: exige a palavra ZERAR."""
        # Cria 3 senhas de teste
        for n in [1, 2, 3]:
            SenhaInscricao.objects.create(
                evento=self.evento,
                categoria=self.categoria,
                numero_senha=n,
                vaqueiro_puxador=self.operador,
                cavalo_puxador=Animal.objects.create(nome=f'Cavalo {n}', funcao=Animal.Funcao.PUXADOR),
                representacao='Haras Teste',
                valor_total=500.00
            )
        self.assertEqual(SenhaInscricao.objects.filter(evento=self.evento).count(), 3)

        # Tentativa com confirmação errada
        res_erro = self.client.post('/senhas/admin/zerar-senhas/', data={
            'evento_id': str(self.evento.id),
            'categoria_id': 'TODAS',
            'escopo': 'TODAS',
            'confirmacao': 'SIM'
        })
        self.assertEqual(res_erro.status_code, 302)
        self.assertEqual(SenhaInscricao.objects.filter(evento=self.evento).count(), 3)

        # Confirmação correta digitando 'ZERAR'
        res_ok = self.client.post('/senhas/admin/zerar-senhas/', data={
            'evento_id': str(self.evento.id),
            'categoria_id': 'TODAS',
            'escopo': 'TODAS',
            'confirmacao': 'ZERAR'
        })
        self.assertEqual(res_ok.status_code, 302)
        self.assertEqual(SenhaInscricao.objects.filter(evento=self.evento).count(), 0)
