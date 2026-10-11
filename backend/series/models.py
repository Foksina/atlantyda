from django.core.validators import RegexValidator
from django.db import models

HEX_COLOR = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Kolor musi mieć format #RRGGBB.',
)


class Series(models.Model):
    name = models.CharField('nazwa', max_length=100)
    unit = models.CharField('jednostka', max_length=20, blank=True, null=True)
    min_value = models.FloatField('wartość minimalna')
    max_value = models.FloatField('wartość maksymalna')
    color = models.CharField('kolor', max_length=7, validators=[HEX_COLOR])
    icon = models.CharField('ikona', max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'series'
        verbose_name = 'seria pomiarowa'
        verbose_name_plural = 'serie pomiarowe'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_value__lt=models.F('max_value')),
                name='series_min_value_lt_max_value',
            ),
        ]

    def __str__(self):
        return self.name
