from django.db import DataError
from rest_framework import serializers

from series.models import Series


class StrictCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class SeriesIdField(serializers.Field):
    default_error_messages = {
        'invalid': 'Identyfikator serii ma nieprawidłowy typ.',
        'does_not_exist': 'Wskazana seria pomiarowa nie istnieje.',
    }

    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, str)):
            self.fail('invalid')
        if isinstance(data, str):
            if not data.isdigit():
                self.fail('does_not_exist')
            data = int(data)
        if data < 1:
            self.fail('does_not_exist')
        try:
            series = Series.objects.filter(pk=data).first()
        except (DataError, OverflowError):
            series = None
        if series is None:
            self.fail('does_not_exist')
        return series


class SensorSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    seriesId = serializers.IntegerField(source='series_id', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    lastMeasurementAt = serializers.DateTimeField(
        source='last_measurement_at',
        allow_null=True,
        read_only=True,
    )


class SensorCreateSerializer(serializers.Serializer):
    name = StrictCharField(min_length=1, max_length=100)
    seriesId = SeriesIdField()
