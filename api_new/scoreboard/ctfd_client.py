import requests


class CTFdUnavailableError(Exception):
    pass


class ScoreVisibilityError(Exception):
    pass


def fetch_scoreboard(ctfd_url: str, token: str = "") -> list[dict]:
    # un token n'est necessaire que si l'instance ne publie pas ses scores
    headers = {"Authorization": f"Token {token}"} if token else {}

    try:
        response = requests.get(
            f"{ctfd_url}/api/v1/scoreboard",
            timeout=5,
            headers=headers,
            # sans ca, CTFd renvoie la page de login en 200 et le JSON casse plus loin
            allow_redirects=False,
        )
    except requests.exceptions.RequestException as exc:
        raise CTFdUnavailableError(str(exc)) from exc

    # 302 vers /login = scores non publics et token absent ou invalide
    if response.status_code in (401, 403) or response.is_redirect:
        raise ScoreVisibilityError("Scores are not publicly visible on this CTFd instance")

    if response.status_code != 200:
        raise CTFdUnavailableError(f"CTFd returned status {response.status_code}")

    payload = response.json()
    return [
        {"pos": entry["pos"], "name": entry["name"], "score": entry["score"]}
        for entry in payload.get("data", [])
    ]
