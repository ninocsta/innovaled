from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
from django.http import FileResponse, HttpResponseForbidden
from django.conf import settings
from django.shortcuts import get_object_or_404
import os
from core.models import Contrato, DocumentoContrato


class CustomLoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('contratos')  # Redireciona para a URL de contratos
        return super().dispatch(request, *args, **kwargs)
    

def custom_404(request, exception):
    return render(request, '404.html', status=404)


def servir_arquivo_contrato(request, documento_id):
    documento = get_object_or_404(DocumentoContrato, pk=documento_id)

    # Apenas usuários autenticados podem acessar
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Você não tem permissão para acessar este arquivo.")

    # Caminho do arquivo no servidor
    file_path = os.path.join(settings.MEDIA_ROOT, documento.arquivo.name)

    # Verificar se o arquivo existe
    if not os.path.exists(file_path):
        return HttpResponseForbidden("Arquivo não encontrado.")

    return FileResponse(open(file_path, 'rb'))
