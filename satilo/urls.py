# satilo/satilo/urls.py

from django.contrib import admin
from django.urls import path, include # Certifique-se de que 'include' está importado
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pessoas.urls')), # Inclui as URLs da sua app 'pessoas'
    path('accounts/', include('django.contrib.auth.urls')), # NOVO: Inclui as URLs de autenticação do Django
]

# Apenas para servir arquivos de mídia (fotos) em ambiente de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)