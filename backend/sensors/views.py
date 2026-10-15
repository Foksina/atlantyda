from django.db import DataError
from django.db.models import Max
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import BearerAuthentication

from .models import Sensor
from .serializers import SensorSerializer


def problem_response(status_code, title, *, detail=None, instance=None):
    payload = {
        'type': 'about:blank',
        'title': title,
        'status': status_code,
    }
    if detail:
        payload['detail'] = detail
    if instance:
        payload['instance'] = instance
    return Response(
        payload,
        status=status_code,
        content_type='application/problem+json',
    )


def sensor_queryset():
    return Sensor.objects.annotate(
        last_measurement_at=Max('measurements__timestamp'),
    ).order_by('id')


def find_sensor(sensor_id):
    try:
        pk = int(sensor_id)
    except (TypeError, ValueError):
        return None
    if pk < 1:
        return None
    try:
        return sensor_queryset().filter(pk=pk).first()
    except (DataError, OverflowError):
        return None


class AdministratorSensorMixin:
    authentication_classes = [BearerAuthentication]
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        if isinstance(exc, NotAuthenticated):
            return problem_response(
                401,
                'Brak autoryzacji',
                detail='Wymagany jest token administratora.',
                instance=self.request.path,
            )
        return super().handle_exception(exc)


class SensorListView(AdministratorSensorMixin, APIView):
    """Lista zarejestrowanych czujników."""

    def get(self, request):
        sensors = sensor_queryset()
        return Response(SensorSerializer(sensors, many=True).data)


class SensorDetailView(AdministratorSensorMixin, APIView):
    """Odczyt jednego czujnika."""

    def get(self, request, sensor_id):
        sensor = find_sensor(sensor_id)
        if sensor is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Czujnik nie istnieje.',
                instance=request.path,
            )
        return Response(SensorSerializer(sensor).data)
