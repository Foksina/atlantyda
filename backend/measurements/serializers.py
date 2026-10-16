from rest_framework import serializers


class StrictFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


class MeasurementInputSerializer(serializers.Serializer):
    value = StrictFloatField()
    timestamp = serializers.DateTimeField(required=False)
