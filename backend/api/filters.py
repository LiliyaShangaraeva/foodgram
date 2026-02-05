from django_filters import rest_framework as filters
from django_filters.widgets import BooleanWidget
from recipes.models import Recipe
from rest_framework.filters import SearchFilter


class TransformativeBooleanFilter(filters.BooleanFilter):
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = BooleanWidget
        super().__init__(*args, **kwargs)

    def filter(self, queryset, value):
        if value is None:
            return queryset
        if isinstance(value, str):
            value = value.lower() in ('true', '1')

        if value:
            return self.method(queryset, self.field_name, True)
        return self.method(queryset, self.field_name, False)


class RecipeFilter(filters.FilterSet):
    """Фильтр для рецептов."""

    is_favorited = TransformativeBooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = TransformativeBooleanFilter(
        method='filter_is_in_shopping_cart')
    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')

    class Meta:
        model = Recipe
        fields = ['is_favorited', 'is_in_shopping_cart', 'author', 'tags']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def _boolean_filter(self, queryset, name, value, filter_field):
        user = self.request.user if self.request else None
        if not user or not user.is_authenticated:
            return queryset.none()

        filter_kwargs = {filter_field: user}

        if value:
            return queryset.filter(**filter_kwargs)
        return queryset.exclude(**filter_kwargs)

    def filter_is_favorited(self, queryset, name, value):
        return self._boolean_filter(
            queryset, name, value,
            filter_field='favorited_by__user',
        )

    def filter_is_in_shopping_cart(self, queryset, name, value):
        return self._boolean_filter(
            queryset, name, value,
            filter_field='in_shopping_cart__user',
        )


class NameSearchFilter(SearchFilter):
    search_param = 'name'
