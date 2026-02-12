from django.core.management.base import BaseCommand
from recipes.models import Tag


class Command(BaseCommand):
    help = 'Создание базовых тегов'

    TAGS = (
        ('Завтрак', 'breakfast'),
        ('Обед', 'lunch'),
        ('Ужин', 'dinner'),
    )

    def handle(self, *args, **options):
        created = 0

        for name, slug in self.TAGS:
            _, is_created = Tag.objects.get_or_create(
                name=name,
                slug=slug,
            )
            if is_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Теги загружены. Создано: {created}'
            )
        )
