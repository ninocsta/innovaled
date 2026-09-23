from django.contrib import admin
from django.urls import path
from django.urls import include
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, servir_arquivo_contrato, LandingView, health


urlpatterns = [
    path('', LandingView.as_view(), name='landing'),
    path('health/', health, name='health'),

    path('admin/', admin.site.urls),
    path('app/', include('core.urls')),  # Include core app URLs

    path('app/login/', CustomLoginView.as_view(), name='login'),  # Usa a CustomLoginView aqui
    path('app/logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('app/contrato/arquivo/<int:documento_id>/', servir_arquivo_contrato, name='servir_arquivo_contrato'),

]
