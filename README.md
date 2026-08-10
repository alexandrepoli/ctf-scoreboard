# Classement CTF

Affichage plein écran du classement d'une instance [CTFd](https://github.com/CTFd/CTFd), pensé pour un vidéoprojecteur ou un écran de salle : 20 équipes visibles d'un coup, rafraîchissement automatique, et animation de glissement quand une équipe en dépasse une autre.

![Classement CTF](docs/scoreboard.png)

## Comment ça marche

```
Navigateur (frontend/)
      │  fetch("/api/scoreboard") toutes les 7 s
      ▼
Django (api_new/)
      │  GET {CTFD_URL}/api/v1/scoreboard
      ▼
CTFd (Docker, port 8000)
```

Le navigateur ne parle jamais directement à CTFd : Django sert d'intermédiaire, ce qui évite les problèmes de CORS et ne laisse filtrer côté client que `pos`, `name` et `score` — les champs internes de CTFd (identifiants de compte, membres, brackets…) ne sortent pas du serveur.

## Prérequis

- Python 3.11+
- Une instance CTFd accessible (Docker ou distante)

## Installation

```bash
pip install -r api_new/requirements.txt
```

```bash
cp api_new/.env.example api_new/.env
```

`.env` contient l'adresse de l'instance CTFd :

```
CTFD_URL=http://localhost:8000
```

## Lancement

```bash
python api_new/manage.py runserver 5001
```

Le classement est sur <http://localhost:5001> — Django sert aussi les fichiers statiques du `frontend/`, il n'y a pas de second serveur à démarrer.

## Tests

```bash
python api_new/manage.py test
```

Trois tests couvrent les trois branches de la vue : succès (200), CTFd injoignable (502), scores non publics (403). Ils utilisent un mock, aucune instance CTFd n'est nécessaire.

## Réglages

| Où | Quoi |
|---|---|
| `frontend/app.js` — `REFRESH_MS` | intervalle de rafraîchissement (7000 ms) |
| `frontend/app.js` — `MAX_TEAMS` | nombre d'équipes affichées (20) |
| `frontend/app.js` — `MOVE_MS` | durée de l'animation de dépassement (700 ms) |
| `api_new/.env` — `CTFD_URL` | adresse de l'instance CTFd |

L'animation repose sur la technique FLIP : chaque `<tr>` est conservée d'un rafraîchissement à l'autre dans une `Map` indexée par nom d'équipe, on mesure sa position avant et après le tri, et on rejoue l'écart. Sans cette réutilisation des nœuds, le tableau serait reconstruit à chaque fois et aucune transition ne serait possible.

Les tailles sont exprimées en `vh` pour que les 20 lignes tiennent dans un écran quelle que soit sa hauteur.

## Structure

```
api_new/                     backend Django
├── scoreboard/              l'app : client CTFd, vue, routes, tests
└── scoreboard_project/      config globale et routeur principal
frontend/                    page statique (index.html, style.css, app.js)
DOCUMENTATION.md             explication détaillée de chaque fichier
```

`DOCUMENTATION.md` détaille le rôle de chaque fichier, classe et fonction.

## Sécurité

Les noms d'équipes viennent de CTFd et sont saisis par les participants : ils sont insérés via `textContent`, jamais via `innerHTML`, pour qu'un nom contenant du HTML ne puisse pas être interprété.

La configuration fournie (`DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, clé secrète en dur) vise un usage local sur le réseau de l'événement. À durcir avant toute exposition publique.
