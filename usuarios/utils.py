from usuarios.models import Usuario

# SUPERUSUÁRIO NÃO ESTÁ NA TABELA DE USUÁRIOS E SIM NA DE USER. LOGO SE FOR SUPERUSUÁRIO ESSE MÉTODO RETORNA None.
def usuario_logado(request):
    if not request.user.is_authenticated:
        return None

    return Usuario.objects.filter(pk=request.user.pk).first()
