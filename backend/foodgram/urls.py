from django.contrib import admin
from django.urls import include, path

from api.views import ShortLinkView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('s/<str:encoded_id>/', ShortLinkView.as_view(), name='short-link'),
]
