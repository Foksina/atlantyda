from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response
    return Response(
        {
            'type': 'about:blank',
            'title': 'Błąd serwera',
            'status': 500,
        },
        status=500,
        content_type='application/problem+json',
    )
