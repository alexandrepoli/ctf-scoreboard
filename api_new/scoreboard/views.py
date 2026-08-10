from django.conf import settings
from django.http import JsonResponse

from scoreboard.ctfd_client import CTFdUnavailableError, ScoreVisibilityError, fetch_scoreboard


def get_scoreboard(request):
    try:
        data = fetch_scoreboard(settings.CTFD_URL)
    except ScoreVisibilityError:
        return JsonResponse({"success": False, "data": []}, status=403)
    except CTFdUnavailableError:
        return JsonResponse({"success": False, "data": []}, status=502)
    except Exception:
        return JsonResponse({"success": False, "data": []}, status=502)
    return JsonResponse({"success": True, "data": data})
