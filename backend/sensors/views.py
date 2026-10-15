from django.db import DataError, IntegrityError, transaction
from django.db.models import Max
from django.urls import reverse
from rest_framework.exceptions import NotAuthenticated, ParseError, UnsupportedMediaType
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import BearerAuthentication

from .keys import generate_api_key, hash_api_key
from .models import Sensor
from .serializers import SensorCreateSerializer, SensorSerializer

SYNTAX_ERROR_CODES = {'required', 'invalid', 'null', 'blank'}


def problem_response(status_code, title, *, detail=None, instance=None, errors=None):
    payload = {
        'type': 'about:blank',
        'title': title,
        'status': status_code,
    }
    if detail:
        payload['detail'] = detail
    if instance:
        payload['instance'] = instance
    if errors:
        payload['errors'] = errors
    return Response(
        payload,
        status=status_code,
        content_type='application/problem+json',
    )


def field_errors(serializer_errors):
    items = []
    for field, messages in serializer_errors.items():
        for message in messages:
            items.append({'field': field, 'message': str(message)})
    return items


def validation_status(serializer_errors):
    for messages in serializer_errors.values():
        for message in messages:
            if getattr(message, 'code', None) in SYNTAX_ERROR_CODES:
                return 400
    return 422


def invalid_sensor_response(serializer, request):
    status_code = validation_status(serializer.errors)
    title = 'Niepoprawne żądanie' if status_code == 400 else 'Nie można przetworzyć danych'
    return problem_response(
        status_code,
        title,
        detail='Dane czujnika są niepoprawne.',
        instance=request.path,
        errors=field_errors(serializer.errors),
    )


def sensor_queryset():
    return Sensor.objects.filter(is_active=True).annotate(
        last_measurement_at=Max('measurements__timestamp'),
    ).order_by('id')


def retire_sensor(sensor):
    """Unieważnia klucz. Rekord zostaje, bo wyniki pomiarów mają przetrwać."""
    for _ in range(5):
        sensor.is_active = False
        sensor.api_key_hash = hash_api_key(generate_api_key())
        try:
            with transaction.atomic():
                sensor.save(update_fields=['is_active', 'api_key_hash'])
            return True
        except IntegrityError:
            sensor.refresh_from_db()
    return False


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
        if isinstance(exc, ParseError):
            return problem_response(
                400,
                'Niepoprawne żądanie',
                detail='Treść nie jest poprawnym JSON.',
                instance=self.request.path,
            )
        if isinstance(exc, UnsupportedMediaType):
            return problem_response(
                415,
                'Nieobsługiwany format',
                detail='Treść żądania musi mieć format JSON.',
                instance=self.request.path,
            )
        return super().handle_exception(exc)


class SensorListView(AdministratorSensorMixin, APIView):
    """Lista zarejestrowanych czujników oraz rejestracja nowego czujnika."""

    def get(self, request):
        sensors = sensor_queryset()
        return Response(SensorSerializer(sensors, many=True).data)

    def post(self, request):
        serializer = SensorCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_sensor_response(serializer, request)
        sensor = None
        api_key = None
        for _ in range(5):
            api_key = generate_api_key()
            try:
                sensor = Sensor.objects.create(
                    name=serializer.validated_data['name'],
                    series=serializer.validated_data['seriesId'],
                    api_key_hash=hash_api_key(api_key),
                )
                break
            except IntegrityError:
                sensor = None
        if sensor is None:
            return problem_response(
                422,
                'Nie można przetworzyć danych',
                detail='Nie udało się zarejestrować czujnika.',
                instance=request.path,
            )
        created = find_sensor(sensor.pk)
        payload = SensorSerializer(created).data
        payload['apiKey'] = api_key
        return Response(
            payload,
            status=201,
            headers={'Location': reverse('sensor-detail', kwargs={'sensor_id': sensor.pk})},
        )


class SensorDetailView(AdministratorSensorMixin, APIView):
    """Odczyt i wyrejestrowanie jednego czujnika."""

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

    def delete(self, request, sensor_id):
        sensor = find_sensor(sensor_id)
        if sensor is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Czujnik nie istnieje.',
                instance=request.path,
            )
        with transaction.atomic():
            locked = (
                Sensor.objects.select_for_update()
                .filter(pk=sensor.pk, is_active=True)
                .first()
            )
            if locked is None:
                return problem_response(
                    404,
                    'Nie znaleziono',
                    detail='Czujnik nie istnieje.',
                    instance=request.path,
                )
            if not retire_sensor(locked):
                return problem_response(
                    422,
                    'Nie można przetworzyć danych',
                    detail='Nie udało się wyrejestrować czujnika.',
                    instance=request.path,
                )
        return Response(status=204)
