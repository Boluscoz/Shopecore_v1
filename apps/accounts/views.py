from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.decorators import api_view

# Create your views here.


@api_view(['POST'])
def register(request):
    person = {'name': 'boluwatife', 'age': 14}
    return Response(person)
