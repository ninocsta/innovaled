from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, servir_arquivo_contrato


urlpatterns = [
    path('admin/', admin.site.urls),    
    path('', include('core.urls')),  # Include core app URLs

    path('login/', CustomLoginView.as_view(), name='login'),  # Usa a CustomLoginView aqui
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('contrato/arquivo/<int:documento_id>/', servir_arquivo_contrato, name='servir_arquivo_contrato'),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
