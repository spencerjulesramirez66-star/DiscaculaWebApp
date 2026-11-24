from django import template

from apps.accounts.avatars import render_parts

register = template.Library()


@register.inclusion_tag("components/avatar.html")
def avatar(user, size="md"):
    """{% avatar user "sm" %} — a student's layered avatar (sizes: sm, md, lg)."""
    profile = getattr(user, "student_profile", None)
    data = profile.avatar if profile else None
    return {"parts": render_parts(data) if data else None, "size": size, "user": user}
