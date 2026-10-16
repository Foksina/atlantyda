from datetime import timedelta

from django.db import DataError, transaction
from django.utils import timezone
from rest_framework import serializers
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
DEFAULT_LIMIT = 1000
MAX_LIMIT = 10000
MAX_SERIES_ID = 2**63 - 1


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


def measurement_data(measurement):
    return {
        'id': measurement.id,
        'seriesId': measurement.sensor.series_id,
        'sensorId': measurement.sensor_id,
        'value': measurement.value,
        'timestamp': measurement.timestamp,
    }


def measurement_queryset():
    return Measurement.objects.select_related('sensor')


def parse_series_ids(raw):
    if raw is None:
        return None
    parts = [part.strip() for part in raw.split(',')]
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError
    parsed = []
    for part in parts:
        value = int(part)
        if value < 1 or value > MAX_SERIES_ID:
            raise ValueError
        parsed.append(value)
    return parsed


def parse_instant(raw):
    if raw is None:
        return None
    try:
        return serializers.DateTimeField().to_internal_value(raw)
    except serializers.ValidationError as exc:
        raise ValueError from exc


def parse_limit(raw):
    if raw is None:
        return DEFAULT_LIMIT
    if not raw.isdigit():
        raise ValueError
    value = int(raw)
    if value < 1 or value > MAX_LIMIT:
        raise ValueError
    return value


def parse_sort(raw):
    if raw is None or raw == 'timestamp':
        return ('timestamp', 'id')
    if raw == '-timestamp':
        return ('-timestamp', '-id')
    raise ValueError


def filtered_measurements(params):
    errors = []
    try:
        series_ids = parse_series_ids(params.get('series'))
    except ValueError:
        errors.append({'field': 'series', 'message': 'Identyfikatory serii są niepoprawne.'})
        series_ids = None
    try:
        start = parse_instant(params.get('from'))
    except ValueError:
        errors.append({'field': 'from', 'message': 'Parametr from musi być datą i godziną.'})
        start = None
    try:
        end = parse_instant(params.get('to'))
    except ValueError:
        errors.append({'field': 'to', 'message': 'Parametr to musi być datą i godziną.'})
        end = None
    try:
        ordering = parse_sort(params.get('sort'))
    except ValueError:
        errors.append({'field': 'sort', 'message': 'Dozwolone wartości to timestamp i -timestamp.'})
        ordering = None
    try:
        limit = parse_limit(params.get('limit'))
    except ValueError:
        errors.append({'field': 'limit', 'message': 'Limit musi być liczbą całkowitą od 1 do 10000.'})
        limit = None
    if errors:
        return errors, None
    queryset = measurement_queryset()
    if series_ids is not None:
        queryset = queryset.filter(sensor__series_id__in=series_ids)
    if start is not None:
        queryset = queryset.filter(timestamp__gte=start)
    if end is not None:
        queryset = queryset.filter(timestamp__lte=end)
    return None, queryset.order_by(*ordering)[:limit]


def find_measurement(measurement_id):
    try:
        pk = int(measurement_id)
    except (TypeError, ValueError):
        return None
    if pk < 1 or pk > MAX_SERIES_ID:
        return None
    try:
        return measurement_queryset().filter(pk=pk).first()
    except (DataError, OverflowError):
        return None


class MeasurementListView(APIView):
    """Odczyt wyników oraz zapis wyniku przesłanego kluczem API czujnika."""

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

    def get(self, request):
        errors, queryset = filtered_measurements(request.query_params)
        if errors:
            return problem_response(
                400,
                'Niepoprawne żądanie',
                detail='Parametry zapytania są niepoprawne.',
                instance=request.path,
                errors=errors,
            )
        return Response([measurement_data(item) for item in queryset])

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
            measurement.sensor = locked_sensor
        return Response(
            measurement_data(measurement),
            status=201,
            headers={'Location': f'/api/measurements/{measurement.id}'},
        )


class MeasurementDetailView(APIView):
    """Odczyt jednego wyniku."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, measurement_id):
        measurement = find_measurement(measurement_id)
        if measurement is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Pomiar nie istnieje.',
                instance=request.path,
            )
        return Response(measurement_data(measurement))
