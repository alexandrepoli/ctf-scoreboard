import json
from unittest.mock import patch

from django.test import Client, TestCase

from scoreboard.ctfd_client import (
    CTFdUnavailableError,
    ScoreVisibilityError,
    fetch_scoreboard,
)


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


class CTFdClientTests(TestCase):
    @patch("scoreboard.ctfd_client.requests.get")
    def test_login_redirect_is_a_visibility_error(self, mock_get):
        # CTFd renvoie 302 vers /login quand les scores ne sont pas publics
        mock_get.return_value.status_code = 302
        mock_get.return_value.is_redirect = True

        with self.assertRaises(ScoreVisibilityError):
            fetch_scoreboard("https://exemple.test")

    @patch("scoreboard.ctfd_client.requests.get")
    def test_token_is_sent_as_authorization_header(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.is_redirect = False
        mock_get.return_value.json.return_value = {"data": []}

        fetch_scoreboard("https://exemple.test", "jeton")

        self.assertEqual(
            mock_get.call_args.kwargs["headers"],
            {"Authorization": "Token jeton", "Content-Type": "application/json"},
        )
