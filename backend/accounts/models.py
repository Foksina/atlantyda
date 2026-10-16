from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Meta:
        verbose_name = 'administrator'
        verbose_name_plural = 'administratorzy'


class RevokedAccessToken(models.Model):
    token_hash = models.CharField('skrót tokenu', max_length=64, unique=True)
    expires_at = models.DateTimeField('wygasa')

    class Meta:
        db_table = 'revoked_access_tokens'
        verbose_name = 'unieważniony token'
        verbose_name_plural = 'unieważnione tokeny'
