from django.db import DataError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Series
from .serializers import SeriesSerializer


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


class SeriesListView(APIView):
    """Publiczna lista serii pomiarowych."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        series = Series.objects.order_by('id')
        return Response(SeriesSerializer(series, many=True).data)


class SeriesDetailView(APIView):
    """Publiczny odczyt jednej serii pomiarowej."""

    permission_classes = [AllowAny]
    authentication_classes = []

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
