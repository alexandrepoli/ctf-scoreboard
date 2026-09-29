from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

FRONTEND_DIR = settings.BASE_DIR.parent / "frontend"


def servir_frontend(request, path="index.html"):
    """Sert un fichier du frontend en interdisant le cache heuristique.

    Sans en-tete Cache-Control, Chrome decide lui-meme combien de temps garder
    un fichier, en se basant sur sa date de modification. Sur un ecran en
    kiosque, jamais rafraichi a la main, cela signifie continuer d'afficher
    l'ancien CSS ou l'ancien JS pendant des heures apres une mise a jour --
    et pire, un melange des deux, une moitie a jour et l'autre non.

    no-cache ne supprime pas le cache : il oblige le navigateur a revalider a
    chaque chargement. Le serveur repond alors 304 si rien n'a change, donc
    le cout reseau reste negligeable.
    """
    reponse = serve(request, path, document_root=FRONTEND_DIR)
    reponse["Cache-Control"] = "no-cache, must-revalidate"
    return reponse


urlpatterns = [
    path("api/", include("scoreboard.urls")),
    path("", servir_frontend),
    re_path(r"^(?P<path>.*)$", servir_frontend),
]
