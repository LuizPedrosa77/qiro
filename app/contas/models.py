import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    class Papel(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrador da Plataforma'
        ORGANIZADOR = 'ORGANIZADOR', 'Organizador do Evento'
        SECRETARIA = 'SECRETARIA', 'Operador da Secretaria'
        LOCUTOR = 'LOCUTOR', 'Locutor Oficial'
        JUIZ = 'JUIZ', 'Juiz de Pista / TV'
        VETERINARIO = 'VETERINARIO', 'Juiz de Bem-Estar / Veterinário'
        COMPETIDOR = 'COMPETIDOR', 'Vaqueiro / Competidor'
        PUBLICO = 'PUBLICO', 'Espectador / Usuário Geral'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.CharField(max_length=14, unique=True, null=True, blank=True, db_index=True)
    telefone = models.CharField(max_length=20, blank=True)
    papel = models.CharField(max_length=20, choices=Papel.choices, default=Papel.COMPETIDOR, db_index=True)
    apelido_locucao = models.CharField(max_length=100, blank=True, help_text="Nome chamado pelo locutor na pista")
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    foto_perfil = models.ImageField(upload_to='perfis/', blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['first_name', 'username']

    def __str__(self):
        return f"{self.apelido_locucao or self.get_full_name() or self.username} ({self.get_papel_display()})"
