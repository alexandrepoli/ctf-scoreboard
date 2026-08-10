import json
from unittest.mock import patch

from django.test import Client, TestCase

from scoreboard.ctfd_client import CTFdUnavailableError, ScoreVisibilityError


class ScoreboardViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("scoreboard.views.fetch_scoreboard")
    def test_scoreboard_success(self, mock_fetch):
        mock_fetch.return_value = [{"pos": 1, "name": "Kraken", "score": 350}]

        response = self.client.get("/api/scoreboard")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content),
            {"success": True, "data": [{"pos": 1, "name": "Kraken", "score": 350}]},
        )

    @patch("scoreboard.views.fetch_scoreboard")
    def test_scoreboard_ctfd_unavailable(self, mock_fetch):
        mock_fetch.side_effect = CTFdUnavailableError("boom")

        response = self.client.get("/api/scoreboard")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(json.loads(response.content), {"success": False, "data": []})

    @patch("scoreboard.views.fetch_scoreboard")
    def test_scoreboard_hidden(self, mock_fetch):
        mock_fetch.side_effect = ScoreVisibilityError("hidden")

        response = self.client.get("/api/scoreboard")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content), {"success": False, "data": []})
