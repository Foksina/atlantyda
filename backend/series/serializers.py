from rest_framework import serializers

from .models import Series


class SeriesSerializer(serializers.ModelSerializer):
    minValue = serializers.FloatField(source='min_value')
    maxValue = serializers.FloatField(source='max_value')

    class Meta:
        model = Series
        fields = ['id', 'name', 'minValue', 'maxValue', 'color', 'icon', 'unit']
        read_only_fields = ['id']
