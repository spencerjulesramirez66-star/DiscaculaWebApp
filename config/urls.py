from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("admin/", admin.site.urls),  # dev convenience only; product admin panel is Docs-only
    path("accounts/", include("apps.accounts.urls")),
    path("teach/", include("apps.classrooms.urls_teacher")),
    path("teach/library/", include("apps.games.urls_library")),
    path("teach/videos/", include("apps.content.urls")),
    path("play/", include("apps.classrooms.urls_student")),
    path("play/", include("apps.games.urls")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [path("__debug__/", include("debug_toolbar.urls"))]
elif getattr(settings, "SERVE_MEDIA", False):
    # Hosted demo (prod settings): let Django serve teacher uploads. See config/settings/prod.py.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
