# python:3.13-slim existe en arm64 : la meme image tourne sur le Raspberry Pi
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# les dependances sont copiees seules : tant que requirements.txt ne bouge pas,
# Docker reutilise cette couche et ne reinstalle rien
COPY api_new/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0

COPY api_new/ ./api_new/
COPY frontend/ ./frontend/

# l'app ne stocke rien et n'a pas besoin d'ecrire : elle tourne sans privileges
RUN useradd --create-home --uid 1001 scoreboard
USER scoreboard

EXPOSE 5001

# gunicorn plutot que runserver : ce dernier est un serveur de developpement,
# mono-thread et explicitement deconseille par Django hors developpement.
# 2 workers suffisent pour un ecran qui interroge l'API toutes les 7 s.
CMD ["gunicorn", "--chdir", "api_new", "--bind", "0.0.0.0:5001", \
     "--workers", "2", "--access-logfile", "-", \
     "scoreboard_project.wsgi:application"]
