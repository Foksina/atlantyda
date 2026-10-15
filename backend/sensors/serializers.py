from rest_framework import serializers


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
