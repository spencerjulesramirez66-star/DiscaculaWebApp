from django.shortcuts import redirect
from django.views.generic import TemplateView


def root(request):
    """Bare address (http://127.0.0.1:8000/) → /home/, so the address bar names the page."""
    return redirect("core:home")


class HomeView(TemplateView):
    """/home/: the welcome page with 'I'm a student' / 'I'm a teacher'."""

    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:after_login")
        return super().get(request, *args, **kwargs)
