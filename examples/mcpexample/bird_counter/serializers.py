from rest_framework.serializers import ModelSerializer

from .models import Bird


class BirdSerializer(ModelSerializer):
    """Serializer for the Bird model"""
    class Meta:
        model = Bird
        fields = ['species', 'count']