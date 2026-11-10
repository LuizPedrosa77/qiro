from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from contas.models import Usuario


class EmailOrCPFBackend(ModelBackend):
    """
    Permite autenticação flexível com CPF ou E-mail ou Username + Senha.
    Trata CPFs digitados com ou sem pontuação (ex: 123.456.789-00 ou 12345678900).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('username') or kwargs.get('email') or kwargs.get('cpf')

        if not username or not password:
            return None

        username_clean = username.strip()
        cpf_numeros = ''.join(filter(str.isdigit, username_clean))

        q_filter = Q(username__iexact=username_clean) | Q(email__iexact=username_clean)
        if cpf_numeros:
            q_filter |= Q(cpf=username_clean) | Q(cpf=cpf_numeros)

        try:
            usuarios = Usuario.objects.filter(q_filter)
            for usuario in usuarios:
                if usuario.check_password(password) and self.user_can_authenticate(usuario):
                    return usuario
        except Exception:
            return None

        return None
