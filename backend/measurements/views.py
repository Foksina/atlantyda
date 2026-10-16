from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from sensors.models import Sensor
from series.models import Series

from .authentication import sensor_from_api_key
from .models import Measurement
from .serializers import MeasurementInputSerializer

SYNTAX_ERROR_CODES = {'required', 'invalid', 'null', 'blank'}
FUTURE_LIMIT = timedelta(minutes=5)


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


def invalid_measurement_response(serializer, request):
    status_code = validation_status(serializer.errors)
    title = 'Niepoprawne żądanie' if status_code == 400 else 'Nie można przetworzyć danych'
    return problem_response(
        status_code,
        title,
        detail='Dane pomiaru są niepoprawne.',
        instance=request.path,
        errors=field_errors(serializer.errors),
    )


def unauthorized(request):
    return problem_response(
        401,
        'Brak autoryzacji',
        detail='Wymagany jest klucz API czujnika.',
        instance=request.path,
    )


class MeasurementCreateView(APIView):
    """Zapis wyniku przesłanego kluczem API czujnika."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def handle_exception(self, exc):
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

    def post(self, request):
        sensor = sensor_from_api_key(request.headers.get('X-API-Key'))
        if sensor is None:
            return unauthorized(request)
        serializer = MeasurementInputSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_measurement_response(serializer, request)
        value = serializer.validated_data['value']
        timestamp = serializer.validated_data.get('timestamp')
        with transaction.atomic():
            locked_series = Series.objects.select_for_update().filter(pk=sensor.series_id).first()
            locked_sensor = (
                Sensor.objects.select_for_update()
                .filter(pk=sensor.pk, is_active=True)
                .first()
            )
            if locked_series is None or locked_sensor is None:
                return unauthorized(request)
            if value < locked_series.min_value or value > locked_series.max_value:
                return problem_response(
                    422,
                    'Nie można przetworzyć danych',
                    detail='Wartość jest poza dopuszczalnym przedziałem serii.',
                    instance=request.path,
                    errors=[
                        {
                            'field': 'value',
                            'message': 'Wartość musi mieścić się w przedziale serii.',
                        }
                    ],
                )
            if timestamp is None:
                timestamp = timezone.now()
            elif timestamp > timezone.now() + FUTURE_LIMIT:
                return problem_response(
                    422,
                    'Nie można przetworzyć danych',
                    detail='Znacznik czasu jest zbyt odległy w przyszłości.',
                    instance=request.path,
                    errors=[
                        {
                            'field': 'timestamp',
                            'message': 'Znacznik czasu nie może być późniejszy niż 5 minut od czasu serwera.',
                        }
                    ],
                )
            measurement = Measurement.objects.create(
                sensor=locked_sensor,
                value=value,
                timestamp=timestamp,
            )
        return Response(
            {
                'id': measurement.id,
                'seriesId': locked_series.id,
                'sensorId': locked_sensor.id,
                'value': measurement.value,
                'timestamp': timestamp,
            },
            status=201,
            headers={'Location': f'/api/measurements/{measurement.id}'},
        )
