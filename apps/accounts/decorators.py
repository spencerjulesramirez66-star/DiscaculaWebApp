"""Role guards for views. Use these instead of ad-hoc role checks."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def teacher_required(view=None, *, verified=True):
    """Logged-in teacher; unverified teachers are sent to verify their email first."""

    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.is_teacher:
                raise PermissionDenied
            if verified and not request.user.email_verified:
                return redirect("accounts:verify_email")
            return fn(request, *args, **kwargs)

        return wrapper

    return decorator(view) if view else decorator


def student_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            raise PermissionDenied
        return fn(request, *args, **kwargs)

    return wrapper
