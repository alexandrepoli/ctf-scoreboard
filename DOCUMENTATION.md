# CTF Ocean Scoreboard — Documentation complète

Explication détaillée de chaque fichier, chaque classe, chaque fonction — et pourquoi elle existe.

## Vue d'ensemble

```
Navigateur (frontend/)
      │  fetch("/api/scoreboard") toutes les 7s
      ▼
Django (api_new/)
      │  fetch_scoreboard(CTFD_URL)
      ▼
CTFd réel (Docker, port 8000)
```

Le navigateur ne parle **jamais** directement à CTFd (problèmes CORS + sécurité si on exposait un token d'accès dans le JS). Django sert d'intermédiaire: lui seul interroge CTFd, reformate, republie une version simplifiée.

Structure sur disque:
```
D:\valette\
├── api_new\          ← backend Django
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── db.sqlite3
│   ├── scoreboard\             ← l'app (code métier)
│   └── scoreboard_project\     ← le projet (config globale)
└── frontend\          ← page web statique
    ├── index.html
    ├── style.css
    └── app.js
```

---

## Backend — `api_new/`

### `manage.py`

Point d'entrée de toute commande Django (`runserver`, `test`, `migrate`...).

```python
import os
import sys

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "scoreboard_project.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    main()
```

**Pourquoi il existe:** Django a besoin de savoir quel fichier de config (`settings.py`) utiliser avant de faire quoi que ce soit. `os.environ.setdefault(...)` fixe cette info dans une variable d'environnement, lue ensuite par tout le framework. C'est un fichier généré automatiquement par Django (`django-admin startproject`), quasiment jamais modifié à la main.

### `requirements.txt`

```
Django==5.1.4
requests==2.32.3
python-dotenv==1.0.1
```

| Paquet | Pourquoi |
|---|---|
| `Django` | le framework web lui-même |
| `requests` | fait les appels HTTP sortants vers CTFd (Django ne fournit pas de client HTTP) |
| `python-dotenv` | lit le fichier `.env` et injecte ses variables dans `os.environ` |

### `.env.example`

```
CTFD_URL=http://localhost:8000
```

Template. Copié en `.env` (non versionné) pour changer l'URL de CTFd sans toucher au code — utile si CTFd tourne sur un autre port/serveur.

### `db.sqlite3`

Base de données créée automatiquement par Django car `settings.DATABASES` doit pointer vers quelque chose de valide. **Vide et inutilisée** ici: aucun `models.py` n'a été créé, donc rien n'y est jamais écrit. Elle existe uniquement pour satisfaire Django au démarrage.

---

### `scoreboard_project/` — le **projet** (config globale)

Un projet Django = la configuration générale + le routeur principal. Il ne contient (presque) jamais de logique métier — ça, c'est le rôle des **apps**.

#### `scoreboard_project/__init__.py`

Vide. Sa seule fonction: dire à Python "ce dossier est un package importable" (sans lui, `import scoreboard_project.settings` échouerait).

#### `scoreboard_project/settings.py`

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
```
Charge le fichier `.env` s'il existe, rend ses variables lisibles via `os.getenv(...)`.

```python
BASE_DIR = Path(__file__).resolve().parent.parent
```
`__file__` = ce fichier settings.py. `.parent` = `scoreboard_project/`. `.parent.parent` = `api_new/` (la racine du backend). Sert de point de repère pour construire d'autres chemins (ex: `db.sqlite3`, ou le dossier du frontend dans `urls.py`).

```python
SECRET_KEY = "dev-only-not-for-production"
```
Clé cryptographique utilisée par Django pour signer cookies/sessions/tokens CSRF. Valeur factice ici car le projet n'a ni comptes utilisateurs ni sessions — aucun risque réel en local. **Ne jamais utiliser une clé en dur comme ça en production.**

```python
DEBUG = True
```
Mode développement: affiche les erreurs détaillées dans le navigateur (comme la page jaune "Page not found" avec le chemin exact du fichier manquant que t'as eu). À mettre `False` en production (sinon ça expose des infos internes).

```python
ALLOWED_HOSTS = ["*"]
```
Liste des noms d'hôte autorisés à requêter ce serveur. `"*"` = tous acceptés — pratique en dev, dangereux en prod (on restreindrait à un domaine précis).

```python
INSTALLED_APPS = [
    "scoreboard",
]
```
Liste des apps actives du projet. Une seule ici. Cette liste sert à Django pour savoir où chercher des modèles, migrations, templates, etc. (même si `scoreboard` n'en a aucun).

```python
MIDDLEWARE = []
```
Vide volontairement. Les middlewares par défaut de Django (gestion de sessions, protection CSRF, authentification...) sont conçus pour des sites avec comptes utilisateurs et formulaires — inutiles pour une API en lecture seule sans connexion.

```python
ROOT_URLCONF = "scoreboard_project.urls"
```
Dit à Django où trouver le fichier de routage principal.

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
```
Configuration obligatoire même sans usage réel — Django refuse de démarrer sans un `DATABASES["default"]` valide.

```python
CTFD_URL = os.getenv("CTFD_URL", "http://localhost:8000")
```
Variable **custom** (pas standard Django) ajoutée pour ce projet. Lue depuis `.env`, avec `http://localhost:8000` comme valeur de secours si `.env` n'existe pas. Accessible partout dans le code via `from django.conf import settings` puis `settings.CTFD_URL`.

#### `scoreboard_project/urls.py`

```python
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve

FRONTEND_DIR = settings.BASE_DIR.parent / "frontend"
```
`BASE_DIR` = `api_new/`. `.parent` = son dossier parent (`D:\valette\`). `/ "frontend"` = `D:\valette\frontend`. **C'est ce calcul qui a cassé** quand `api_new` a été déplacé sans que `frontend` suive au même niveau.

```python
urlpatterns = [
    path("api/", include("scoreboard.urls")),
    path("", serve, {"document_root": FRONTEND_DIR, "path": "index.html"}),
    re_path(r"^(?P<path>.*)$", serve, {"document_root": FRONTEND_DIR}),
]
```

| Ligne | Rôle |
|---|---|
| `path("api/", include(...))` | toute URL commençant par `/api/` part se faire router par `scoreboard/urls.py` |
| `path("", serve, ...)` | requête exacte sur `/` → sert `index.html` |
| `re_path(r"^(?P<path>.*)$", serve, ...)` | catch-all: toute autre URL (`/style.css`, `/app.js`...) → cherche le fichier du même nom dans `FRONTEND_DIR` |

**Ordre critique**: Django teste ces règles de haut en bas et s'arrête à la première qui matche. Si le catch-all `.*` était en premier, il intercepterait aussi `/api/scoreboard` (qui matche `.*`) et l'API ne serait jamais atteinte.

`django.views.static.serve` = fonction Django prête à l'emploi qui sert un fichier statique depuis un dossier donné. Volontairement utilisée telle quelle (pas de config `staticfiles`/`whitenoise` en plus) pour rester simple — adaptée au dev, pas à la prod à grande échelle.

---

### `scoreboard/` — l'**app** (le code métier)

Une app Django = un module autonome avec sa propre logique. Le projet peut en avoir plusieurs; ici une seule suffit.

#### `scoreboard/__init__.py`

Vide, même rôle que celui du projet: marque le dossier comme package Python importable.

#### `scoreboard/ctfd_client.py`

```python
import requests
```
Bibliothèque tierce pour faire des requêtes HTTP sortantes.

```python
class CTFdUnavailableError(Exception):
    pass
```
**Pourquoi cette classe existe:** exception personnalisée pour représenter "CTFd est injoignable ou a répondu n'importe quoi". Hériter d'`Exception` (sans rien ajouter, juste `pass`) suffit à créer un type d'erreur distinct et attrapable spécifiquement avec `except CTFdUnavailableError:` — plutôt que d'attraper une erreur générique impossible à distinguer d'une autre.

```python
class ScoreVisibilityError(Exception):
    pass
```
**Pourquoi:** cas différent du précédent — CTFd répond bien, mais refuse de donner les scores (visibilité non publique, HTTP 403). Séparer ce cas de `CTFdUnavailableError` permet au code appelant (`views.py`) de renvoyer un message différent selon la cause exacte.

```python
def fetch_scoreboard(ctfd_url: str) -> list[dict]:
```
**Pourquoi cette fonction et pas une classe:** un seul comportement, sans état à conserver entre deux appels — une fonction pure suffit, pas besoin de la complexité d'une classe (YAGNI: pas de sur-ingénierie).

```python
    try:
        response = requests.get(f"{ctfd_url}/api/v1/scoreboard", timeout=5)
    except requests.exceptions.RequestException as exc:
        raise CTFdUnavailableError(str(exc)) from exc
```
Appelle le vrai endpoint CTFd. `timeout=5` = abandonne après 5 secondes d'attente (sans ça, une requête qui traîne bloquerait toute la réponse indéfiniment). `RequestException` = classe mère de toutes les erreurs réseau de `requests` (DNS cassé, connexion refusée, timeout...) — on les attrape toutes d'un coup et on les retraduit en notre propre exception.

```python
    if response.status_code == 403:
        raise ScoreVisibilityError("Scores are not publicly visible on this CTFd instance")

    if response.status_code != 200:
        raise CTFdUnavailableError(f"CTFd returned status {response.status_code}")
```
Traduit les codes HTTP de CTFd en exceptions typées. 403 = visibilité, tout le reste d'anormal = indisponibilité.

```python
    payload = response.json()
    return [
        {"pos": entry["pos"], "name": entry["name"], "score": entry["score"]}
        for entry in payload.get("data", [])
    ]
```
CTFd renvoie beaucoup plus de champs par équipe (`account_id`, `account_url`, `account_type`, `oauth_id`, `bracket_id`, `bracket_name`, `members`...). Cette liste en compréhension ne garde que les 3 champs utiles au front — **pourquoi**: minimise ce qui transite, évite d'exposer des infos internes CTFd (IDs de compte, etc.) inutiles côté client.

#### `scoreboard/views.py`

```python
from django.conf import settings
from django.http import JsonResponse
from scoreboard.ctfd_client import CTFdUnavailableError, ScoreVisibilityError, fetch_scoreboard

def get_scoreboard(request):
```
**Pourquoi une fonction et pas une classe:** Django accepte deux styles de vues — fonctions (`FBV`) ou classes (`CBV`, ex: `class ScoreboardView(View)`). Pour une seule route simple avec une seule méthode HTTP (`GET`), une fonction est plus directe; les classes servent surtout quand une route doit gérer plusieurs méthodes (`GET`/`POST`/`PUT`...) avec de la logique partagée. `request` (objet `HttpRequest`) est obligatoire en premier paramètre de toute vue Django, même s'il n'est pas utilisé ici (on ne lit ni query params ni body).

```python
    try:
        data = fetch_scoreboard(settings.CTFD_URL)
    except ScoreVisibilityError:
        return JsonResponse({"success": False, "data": []}, status=403)
    except CTFdUnavailableError:
        return JsonResponse({"success": False, "data": []}, status=502)
    except Exception:
        return JsonResponse({"success": False, "data": []}, status=502)
    return JsonResponse({"success": True, "data": data})
```
Le `except Exception:` final est un filet de sécurité: si `fetch_scoreboard` plante pour une raison imprévue (JSON malformé renvoyé par CTFd, champ manquant...), on renvoie quand même une réponse JSON propre au format attendu, plutôt qu'un crash 500 brut qui casserait le contrat `{"success": bool, "data": [...]}` que le front s'attend à recevoir dans tous les cas.

`JsonResponse` = classe Django qui prend un `dict` Python, le sérialise en JSON, pose automatiquement le header `Content-Type: application/json`.

#### `scoreboard/urls.py`

```python
from django.urls import path
from scoreboard.views import get_scoreboard

urlpatterns = [
    path("scoreboard", get_scoreboard, name="scoreboard"),
]
```
Sous-routeur de l'app, inclus depuis `scoreboard_project/urls.py`. Le préfixe `api/` est déjà consommé par le routeur principal, donc `path("scoreboard", ...)` complète l'URL finale en `/api/scoreboard`. `name="scoreboard"` = identifiant interne Django (permettrait de générer cette URL par son nom ailleurs dans le code — pas utilisé ici, mais convention standard qui coûte rien).

#### `scoreboard/tests.py`

```python
import json
from unittest.mock import patch
from django.test import Client, TestCase
from scoreboard.ctfd_client import CTFdUnavailableError, ScoreVisibilityError
```

```python
class ScoreboardViewTests(TestCase):
```
**Pourquoi une classe:** `django.test.TestCase` est la classe de base fournie par Django pour regrouper des tests liés (ici, tous les cas de la vue `get_scoreboard`). Chaque méthode `test_*` à l'intérieur est un test indépendant, lancé automatiquement par `python manage.py test`.

```python
    def setUp(self):
        self.client = Client()
```
`setUp` = méthode spéciale exécutée avant **chaque** test de la classe. `Client()` = faux navigateur fourni par Django, permet de simuler des requêtes HTTP (`self.client.get(...)`) sans faire tourner un vrai serveur.

```python
    @patch("scoreboard.views.fetch_scoreboard")
    def test_scoreboard_success(self, mock_fetch):
        mock_fetch.return_value = [{"pos": 1, "name": "Kraken", "score": 350}]
        response = self.client.get("/api/scoreboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {...})
```
`@patch` remplace temporairement `fetch_scoreboard` (tel qu'importé dans `views.py`) par un faux objet contrôlé (`mock_fetch`). **Pourquoi:** le test doit vérifier uniquement la logique de `views.py` (bon code HTTP, bonne forme JSON selon ce que `fetch_scoreboard` renvoie/lève) — pas dépendre d'un vrai CTFd démarré ou non. `mock_fetch.return_value = ...` simule un succès; dans les deux autres tests, `mock_fetch.side_effect = CTFdUnavailableError(...)` simule une exception levée.

3 tests au total, un par branche du `try/except` de `get_scoreboard`: succès (200), CTFd indisponible (502), scores cachés (403).

---

## Frontend — `frontend/`

### `index.html`

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>🌊 CTF Scoreboard</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>🌊 Classement CTF</h1>
  <div id="status"></div>
  <table id="scoreboard">
    <thead>
      <tr><th>Rang</th><th>Nom</th><th>Score</th></tr>
    </thead>
    <tbody id="scoreboard-body"></tbody>
  </table>
  <script src="app.js"></script>
</body>
</html>
```

Structure minimale, volontairement vide de données au chargement — c'est `app.js` qui remplit `#scoreboard-body` dynamiquement. Deux ancres importantes pour le JS: `id="status"` (zone de message d'erreur) et `id="scoreboard-body"` (le `<tbody>` où les lignes sont injectées).

### `style.css`

Thème visuel "mer": dégradé de bleu profond vers turquoise (`linear-gradient`), tableau semi-transparent par-dessus (`rgba(1, 42, 74, 0.6)`), première ligne du classement mise en évidence en jaune doré (`tbody tr:first-child`). Purement cosmétique, aucune logique.

### `app.js`

```javascript
const REFRESH_MS = 7000;
```
Constante: intervalle de rafraîchissement en millisecondes. Nommée plutôt que le chiffre `7000` écrit en dur plus bas — si on veut changer la fréquence, un seul endroit à modifier.

```javascript
let fetchInFlight = false;
```
**Pourquoi cette variable:** garde-fou contre les requêtes qui se chevauchent. Si une requête met plus de 7 secondes à répondre (réseau lent, backend chargé), le `setInterval` suivant se déclencherait quand même et lancerait une 2ème requête en parallèle — avec le risque qu'elle réponde *avant* la première et affiche des données obsolètes ensuite quand la première finit. `fetchInFlight` empêche de démarrer une nouvelle requête tant que la précédente n'est pas terminée.

```javascript
function renderRow(team) {
  const tr = document.createElement("tr");
  for (const value of [team.pos, team.name, team.score]) {
    const td = document.createElement("td");
    td.textContent = value;
    tr.appendChild(td);
  }
  return tr;
}
```
**Pourquoi cette fonction existe séparément, et pourquoi `textContent` plutôt que `innerHTML`:** construit une ligne `<tr>` en assemblant des éléments DOM un par un, avec `td.textContent = value` (jamais de concaténation de chaînes HTML). C'est une correction de sécurité: `team.name` vient de CTFd et peut être n'importe quoi tapé par un participant (ex: `<script>...</script>` comme nom d'équipe). `textContent` insère toujours du texte brut, jamais interprété comme du HTML — donc aucun script ne peut s'exécuter. La version initiale utilisait un template string injecté via `innerHTML`, ce qui aurait été une faille XSS réelle et facilement exploitable dans un contexte CTF.

```javascript
async function loadScoreboard() {
  if (fetchInFlight) return;
  fetchInFlight = true;

  const statusEl = document.getElementById("status");
  const bodyEl = document.getElementById("scoreboard-body");

  try {
    const response = await fetch("/api/scoreboard");
    const payload = await response.json();

    if (!response.ok || !payload.success) {
      statusEl.textContent = response.status === 403
        ? "Scores non publics sur cette instance CTFd."
        : "Scoreboard indisponible.";
      return;
    }

    statusEl.textContent = "";
    bodyEl.replaceChildren(...payload.data.map(renderRow));
  } catch (err) {
    statusEl.textContent = "Scoreboard indisponible.";
  } finally {
    fetchInFlight = false;
  }
}
```
Fonction principale, `async` car `fetch` est asynchrone (retourne une `Promise`).

- `fetch("/api/scoreboard")` — requête relative: part toujours vers le même serveur qui a servi la page (Django), jamais besoin d'écrire l'URL complète.
- `response.ok` — vrai si le code HTTP est 2xx. Combiné à `payload.success`, couvre à la fois les erreurs HTTP et les erreurs "métier" renvoyées avec un statut non-200.
- `response.status === 403` — distingue le message affiché selon la cause (visibilité vs indisponibilité), pour donner une info utile plutôt qu'un message générique.
- `bodyEl.replaceChildren(...payload.data.map(renderRow))` — vide et remplit le tableau en une seule opération DOM (`replaceChildren` retire tous les enfants existants et les remplace par la nouvelle liste), plus efficace et plus sûr que manipuler `innerHTML`.
- `catch (err)` — filet pour les erreurs réseau pures (serveur injoignable, pas seulement une réponse d'erreur).
- `finally { fetchInFlight = false; }` — s'exécute dans tous les cas (succès, erreur gérée, exception) pour libérer le verrou et permettre le prochain rafraîchissement.

```javascript
loadScoreboard();
setInterval(loadScoreboard, REFRESH_MS);
```
Premier appel immédiat au chargement de la page (sinon il faudrait attendre 7s avant de voir quoi que ce soit), puis répétition automatique toutes les `REFRESH_MS` millisecondes.

---

## Flux complet d'une requête `/`

```
1. Navigateur ouvre http://localhost:5001/
2. Django (urls.py) → route "" → sert frontend/index.html
3. Le navigateur charge index.html → déclenche le chargement de style.css et app.js
4. app.js exécute loadScoreboard() immédiatement
5. fetch("/api/scoreboard") → Django (urls.py) → route "api/" → scoreboard/urls.py
   → scoreboard/views.py::get_scoreboard()
   → scoreboard/ctfd_client.py::fetch_scoreboard()
   → requête HTTP réelle vers CTFd (http://localhost:8000/api/v1/scoreboard)
6. CTFd répond avec les données brutes → ctfd_client.py les filtre (pos/name/score)
   → views.py les enveloppe dans {"success": true, "data": [...]}
7. app.js reçoit ce JSON → renderRow() construit les <tr> → tableau affiché
8. setInterval relance l'étape 4 toutes les 7 secondes
```
