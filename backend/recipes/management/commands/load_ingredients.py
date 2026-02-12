import json

from django.core.management.base import BaseCommand
from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузка ингредиентов из data/ingredients.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            default='data/ingredients.json',
            help='Путь к файлу с ингредиентами'
        )

    def handle(self, *args, **options):
        path = options['path']

        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except FileNotFoundError:
            self.stderr.write(
                self.style.ERROR(f'Файл не найден: {path}')
            )
            return

        created = 0

        for item in data:
            _, is_created = Ingredient.objects.get_or_create(
                name=item['name'],
                measurement_unit=item['measurement_unit'],
            )
            if is_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Ингредиенты загружены. Создано: {created}'
            )
        )
