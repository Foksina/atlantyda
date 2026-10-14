from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import Series

HEX_COLOR = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Kolor musi mieć format #RRGGBB.',
    code='invalid_format',
)


class StrictCharField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class StrictFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool) or not isinstance(data, (int, float)):
            self.fail('invalid')
        return super().to_internal_value(data)


class SeriesSerializer(serializers.ModelSerializer):
    name = StrictCharField(min_length=1, max_length=100)
    minValue = StrictFloatField(source='min_value')
    maxValue = StrictFloatField(source='max_value')
    color = StrictCharField(min_length=7, max_length=7, validators=[HEX_COLOR])
    icon = StrictCharField(required=False, allow_null=True, allow_blank=True, max_length=100)
    unit = StrictCharField(required=False, allow_null=True, allow_blank=True, max_length=20)

    class Meta:
        model = Series
        fields = ['id', 'name', 'minValue', 'maxValue', 'color', 'icon', 'unit']
        read_only_fields = ['id']

    def validate(self, attrs):
        min_value = attrs.get('min_value')
        max_value = attrs.get('max_value')
        if min_value is not None and max_value is not None and min_value >= max_value:
            raise serializers.ValidationError(
                {
                    'minValue': [
                        serializers.ErrorDetail(
                            'Wartość minimalna musi być mniejsza od maksymalnej.',
                            code='range',
                        )
                    ]
                }
            )
        return attrs

    def update(self, instance, validated_data):
        validated_data.setdefault('icon', None)
        validated_data.setdefault('unit', None)
        return super().update(instance, validated_data)
