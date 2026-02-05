from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Кастомный обработчик исключений для DRF.

    Переопределяет стандартный ответ на NotFound (404), чтобы возвращать
    единообразное сообщение "Страница не найдена".
    """
    response = exception_handler(exc, context)

    if isinstance(exc, NotFound):
        response.data = {
            "detail": "Страница не найдена."
        }
        response.status_code = 404

    return response
