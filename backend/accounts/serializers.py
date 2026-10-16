from rest_framework import serializers


class StrictCharField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault('trim_whitespace', False)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail('invalid')
        return super().to_internal_value(data)


class LoginSerializer(serializers.Serializer):
    username = StrictCharField()
    password = StrictCharField()


class PasswordChangeSerializer(serializers.Serializer):
    currentPassword = StrictCharField()
    newPassword = StrictCharField(min_length=8)
