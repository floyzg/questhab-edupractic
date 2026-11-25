"""Корневые маршруты проекта QuestHub."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('booking.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = 'booking.views.custom_403_view'
handler404 = 'booking.views.custom_404_view'
handler500 = 'booking.views.custom_500_view'
