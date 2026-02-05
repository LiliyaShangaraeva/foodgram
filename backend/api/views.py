import base64

from api.filters import NameSearchFilter
from api.pagination import BasePagination
from api.permissions import IsAuthorOrReadOnly
from api.serializers import (FavoriteSerializer, IngredientSerializer,
                             RecipeCreateSerializer, RecipeMinifiedSerializer,
                             RecipeSerializer, SetPasswordSerializer,
                             ShoppingCartSerializer, SubscriptionSerializer,
                             TagSerializer, UserCreateSerializer,
                             UserSerializer)
from django.db.models import BooleanField, Count, Exists, OuterRef, Sum, Value
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingCart, Tag)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (AllowAny, IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from users.models import Subscription, User


class UserViewSet(DjoserUserViewSet):
    """Получить список пользователей и профиль по id."""

    queryset = User.objects.all()
    pagination_class = BasePagination
    permission_classes = (IsAuthenticatedOrReadOnly,)

    def get_permissions(self):
        """Возвращает список разрешений в зависимости от действия (action)."""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        """Используем разные сериализаторы в зависимости от действия."""
        mapping = {
            'create': UserCreateSerializer,
            'me': UserSerializer,
            'set_password': SetPasswordSerializer,
            'subscriptions': SubscriptionSerializer,
        }
        return mapping.get(self.action, UserSerializer)

    def get_queryset(self):
        """Переопределяем queryset для подписок."""
        if self.action == 'list':
            return User.objects.all()
        if self.action == 'subscriptions':
            return User.objects.filter(
                subscribed_to__user=self.request.user
            ).annotate(
                recipes_count=Count('recipes')
            ).prefetch_related('recipes')
        return super().get_queryset()

    def get_serializer_context(self):
        """Добавляет request в контекст сериализатора."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        """Получить профиль текущего пользователя."""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAuthenticated]
    )
    def set_password(self, request):
        """Изменить пароль текущего пользователя."""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated]
    )
    def set_avatar(self, request):
        """Добавить или удалить аватар текущего пользователя."""
        user = request.user

        if request.method == 'DELETE':
            user.avatar.delete(save=True)
            return Response(status=status.HTTP_204_NO_CONTENT)
        if 'avatar' not in request.data:
            return Response(
                {'avatar': ['Обязательное поле.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            avatar_url = (
                request.build_absolute_uri(user.avatar.url)
                if user.avatar
                else None
            )
            return Response(
                {'avatar': avatar_url},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def _get_author_or_400(self, author_id):
        """Возвращает автора или выбрасывает ValidationError."""
        author = get_object_or_404(User, id=author_id)
        if self.request.user == author:
            raise ValidationError('Нельзя подписаться на себя.')
        return author

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
    )
    def subscriptions(self, request):
        """Возвращает авторов, на которых подписан текущий пользователь."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(
                page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(
            queryset, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, id=None):
        """Подписаться/отписаться от автора."""
        author = self._get_author_or_400(id)
        if request.method == 'POST':
            if Subscription.objects.filter(
                user=request.user,
                author=author
            ).exists():
                return Response(
                    {'errors': 'Вы уже подписаны на этого автора.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            Subscription.objects.create(user=request.user, author=author)
            serializer = SubscriptionSerializer(
                author, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            if not Subscription.objects.filter(
                user=request.user,
                author=author
            ).exists():
                raise ValidationError('Вы не подписаны на этого автора.')

            Subscription.objects.filter(
                user=request.user,
                author=author
            ).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(ReadOnlyModelViewSet):
    """Получить список тегов и тег по id."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class IngredientViewSet(ReadOnlyModelViewSet):
    """Предоставляет доступ только для чтения к списку ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_backends = (NameSearchFilter,)
    search_fields = ['^name']


class RecipeViewSet(ModelViewSet):
    """Список рецептов на главной странице."""

    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = (IsAuthorOrReadOnly, IsAuthenticatedOrReadOnly)
    pagination_class = BasePagination
    ordering_fields = ['created_at', 'name']

    def get_queryset(self):
        """
        Возвращает queryset рецептов.

        C аннотациями is_favorited и is_in_shopping_cart
        для авторизованного пользователя или False (если аноним).

        Применяет фильтрацию по:
        - Тегам (tags)
        - Автору (author)
        - Параметрам is_favorited=1/0 и is_in_shopping_cart=1/0

        Использует аннотации через Exists для оптимизации производительности.
        """
        user = self.request.user
        queryset = Recipe.objects.all().prefetch_related(
            'tags',
            'recipe_ingredients__ingredient',
            'author',
        )

        if user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=user,
                        recipe=OuterRef('pk')
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(
                        user=user,
                        recipe=OuterRef('pk')
                    )
                ),
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField()),
            )

        if user.is_authenticated:
            is_in_cart = self.request.query_params.get('is_in_shopping_cart')
            if is_in_cart == '1':
                queryset = queryset.filter(is_in_shopping_cart=True)
            elif is_in_cart == '0':
                queryset = queryset.exclude(is_in_shopping_cart=True)

            is_fav = self.request.query_params.get('is_favorited')
            if is_fav == '1':
                queryset = queryset.filter(is_favorited=True)
            elif is_fav == '0':
                queryset = queryset.exclude(is_favorited=True)

        tags = self.request.query_params.getlist('tags')
        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()

        author_id = self.request.query_params.get('author')
        if author_id:
            queryset = queryset.filter(author_id=author_id)

        return queryset

    def get_serializer_context(self):
        """Добавляет request в контекст сериализатора."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def get_serializer_class(self):
        """Возвращает сериализатор в зависимости от действия (action)."""
        mapping = {
            'create': RecipeCreateSerializer,
            'update': RecipeCreateSerializer,
            'partial_update': RecipeCreateSerializer,
            'favorite': RecipeMinifiedSerializer,
            'shopping_cart': RecipeMinifiedSerializer,
        }
        return mapping.get(self.action, RecipeSerializer)

    def get_permissions(self):
        """Возвращает список разрешений в зависимости от действия (action)."""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthorOrReadOnly()]
        return super().get_permissions()

    @action(detail=True, methods=['get'], url_path='get-link')
    def get_link(self, request, pk=None):
        """Возвращает короткую ссылку на рецепт без сохранения в БД."""
        recipe = get_object_or_404(Recipe, pk=pk)
        encoded_id = base64.urlsafe_b64encode(
            str(recipe.id).encode(),
        ).decode().rstrip('=')
        short_url = request.build_absolute_uri(f'/s/{encoded_id}/')
        return Response({'short-link': short_url}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAuthenticated],
    )
    def _get_item_or_error(self, model, user, recipe, error_message):
        """Возвращает объект для удаления или ошибку, если его нет."""
        item = model.objects.filter(user=user, recipe=recipe)
        if not item.exists():
            return Response(error_message, status=status.HTTP_400_BAD_REQUEST)
        return item

    def _add_recipe(
        self, request, recipe, model, serializer_class,
        existing_error_message,
    ):
        """Общий метод для добавления рецепта (в избранное или корзину)."""
        user = request.user

        if model.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                existing_error_message,
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = serializer_class(
            data={'user': user.id, 'recipe': recipe.id},
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            RecipeMinifiedSerializer(
                recipe, context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def _remove_recipe(self, model, recipe, user, non_existing_error_message):
        """Общий метод для удаления рецепта (из избранного или корзины)."""
        item = self._get_item_or_error(
            model, user, recipe, non_existing_error_message,
        )
        if isinstance(item, Response):
            return item
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        """Добавляет или удаляет рецепт из избранного."""
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            return self._add_recipe(
                request,
                recipe,
                Favorite,
                FavoriteSerializer,
                existing_error_message={
                    'errors': 'Рецепт уже добавлен в избранное.'
                },
            )

        elif request.method == 'DELETE':
            return self._remove_recipe(
                Favorite,
                recipe,
                request.user,
                non_existing_error_message={
                    'errors': 'Рецепта нет в избранном.'
                }
            )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        """Добавляет или удаляет рецепт из списка покупок."""
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            return self._add_recipe(
                request,
                recipe,
                ShoppingCart,
                ShoppingCartSerializer,
                existing_error_message={
                    'errors': 'Рецепт уже в списке покупок.'
                },
            )

        elif request.method == 'DELETE':
            return self._remove_recipe(
                ShoppingCart,
                recipe,
                request.user,
                non_existing_error_message={
                    'errors': 'Рецепта нет в списке покупок.'
                }
            )

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
        url_path='download_shopping_cart',
    )
    def download_shopping_cart(self, request):
        """Скачивает список покупок в формате .txt."""
        user = request.user

        if not user.shopping_cart.exists():
            return Response(
                {'error': 'Список покупок пуст.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingredients = (
            RecipeIngredient.objects
            .filter(recipe__in_shopping_cart__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )

        lines = [
            f"СПИСОК ПОКУПОК для {user.username}",
            "=" * 40,
        ]

        for item in ingredients:
            name = item['ingredient__name']
            unit = item['ingredient__measurement_unit']
            amount = item['total_amount']
            lines.append(f"• {name} ({unit}) — {amount}")

        content = "\n".join(lines)

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response


class ShortLinkView(APIView):
    """Декодирует короткую ссылкуи возвращает данные рецепта."""

    def get(self, request, encoded_id):
        """Обрабатывает GET-запрос к короткой ссылке.

        Декодирует encoded_id из URL-safe base64,
        преобразует результат в целое число (ID рецепта), затем:
          1. Ищет рецепт по ID,
          2. Сериализует его через RecipeSerializer,
          3. Возвращает JSON-ответ.
        """
        try:
            padded_id = encoded_id + '=' * (-len(encoded_id) % 4)
            decoded_id = base64.urlsafe_b64decode(padded_id.encode()).decode()
            recipe_id = int(decoded_id)
        except (ValueError, base64.binascii.Error):
            return Response(
                {'error': 'Некорректная короткая ссылка.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            recipe = Recipe.objects.get(pk=recipe_id)
        except Recipe.DoesNotExist:
            return Response(
                {'detail': 'Рецепт не найден.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        redirect_url = f"/recipes/{recipe.id}/"
        return HttpResponseRedirect(redirect_url)
