from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.text import Truncator

from recipes.constants import RECIPE_NAME_MAX_LENGTH
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Админка для модели ингредиентов."""

    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Админка для модели тегов."""

    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


class RecipeIngredientInline(admin.TabularInline):
    """Вложенная форма для добавления ингредиентов к рецепту (минимум 1)."""

    model = RecipeIngredient
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Админка для модели рецептов."""

    list_display = (
        'id',
        'short_name',
        'author',
        'cooking_time',
        'recipe_tags',
    )
    inlines = [RecipeIngredientInline]
    list_filter = ('tags', 'author')
    search_fields = ('name', 'author__username')
    readonly_fields = ('favorites_count',)
    fields = (
        'name',
        'text',
        'cooking_time',
        'tags',
        'author',
        'image',
        'favorites_count',
    )

    def get_queryset(self, request):
        """Добавляет к каждому рецепту поле favorites_count."""
        return super().get_queryset(request).annotate(
            favorites_count=Count('favorited_by_users')
        ).prefetch_related('tags')

    @admin.display(description='В избранном')
    def favorites_count(self, obj):
        """Возвращает количество добавлений рецепта в избранное."""
        return getattr(obj, 'favorites_count', 0)

    @admin.display(description='Теги')
    def recipe_tags(self, obj):
        """Возвращает список имён тегов рецепта через запятую."""
        return ", ".join(tag.name for tag in obj.tags.all())

    @admin.display(description='Название', ordering='name')
    def short_name(self, obj):
        """Возвращает обрезанное название рецепта."""
        truncated = Truncator(obj.name).chars(RECIPE_NAME_MAX_LENGTH)
        if len(obj.name) > RECIPE_NAME_MAX_LENGTH:
            return format_html(
                '<span title="{}">{}</span>',
                obj.name,
                truncated + '…'
            )
        return truncated


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    """Админка для связывающей модели рецпты-ингредиенты."""

    list_display = ('recipe', 'ingredient', 'amount')
    list_filter = ('recipe',)
    search_fields = ('ingredient__name', 'recipe__name')


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Админка для модели избранного."""

    list_display = ('user', 'recipe')
    list_filter = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Админка для модели корзина покупок."""

    list_display = ('user', 'recipe')
    list_filter = ('user', 'recipe')
    search_fields = ('user__username', 'recipe__name')
