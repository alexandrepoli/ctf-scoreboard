import os

from django.core.wsgi import get_wsgi_application

# manage.py fixe cette variable pour les commandes ; un serveur WSGI, lui,
# importe ce fichier directement et doit la poser lui-meme
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scoreboard_project.settings")

application = get_wsgi_application()
