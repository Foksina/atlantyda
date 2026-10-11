from django.db import models

from sensors.models import Sensor


class Measurement(models.Model):
    sensor = models.ForeignKey(
        Sensor,
        on_delete=models.CASCADE,
        related_name='measurements',
        verbose_name='czujnik',
    )
    value = models.FloatField('wartość')
    timestamp = models.DateTimeField('znacznik czasu')

    class Meta:
        db_table = 'measurements'
        verbose_name = 'pomiar'
        verbose_name_plural = 'pomiary'
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['sensor', 'timestamp']),
        ]

    def __str__(self):
        return f'{self.sensor}: {self.value}'
