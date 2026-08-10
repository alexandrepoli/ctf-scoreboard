import requests


class CTFdUnavailableError(Exception):
    pass


class ScoreVisibilityError(Exception):
    pass


def fetch_scoreboard(ctfd_url: str) -> list[dict]:
    try:
        response = requests.get(f"{ctfd_url}/api/v1/scoreboard", timeout=5)
    except requests.exceptions.RequestException as exc:
        raise CTFdUnavailableError(str(exc)) from exc

    if response.status_code == 403:
        raise ScoreVisibilityError("Scores are not publicly visible on this CTFd instance")

    if response.status_code != 200:
        raise CTFdUnavailableError(f"CTFd returned status {response.status_code}")

    payload = response.json()
    return [
        {"pos": entry["pos"], "name": entry["name"], "score": entry["score"]}
        for entry in payload.get("data", [])
    ]
