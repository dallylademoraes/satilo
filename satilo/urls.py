# satilo/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importe suas ViewSets e APIViews DO NOVO ARQUIVO api_views.py
from rest_framework.routers import DefaultRouter
from pessoas.api_views import PessoaViewSet, CustomAuthToken, RegisterUserAPIView

# Crie um roteador para suas ViewSets
router = DefaultRouter()
router.register(r'pessoas', PessoaViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pessoas.urls')), # Inclui as URLs da sua app 'pessoas' (views tradicionais)
    path('accounts/', include('django.contrib.auth.urls')),

    # URLs da API
    path('api/', include(router.urls)), # Inclui todas as URLs geradas pelo roteador
    path('api/auth/', CustomAuthToken.as_view(), name='api_token_auth'),
    path('api/register/', RegisterUserAPIView.as_view(), name='api_register'),
]

# Apenas para servir arquivos de mídia (fotos) em ambiente de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
