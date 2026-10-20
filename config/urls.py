from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SITE_NAME} Control Room"
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = "Markets, products, orders & chats"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("hub/", include("hub.urls")),
    path("accounts/", include("accounts.urls")),
    path("", include("support.urls")),
    path("", include("sourcing.urls")),
    path("", include("travel.urls")),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
