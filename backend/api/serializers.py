import base64

from api.constants import MIN_COOKING_TIME, MIN_INGREDIENT_AMOUNT
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from rest_framework import serializers
from users.models import User


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для загрузки изображения из Base64."""

    def to_internal_value(self, data):
        """Декодирует Base64 и возвращает файл."""
        if isinstance(data, str) and data.startswith('data:image'):

            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'avatar.{ext}')

        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Базовый сериализатор для пользователя."""

    avatar = Base64ImageField(required=False)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'avatar')

    def get_avatar(self, obj):
        """Возвращает ссылку на аватар."""
        request = self.context.get('request')
        return (
            request.build_absolute_uri(obj.avatar.url)
            if obj.avatar and hasattr(obj.avatar, 'url')
            else None
        )

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на этого."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user.subscriber.filter(author=obj).exists()
        return False


class UserCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации пользователя."""

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password'
        )
        read_only_fields = ('id',)
        extra_kwargs = {
            'password': {'write_only': True},
            'username': {
                'validators': [UnicodeUsernameValidator()],
                'required': True
            },
        }

    def create(self, validated_data):
        try:
            user = User.objects.create_user(**validated_data)
            return user
        except IntegrityError:
            raise serializers.ValidationError({
                'username': ['Пользователь с таким username уже существует.']
            })


class SetPasswordSerializer(serializers.Serializer):
    """Сериализатор для изменения пароля."""

    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)

    def validate_current_password(self, value):
        """Проверяет, что текущий пароль верный."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный текущий пароль.")
        return value

    def validate_new_password(self, value):
        """Проверяет новый пароль по стандартным правилам Django."""
        validate_password(value)
        return value

    def save(self):
        """Меняет пароль пользователя."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    """Сериализатор для сокращённого представления рецепта."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


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
        if recipes_limit:
            try:
                recipes_limit = int(recipes_limit)
            except ValueError:
                recipes_limit = None

        recipes = (
            obj.recipes.all()[:recipes_limit]
            if recipes_limit
            else obj.recipes.all()
        )
        return RecipeMinifiedSerializer(
            recipes, many=True,
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
    amount = serializers.IntegerField(min_value=MIN_INGREDIENT_AMOUNT)

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
        """Возвращает True/False аннотированного поля is_in_shopping_cart."""
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
    name = serializers.CharField(required=True)
    text = serializers.CharField(required=True)
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME,
        error_messages={
            'min_value': (
                'Время приготовления должно быть '
                f'не менее {MIN_COOKING_TIME} мин.'
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
        name = data.get('name')
        if name and len(name) > 256:
            raise serializers.ValidationError({
                'name': 'Название не должно превышать 256 символов.'
            })
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

        tag_ids = [tag.id for tag in tags]
        if len(tag_ids) != len(set(tag_ids)):
            raise serializers.ValidationError(
                {'tags': 'Теги не должны повторяться.'},
            )

        return data

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
        ingredients_data = validated_data.pop('ingredients', None)
        tags = validated_data.pop('tags', None)

        recipe = super().update(instance, validated_data)

        if tags is not None:
            recipe.tags.set(tags)

        if ingredients_data is not None:
            recipe.recipe_ingredients.all().delete()
            self._create_recipe_ingredients(recipe, ingredients_data)

        return recipe

    def to_representation(self, instance):
        """После создания/обновления возвращаем детализированный рецепт."""
        return RecipeSerializer(instance, context=self.context).data


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/удаления записи «избранное»."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = Favorite
        fields = ('user', 'recipe')


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для добавления/удаления рецепта из списка покупок."""

    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    recipe = serializers.PrimaryKeyRelatedField(queryset=Recipe.objects.all())

    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')
