from django.shortcuts import render
from rest_framework.generics import UpdateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView
from rest_framework.serializers import ModelSerializer

from mcp_server import drf_publish_create_mcp_tool
from .models import Location

# Create your views here.

class LocationSerializer(ModelSerializer):
    """
    Serializer for the Location model.
    """
    class Meta:
        model = Location
        fields = ('name','description','city')



class LocationAPIView(CreateAPIView):
    """
    API view to retrieve, update or delete a Location instance.
    """
    serializer_class = LocationSerializer