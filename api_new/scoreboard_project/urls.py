from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

FRONTEND_DIR = settings.BASE_DIR.parent / "frontend"

urlpatterns = [
    path("api/", include("scoreboard.urls")),
    path("", serve, {"document_root": FRONTEND_DIR, "path": "index.html"}),
    re_path(r"^(?P<path>.*)$", serve, {"document_root": FRONTEND_DIR}),
]
