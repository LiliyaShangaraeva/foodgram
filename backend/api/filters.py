from django_filters import rest_framework as filters
from django_filters.widgets import BooleanWidget
from recipes.models import Recipe
from rest_framework.filters import SearchFilter


class RecipeFilter(filters.FilterSet):
    """Фильтр для рецептов."""

    is_favorited = filters.BooleanFilter(
        method='filter_is_favorited',
        widget=BooleanWidget,
    )
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
        widget=BooleanWidget,
    )
    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')

    class Meta:
        model = Recipe
        fields = ['is_favorited', 'is_in_shopping_cart', 'author', 'tags']

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def _boolean_filter(self, queryset, name, value, filter_field):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return queryset

        filter_kwargs = {filter_field: user}

        if value:
            return queryset.filter(**filter_kwargs)
        return queryset.exclude(**filter_kwargs)

    def filter_is_favorited(self, queryset, name, value):
        return self._boolean_filter(
            queryset, name, value,
            filter_field='favorited_by_users__user',
        )

    def filter_is_shopping_cart_users(self, queryset, name, value):
        return self._boolean_filter(
            queryset, name, value,
            filter_field='shopping_cart_users__user',
        )


class NameSearchFilter(SearchFilter):
    search_param = 'name'
