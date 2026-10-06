from usuarios.models import Usuario

def usuario_logado(request):
    if not request.user.is_authenticated:
        return None

    return Usuario.objects.filter(pk=request.user.pk).first()