from django.db import transaction
from djoser.serializers import UserSerializer as DjoserUserSerializer
from drf_extra_fields.fields import Base64ImageField
from rest_framework import serializers

from recipes.constants import (MAX_COOKING_TIME, MAX_INGREDIENT_AMOUNT,
                               MIN_COOKING_TIME, MIN_INGREDIENT_AMOUNT)
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from users.models import User


class UserSerializer(DjoserUserSerializer):
    """Базовый сериализатор для пользователя."""

    avatar = Base64ImageField(required=False)
    is_subscribed = serializers.SerializerMethodField()

    class Meta(DjoserUserSerializer.Meta):
        fields = DjoserUserSerializer.Meta.fields + ('avatar', 'is_subscribed')

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на этого."""
        request = self.context.get('request')
        return (
            request
            and request.user.is_authenticated
            and obj.subscribed_to.filter(user=request.user).exists()
        )


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    """Сериализатор для сокращённого представления рецепта."""

    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')

    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image:
            return request.build_absolute_uri(obj.image.url)
        return ''


class SubscriptionSerializer(UserSerializer):
    """Сериализатор для вывода подписок."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        model = User
        fields = (*UserSerializer.Meta.fields, 'recipes', 'recipes_count')

    def get_recipes(self, obj):
        """Выводим сокращённый список рецептов автора."""
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit', None)
        queryset = obj.recipes.all()
        if recipes_limit is not None:
            try:
                limit = int(recipes_limit)
                if limit < 0:
                    raise serializers.ValidationError(
                        "recipes_limit должно быть неотрицательным числом."
                    )
                queryset = queryset[:limit]
            except (ValueError, TypeError):
                raise serializers.ValidationError(
                    {"recipes_limit": "Значение должно быть целым числом."}
                )
        return RecipeMinifiedSerializer(
            queryset, many=True,
            context={'request': request},
        ).data

    def get_recipes_count(self, obj):
        """Число рецептов автора."""
        return obj.recipes.count()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор для тегов."""

    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')
        read_only_fields = fields


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""

    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    """Связь ингредиента и его количества в рецепте (для вложенного списка)."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit',
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class IngredientWriteSerializer(serializers.ModelSerializer):
    """
    Сериализатор для добавления/обновления ингредиентов в рецепт.

    Принимает id ингредиента и количество (мин. значение: 1).
    """

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(
        min_value=MIN_INGREDIENT_AMOUNT,
        max_value=MAX_INGREDIENT_AMOUNT,
        error_messages={
            'min_value': (
                f'Количество должно быть не менее {MIN_INGREDIENT_AMOUNT}.'
            ),
            'max_value': (
                f'Количество должно быть не более {MAX_INGREDIENT_AMOUNT}.'
            )
        }
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов."""

    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        many=True,
        read_only=True,
        source='recipe_ingredients',
    )
    image = Base64ImageField(read_only=True)
    is_favorited = serializers.BooleanField(default=False)
    is_in_shopping_cart = serializers.BooleanField(default=False)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text',
            'cooking_time',
        )

    def get_is_favorited(self, obj):
        """Возвращает True/False аннотированного поля is_favorited."""
        return obj.is_favorited

    def get_is_in_shopping_cart(self, obj):
        """Возвращает True/False аннотированного поля."""
        return obj.is_in_shopping_cart


class RecipeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и обновления рецепта."""

    ingredients = IngredientWriteSerializer(many=True, required=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
        required=True
    )
    image = Base64ImageField(required=True)
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME,
        max_value=MAX_COOKING_TIME,
        error_messages={
            'min_value': (
                'Время приготовления должно быть '
                f'не менее {MIN_COOKING_TIME} мин.'
            ),
            'max_value': (
                'Время приготовления должно быть '
                f'не более {MAX_COOKING_TIME} мин.'
            )
        },
        required=True)

    class Meta:
        model = Recipe
        fields = (
            'name', 'image', 'text', 'cooking_time',
            'tags', 'ingredients'
        )

    def validate(self, data):
        """Валидирует входные данные при создании/обновлении рецепта."""
        ingredients = data.get('ingredients')
        tags = data.get('tags')
        if not ingredients:
            raise serializers.ValidationError({
                'ingredients': (
                    'Рецепт должен содержать хотя бы один ингредиент.'
                )
            })

        ingredient_ids = [item['id'] for item in ingredients]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError({
                'ingredients': 'Ингредиенты не должны повторяться.',
            })

        if not tags:
            raise serializers.ValidationError({'tags': ['Обязательное поле.']})

        if len(tags) != len(set(tags)):
            raise serializers.ValidationError(
                {'tags': 'Теги не должны повторяться.'},
            )

        return data

    def validate_image(self, value):
        """Валидация картинки на пустоту."""
        if not value:
            raise serializers.ValidationError(
                "Обязательное поле."
            )
        return value

    def _create_recipe_ingredients(self, recipe, ingredients_data):
        """Создаём связь ингредиентов и рецепта одной операцией."""
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=item['id'],
                amount=item['amount'],
            )
            for item in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)

    @transaction.atomic
    def create(self, validated_data):
        """Создание рецепта с ингредиентами и тегами."""
        ingredients_data = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        user = self.context['request'].user

        recipe = super().create({**validated_data, 'author': user})
        recipe.tags.set(tags)
        self._create_recipe_ingredients(recipe, ingredients_data)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        """Обновление рецепта с заменой ингредиентов и тегов."""
        ingredients_data = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')

        recipe = super().update(instance, validated_data)

        recipe.tags.set(tags)

        recipe.recipe_ingredients.all().delete()
        self._create_recipe_ingredients(recipe, ingredients_data)

        return recipe

    def to_representation(self, instance):
        """После создания/обновления возвращаем детализированный рецепт."""
        return RecipeSerializer(instance, context=self.context).data


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/удаления записи «избранное»."""

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для добавления/удаления рецепта из списка покупок."""

    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')
