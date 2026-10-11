from django.db import models

from series.models import Series


class Sensor(models.Model):
    name = models.CharField('nazwa', max_length=100)
    series = models.ForeignKey(
        Series,
        on_delete=models.CASCADE,
        related_name='sensors',
        verbose_name='seria pomiarowa',
    )
    api_key_hash = models.CharField('hash klucza API', max_length=255, unique=True)
    is_active = models.BooleanField('klucz aktywny', default=True)
    created_at = models.DateTimeField('data utworzenia', auto_now_add=True)

    class Meta:
        db_table = 'sensors'
        verbose_name = 'czujnik'
        verbose_name_plural = 'czujniki'

    def __str__(self):
        return self.name
