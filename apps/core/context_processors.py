from django.conf import settings

# StudentProfile field → class on <body> (styles in static/css/a11y.css).
A11Y_CLASSES = {
    "high_contrast": "a11y-contrast",
    "large_text": "a11y-large-text",
    "reduced_motion": "a11y-reduced-motion",
    "keyboard_mode": "a11y-keyboard",
}


def site(request):
    """Values every template needs.

    SITE_NAME is defined once in config/settings/base.py. For a logged-in student, the
    accessibility profile becomes body classes (`a11y_classes`) and `a11y` (the profile itself,
    for captions / reduced-motion checks in templates).
    """
    context = {"SITE_NAME": settings.SITE_NAME, "a11y_classes": "", "a11y": None}
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and getattr(user, "is_student", False):
        profile = getattr(user, "student_profile", None)
        if profile is not None:
            context["a11y"] = profile
            context["a11y_classes"] = " ".join(
                css for field, css in A11Y_CLASSES.items() if getattr(profile, field)
            )
    return context
