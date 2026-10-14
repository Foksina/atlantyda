from django.db import DataError, IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse
from rest_framework.exceptions import NotAuthenticated, ParseError, UnsupportedMediaType
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import BearerAuthentication
from measurements.models import Measurement
from sensors.models import Sensor

from .models import Series
from .serializers import SeriesSerializer

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


def invalid_series_response(serializer, request):
    status_code = validation_status(serializer.errors)
    title = 'Niepoprawne żądanie' if status_code == 400 else 'Nie można przetworzyć danych'
    return problem_response(
        status_code,
        title,
        detail='Dane serii pomiarowej są niepoprawne.',
        instance=request.path,
        errors=field_errors(serializer.errors),
    )


def measurements_conflict(series, min_value, max_value):
    return Measurement.objects.filter(sensor__series=series).filter(
        Q(value__lt=min_value) | Q(value__gt=max_value)
    ).exists()


def find_series(series_id):
    try:
        pk = int(series_id)
    except (TypeError, ValueError):
        return None
    if pk < 1:
        return None
    try:
        return Series.objects.filter(pk=pk).first()
    except (DataError, OverflowError):
        return None


class AdministratorWriteMixin:
    authentication_classes = [BearerAuthentication]

    def get_permissions(self):
        if self.request.method in ('POST', 'PUT', 'DELETE'):
            return [IsAuthenticated()]
        return [AllowAny()]

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


class SeriesListView(AdministratorWriteMixin, APIView):
    """Lista serii pomiarowych oraz tworzenie serii przez administratora."""

    def get(self, request):
        series = Series.objects.order_by('id')
        return Response(SeriesSerializer(series, many=True).data)

    def post(self, request):
        serializer = SeriesSerializer(data=request.data)
        if not serializer.is_valid():
            return invalid_series_response(serializer, request)
        try:
            series = serializer.save()
        except IntegrityError:
            return problem_response(
                422,
                'Nie można przetworzyć danych',
                detail='Wartość minimalna musi być mniejsza od maksymalnej.',
                instance=request.path,
            )
        return Response(
            SeriesSerializer(series).data,
            status=201,
            headers={'Location': reverse('series-detail', kwargs={'series_id': series.id})},
        )


class SeriesDetailView(AdministratorWriteMixin, APIView):
    """Odczyt i aktualizacja jednej serii pomiarowej."""

    def get(self, request, series_id):
        series = find_series(series_id)
        if series is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Seria pomiarowa nie istnieje.',
                instance=request.path,
            )
        return Response(SeriesSerializer(series).data)

    def put(self, request, series_id):
        series = find_series(series_id)
        if series is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Seria pomiarowa nie istnieje.',
                instance=request.path,
            )
        serializer = SeriesSerializer(series, data=request.data)
        if not serializer.is_valid():
            return invalid_series_response(serializer, request)
        min_value = serializer.validated_data['min_value']
        max_value = serializer.validated_data['max_value']
        try:
            with transaction.atomic():
                locked = Series.objects.select_for_update().get(pk=series.pk)
                list(
                    Sensor.objects.select_for_update()
                    .filter(series=locked)
                    .order_by('pk')
                )
                if measurements_conflict(locked, min_value, max_value):
                    return problem_response(
                        409,
                        'Konflikt',
                        detail='Nowy zakres nie obejmuje istniejących pomiarów.',
                        instance=request.path,
                    )
                serializer.instance = locked
                updated = serializer.save()
        except IntegrityError:
            return problem_response(
                422,
                'Nie można przetworzyć danych',
                detail='Wartość minimalna musi być mniejsza od maksymalnej.',
                instance=request.path,
            )
        return Response(SeriesSerializer(updated).data)

    def delete(self, request, series_id):
        series = find_series(series_id)
        if series is None:
            return problem_response(
                404,
                'Nie znaleziono',
                detail='Seria pomiarowa nie istnieje.',
                instance=request.path,
            )
        with transaction.atomic():
            locked = Series.objects.select_for_update().filter(pk=series.pk).first()
            if locked is None:
                return problem_response(
                    404,
                    'Nie znaleziono',
                    detail='Seria pomiarowa nie istnieje.',
                    instance=request.path,
                )
            locked.delete()
        return Response(status=204)
