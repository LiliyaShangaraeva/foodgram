from django.contrib.auth.models import AbstractUser
from django.db import models
from users.constants import (EMAIL_MAX_LENGTH, FIRST_NAME_MAX_LENGTH,
                             LAST_NAME_MAX_LENGTH, USERNAME_MAX_LENGTH)


class User(AbstractUser):
    """Кастомная модель пользователя."""

    email = models.EmailField(
        verbose_name='Адрес электронной почты',
        max_length=EMAIL_MAX_LENGTH,
        unique=True,
        blank=False
    )
    first_name = models.CharField(
        verbose_name='Имя',
        max_length=FIRST_NAME_MAX_LENGTH,
        blank=False
    )
    last_name = models.CharField(
        verbose_name='Фамилия',
        max_length=LAST_NAME_MAX_LENGTH,
        blank=False
    )
    username = models.CharField(
        verbose_name='Имя пользователя',
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        blank=False
    )
    avatar = models.ImageField(
        upload_to='users/',
        blank=True,
        null=True,
        verbose_name='Аватар'
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username


class Subscription(models.Model):
    """Модель подписки: пользователь подписан на автора."""

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='subscriber',
        verbose_name='Подписчик'
    )
    author = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='subscribed_to',
        verbose_name='Автор'
    )

    class Meta:
        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'author'],
                name='unique_subscription'
            )
        ]

    def __str__(self):
        return f'{self.user.username} подписан на {self.author.username}'
