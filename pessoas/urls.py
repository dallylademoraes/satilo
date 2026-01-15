# satilo/pessoas/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_page, name='home_page'),
    path('pessoas/', views.ListaPessoas.as_view(), name='lista_pessoas'),
    path('pessoas/nova/', views.CriaPessoa.as_view(), name='cria_pessoa'),
    path('pessoas/editar/<int:pk>/', views.EditaPessoa.as_view(), name='edita_pessoa'),
    path('pessoas/definir-eu/<int:person_id>/', views.set_user_person, name='set_user_person'),
    path('pessoas/arvore/', views.arvore_genealogica, name='arvore_genealogica_default'),
    path('pessoas/arvore/<int:pessoa_id>/', views.arvore_genealogica, name='arvore_genealogica'),
    path('accounts/register/', views.register, name='register'),
    path('excluir/<int:pk>/', views.excluir_pessoa, name='excluir_pessoa'), 
]
