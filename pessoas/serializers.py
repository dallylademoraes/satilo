# pessoas/serializers.py
from rest_framework import serializers
from .models import Pessoa
from django.contrib.auth.models import User
from django.conf import settings # <-- Importe settings para acessar MEDIA_URL

# Serializer para o modelo User (simplificado para o que geralmente é necessário na API)
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']

class PessoaSerializer(serializers.ModelSerializer):
    # Campos de relacionamento para exibir informações úteis
    pai_data = serializers.SerializerMethodField()
    mae_data = serializers.SerializerMethodField()
    conjuge_data = serializers.SerializerMethodField()
    owner_data = UserSerializer(source='owner', read_only=True) # Exibe o nome do owner

    # CORREÇÃO: Use SerializerMethodField para 'foto_url' para construir a URL completa
    foto_url = serializers.SerializerMethodField()
    idade = serializers.CharField(source='get_age', read_only=True)
    status_vida = serializers.CharField(source='get_status_vida_display', read_only=True)

    # NOVO: Adicionar children_ids como SerializerMethodField
    children_ids = serializers.SerializerMethodField() # <-- NOVO CAMPO AQUI!

    class Meta:
        model = Pessoa
        fields = [
            'id', 'nome', 'genero', 'data_nascimento', 'local_nascimento',
            'estado_nascimento', 'data_falecimento', 'data_falecimento_incerta', # data_falecimento_incerta
            'historia_pessoal', # <-- Alterado de historico_pessoal
            'foto', 'foto_url', 'owner', 'owner_data',
            'pai', 'pai_data', 'mae', 'mae_data', 'conjuge', 'conjuge_data',
            'idade', 'status_vida',
            'children_ids', # <-- Adicionar ao fields
            # Campos adicionais que você pode querer enviar da API
            # 'relacao', 'is_root_display_node', 'is_user_selected', # Estes são campos calculados na view, não no serializer direto do modelo
        ]
        read_only_fields = ['owner', 'foto_url', 'idade', 'status_vida', 'owner_data', 'children_ids'] # <-- children_ids também é read_only

    # NOVO MÉTODO: get_foto_url para retornar a URL completa
    def get_foto_url(self, obj):
        if obj.foto and hasattr(obj.foto, 'url'):
            request = self.context.get('request')
            if request is not None:
                # Construa a URL absoluta. Adapte o 'http://127.0.0.1:8000' para o seu domínio em produção!
                return request.build_absolute_uri(obj.foto.url)
            return obj.foto.url # Fallback se a requisição não estiver no contexto
        # Retorna None se não houver foto, para que o frontend use o fallback 'assets/img/sem-foto.jpg'
        return None

    # NOVO MÉTODO: get_children_ids para retornar uma lista de IDs dos filhos
    def get_children_ids(self, obj):
        # Supondo que você tem um RelatedManager para filhos, por exemplo, via ForeignKey reversa
        # Se você definiu 'parent_person' ForeignKey em Pessoa apontando para si mesma,
        # você pode ter um related_name como 'children' para acessar os filhos.
        # Ex: children = Pessoa.objects.filter(pai=obj) | Pessoa.objects.filter(mae=obj)
        # Ou se no seu modelo Pessoa você tem um campo 'filhos' (menos comum)
        
        # A forma mais robusta é consultar o modelo Pessoa onde pai ou mae seja o obj atual
        children_pks = Pessoa.objects.filter(pai=obj).values_list('id', flat=True) \
                     | Pessoa.objects.filter(mae=obj).values_list('id', flat=True)
        return list(children_pks.distinct()) # Retorna uma lista de IDs únicos dos filhos

    # Métodos para obter dados de relacionamento aninhados (apenas leitura)
    def get_pai_data(self, obj):
        if obj.pai:
            return {'id': obj.pai.id, 'nome': obj.pai.nome}
        return None

    def get_mae_data(self, obj):
        if obj.mae:
            return {'id': obj.mae.id, 'nome': obj.mae.nome}
        return None

    def get_conjuge_data(self, obj):
        if obj.conjuge:
            return {'id': obj.conjuge.id, 'nome': obj.conjuge.nome}
        return None