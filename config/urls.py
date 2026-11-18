from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),  # dev convenience only; product admin panel is Docs-only
    path("accounts/", include("apps.accounts.urls")),
    path("teach/", include("apps.classrooms.urls_teacher")),
    path("play/", include("apps.classrooms.urls_student")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
