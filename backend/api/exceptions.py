from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """
    Обработчик исключений для DRF.

    Переопределяет стандартный ответ на NotFound (404), чтобы возвращать
    единообразное сообщение "Страница не найдена".
    """
    response = drf_exception_handler(exc, context)

    if isinstance(exc, NotFound):
        response.data = {
            "detail": "Страница не найдена."
        }
        response.status_code = status.HTTP_404_NOT_FOUND

    return response
