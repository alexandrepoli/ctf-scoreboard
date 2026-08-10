from django.urls import path

from scoreboard.views import get_scoreboard

urlpatterns = [
    path("scoreboard", get_scoreboard, name="scoreboard"),
]
