from django.shortcuts import render, redirect
from django.contrib.auth import views as auth_views
import logging

from django.db import connection
from django.http import FileResponse, HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
import os
from core.models import Contrato, DocumentoContrato


class LandingView(TemplateView):
    template_name = 'landing.html'


class CustomLoginView(auth_views.LoginView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('contratos')  # Redireciona para a URL de contratos
        return super().dispatch(request, *args, **kwargs)
    

def custom_404(request, exception):
    return render(request, '404.html', status=404)


INLINE_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp'}


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

    # Abre no navegador só o que é seguro exibir; o resto vai como download.
    inline = os.path.splitext(file_path)[1].lower() in INLINE_EXTENSIONS
    response = FileResponse(open(file_path, 'rb'), as_attachment=not inline, filename=documento.filename)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private'  # conteúdo com login: nunca em cache compartilhado
    return response


def health(request):
    """Healthcheck do container: 200 só se o banco responde."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logging.getLogger(__name__).exception("health: banco inacessível")
        return HttpResponse("db error", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")
