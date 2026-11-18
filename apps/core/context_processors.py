from django.conf import settings


def site(request):
    """Values every template needs. SITE_NAME is defined once in config/settings/base.py."""
    return {"SITE_NAME": settings.SITE_NAME}
