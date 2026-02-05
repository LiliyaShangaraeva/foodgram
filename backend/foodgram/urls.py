from api.views import ShortLinkView
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('s/<str:encoded_id>/', ShortLinkView.as_view(), name='short-link'),
]
