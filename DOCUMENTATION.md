# CTF Ocean Scoreboard — Documentation complète

Explication détaillée de chaque fichier, chaque classe, chaque fonction — et pourquoi elle existe.

## Vue d'ensemble

```
Navigateur (frontend/)
      │  fetch("/api/scoreboard") toutes les 7 s
      ▼
Django (api_new/)
      │  GET {CTFD_URL}/api/v1/scoreboard  (+ jeton si besoin)
      ▼
CTFd (Docker local, ou instance distante)
```

Le navigateur ne parle **jamais** directement à CTFd. Deux raisons : les problèmes de CORS, et surtout le fait qu'un jeton d'accès exposé dans le JS serait lisible par n'importe quel spectateur. Django sert d'intermédiaire : lui seul interroge CTFd, garde le jeton, reformate, et republie une version réduite.

Structure sur disque :

```
api_new/                     backend Django
├── manage.py
├── requirements.txt
├── .env.example
├── db.sqlite3
├── scoreboard/              l'app (code métier)
└── scoreboard_project/      le projet (config globale)
frontend/                    page statique
├── index.html
├── style.css
├── app.js
├── logo-hackagou.png        logo des organisateurs (filigrane)
├── logo-icone.webp          icone d'onglet
├── double.html              variante 40 rangs, deux colonnes
├── double.css               ce qui change par rapport a style.css
└── double.js                logique a deux colonnes
docs/scoreboard.png          capture du tableau simple
docs/scoreboard-double.png   capture du double tableau (README)
```

---

## Backend — `api_new/`

### `manage.py`

Point d'entrée de toute commande Django (`runserver`, `test`, `migrate`...).

**Pourquoi il existe :** Django doit savoir quel fichier de configuration utiliser avant de faire quoi que ce soit. `os.environ.setdefault("DJANGO_SETTINGS_MODULE", ...)` fixe cette information dans une variable d'environnement, lue ensuite par tout le framework. Fichier généré par `django-admin startproject`, quasiment jamais modifié à la main.

### `requirements.txt`

| Paquet | Pourquoi |
|---|---|
| `Django` | le framework web lui-même |
| `requests` | fait les appels HTTP sortants vers CTFd (Django ne fournit pas de client HTTP) |
| `python-dotenv` | lit le fichier `.env` et injecte ses variables dans `os.environ` |

### `.env.example` et `.env`

```
CTFD_URL=https://legacy.hackagou.nc

# Uniquement si l'instance ne publie pas ses scores.
# CTFd : Admin > Settings > Access Tokens
CTFD_TOKEN=
```

`.env.example` est versionné, `.env` ne l'est pas (`.gitignore`). **Pourquoi cette séparation :** `.env` contient le jeton d'accès réel, qui ne doit jamais partir sur GitHub. Le `.example` documente les clés attendues sans livrer de secret.

⚠️ `.env` n'est lu qu'au démarrage du processus. Le rechargeur automatique de `runserver` ne surveille que les `.py` : après avoir modifié `.env`, **il faut redémarrer le serveur**, sinon l'ancienne valeur reste en mémoire.

### `db.sqlite3`

Base créée automatiquement parce que `settings.DATABASES` doit pointer vers quelque chose de valide. **Vide et inutilisée** : aucun `models.py` n'existe, rien n'y est jamais écrit. Elle existe uniquement pour satisfaire Django au démarrage.

---

### `scoreboard_project/` — le **projet** (config globale)

Un projet Django = la configuration générale + le routeur principal. Presque jamais de logique métier : c'est le rôle des **apps**.

#### `settings.py`

```python
load_dotenv()
```
Charge `.env` s'il existe et rend ses variables lisibles via `os.getenv(...)`.

```python
BASE_DIR = Path(__file__).resolve().parent.parent
```
`.parent` = `scoreboard_project/`, `.parent.parent` = `api_new/`. Point de repère pour construire les autres chemins (`db.sqlite3`, dossier du frontend dans `urls.py`).

```python
SECRET_KEY = "dev-only-not-for-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]
```
Configuration de développement assumée : le projet n'a ni comptes utilisateurs, ni sessions, ni formulaires. `DEBUG = True` affiche les erreurs détaillées, `ALLOWED_HOSTS = ["*"]` accepte n'importe quel nom d'hôte — pratique sur le réseau d'un événement, à durcir avant toute exposition publique.

```python
INSTALLED_APPS = ["scoreboard"]
MIDDLEWARE = []
```
`MIDDLEWARE` est vide **volontairement** : les middlewares par défaut (sessions, CSRF, authentification) servent des sites avec comptes et formulaires. Ici l'API est en lecture seule et sans connexion, ils ne feraient que coûter du temps par requête.

```python
CTFD_URL = os.getenv("CTFD_URL", "http://localhost:8000")
CTFD_TOKEN = os.getenv("CTFD_TOKEN", "")
```
Deux réglages **custom** (pas des clés Django standard). Valeurs de repli : l'instance Docker locale, sans jeton. Lisibles partout via `from django.conf import settings`.

#### `urls.py`

```python
FRONTEND_DIR = settings.BASE_DIR.parent / "frontend"

urlpatterns = [
    path("api/", include("scoreboard.urls")),
    path("", serve, {"document_root": FRONTEND_DIR, "path": "index.html"}),
    re_path(r"^(?P<path>.*)$", serve, {"document_root": FRONTEND_DIR}),
]
```

| Ligne | Rôle |
|---|---|
| `path("api/", include(...))` | toute URL commençant par `/api/` part vers `scoreboard/urls.py` |
| `path("", serve, ...)` | requête sur `/` → sert `index.html` |
| `re_path(r"^(?P<path>.*)$", ...)` | catch-all : `/style.css`, `/app.js`... cherchés dans `FRONTEND_DIR` |

**Ordre critique :** Django teste de haut en bas et s'arrête à la première règle qui correspond. Si le catch-all était en premier, il intercepterait aussi `/api/scoreboard` et l'API ne serait jamais atteinte.

`django.views.static.serve` sert les fichiers du frontend sans configuration `staticfiles`. Volontairement minimal : adapté au dev et à un affichage local, pas à de la production à grande échelle.

---

### `scoreboard/` — l'**app** (code métier)

#### `ctfd_client.py`

```python
class CTFdUnavailableError(Exception): pass
class ScoreVisibilityError(Exception): pass
```

**Pourquoi deux exceptions :** les deux échecs n'ont pas la même cause ni le même remède. `CTFdUnavailableError` = CTFd est injoignable ou répond n'importe quoi (problème d'infrastructure). `ScoreVisibilityError` = CTFd répond très bien mais refuse de donner les scores (problème d'autorisation). Les séparer permet à `views.py` de renvoyer un code HTTP différent, et donc à la page d'afficher un message qui dit la vérité.

```python
def fetch_scoreboard(ctfd_url: str, token: str = "") -> list[dict]:
    headers = (
        {"Authorization": f"Token {token}", "Content-Type": "application/json"}
        if token
        else {}
    )
```

**Le `Content-Type` n'est pas décoratif.** CTFd n'honore l'en-tête `Authorization` que si la requête est en JSON — son code fait `if token and request.is_json` avant de résoudre le jeton. Sans `Content-Type: application/json`, le jeton est ignoré **en silence** et la requête repart vers `/login`. C'est le piège le plus coûteux de ce fichier, d'où le test dédié.

```python
    response = requests.get(
        f"{ctfd_url}/api/v1/scoreboard",
        timeout=5,
        headers=headers,
        allow_redirects=False,
    )
```

`timeout=5` : sans lui, une requête qui traîne bloquerait la réponse indéfiniment.

`allow_redirects=False` : **c'est ce qui rend le diagnostic honnête.** Quand les scores ne sont pas publics, CTFd répond `302` vers `/login`. Avec le comportement par défaut de `requests`, la redirection est suivie, la page HTML de connexion arrive avec un code 200, puis `.json()` explose — et l'utilisateur voit « Scoreboard indisponible », c'est-à-dire un message d'erreur réseau pour un problème d'autorisation.

```python
    if response.status_code in (401, 403) or response.is_redirect:
        raise ScoreVisibilityError(...)
    if response.status_code != 200:
        raise CTFdUnavailableError(f"CTFd returned status {response.status_code}")
```

Les trois signes d'un refus d'accès (`401`, `403`, redirection) sont traités ensemble ; tout autre code anormal devient une indisponibilité.

```python
    payload = response.json()
    return [
        {"pos": entry["pos"], "name": entry["name"], "score": entry["score"]}
        for entry in payload.get("data", [])
    ]
```

CTFd renvoie bien plus de champs par compte (`account_id`, `account_url`, `account_type`, `oauth_id`, `bracket_id`, `members`...). **Pourquoi ne garder que trois champs :** ce qui ne sort pas du serveur ne peut pas fuiter, et le contrat avec le front reste petit et stable.

À noter : le format est le même que l'instance tourne en mode *users* ou en mode *teams*. Le front affiche `name`, sans se soucier de ce qu'il y a derrière.

#### `views.py`

```python
def get_scoreboard(request):
    try:
        data = fetch_scoreboard(settings.CTFD_URL, settings.CTFD_TOKEN)
    except ScoreVisibilityError:
        return JsonResponse({"success": False, "data": []}, status=403)
    except CTFdUnavailableError:
        return JsonResponse({"success": False, "data": []}, status=502)
    except Exception:
        return JsonResponse({"success": False, "data": []}, status=502)
    return JsonResponse({"success": True, "data": data})
```

**Pourquoi une fonction et pas une classe :** une seule route, une seule méthode HTTP. Les vues-classes servent surtout quand une route gère `GET`/`POST`/`PUT` avec de la logique partagée. `request` est obligatoire en premier paramètre même s'il n'est pas utilisé ici.

Le `except Exception` final est un filet : si `fetch_scoreboard` casse pour une raison imprévue (JSON malformé, champ manquant), on renvoie quand même une réponse au format attendu plutôt qu'une 500 brute. Le contrat `{"success": bool, "data": [...]}` tient dans tous les cas, ce qui simplifie le code du front.

#### `urls.py`

```python
urlpatterns = [path("scoreboard", get_scoreboard, name="scoreboard")]
```

Le préfixe `api/` est déjà consommé par le routeur principal : l'URL finale est `/api/scoreboard`.

#### `tests.py` — 5 tests

`ScoreboardViewTests` (3 tests) couvre les trois branches de la vue en remplaçant `fetch_scoreboard` par un mock : succès (200), CTFd injoignable (502), scores cachés (403). **Pourquoi mocker :** le test doit valider la logique de la vue, pas dépendre d'une instance CTFd démarrée.

`CTFdClientTests` (2 tests) mocke `requests.get` et verrouille les deux subtilités du client :

- une réponse `302` doit lever `ScoreVisibilityError` (et non partir dans la branche « indisponible ») ;
- le jeton doit être envoyé **avec** `Content-Type: application/json`.

Ce second test existe parce que la règle `request.is_json` de CTFd est invisible depuis notre code : sans lui, un refactor bien intentionné qui retire le `Content-Type` casserait l'authentification sans faire échouer un seul test.

```bash
python api_new/manage.py test
```

---

## Frontend — `frontend/`

### `index.html`

Structure minimale, vide de données au chargement : c'est `app.js` qui remplit `#scoreboard-body`.

```html
<body>
  <div id="status"></div>
  <div class="hull">
    <table id="scoreboard">
      <thead><tr><th>Rang</th><th>Nom</th><th>Score</th></tr></thead>
      <tbody id="scoreboard-body"></tbody>
    </table>
  </div>
  <script src="app.js"></script>
</body>
```

Trois ancres pour le reste du code : `#status` (zone de message), `#scoreboard-body` (lignes injectées), `.hull` (la coque, qui porte le décor).

L'icône d'onglet (`logo-icone.webp`) est l'icône HacKagou fournie par les organisateurs.

Il n'y a **pas de titre** : sur un écran dédié, le contexte est connu de la salle, et les 20 lignes valent mieux que deux lignes d'en-tête.

Les polices viennent de Google Fonts : **Bodoni Moda**, une didone dans l'esprit des éditions Hetzel de Jules Verne, pour les rangs et le leader ; **Share Tech Mono** pour les noms et les scores, qui donne des chiffres de largeur fixe et un air de relevé d'instrument.

### `style.css`

Thème « Nautilus » : coque de métal rivetée posée sur une colonne d'eau qui s'assombrit vers l'abysse.

**Jetons de couleur** (`:root`) — laiton, laiton clair et sombre, phosphore (le turquoise des scores), cuivre (les messages d'erreur), argent et bronze pour le podium, plus les deux bornes de la colonne d'eau.

**`.hull`** empile quatre couches de fond dans une seule propriété : deux rails de rivets (`radial-gradient` répétés horizontalement), un halo de lumière de surface, et le dégradé vertical de la colonne d'eau. Aucune image n'est chargée.

**`.hull::before`** pose le logo des organisateurs en filigrane : centré, sur 72 % de la hauteur de la coque, à 8 % d'opacité. **Pourquoi un pseudo-élément et pas une couche de fond de plus :** une couche de `background` ne peut pas avoir sa propre opacité, alors qu'un pseudo-élément si. Le logo est blanc sur transparent, il n'est pas recoloré — c'est une marque. Il se place naturellement dans l'espace vide entre les noms (à gauche) et les scores (à droite), et reste sous le tableau (`z-index` 0 contre 1), donc sous les plaques et les bulles.

**`.hull::after`** dessine les bulles : huit `radial-gradient` dans une tuile de 260 px, animée en boucle vers le haut. **Pourquoi une tuile plutôt que des éléments :** le motif se répète à l'identique, donc le raccord de la boucle est invisible, et il n'y a aucun nœud DOM supplémentaire à animer.

**Les plaques.** `border-collapse: separate` + `border-spacing: 0 7px` détachent les lignes les unes des autres ; on voit la colonne d'eau passer entre elles. Chaque `td` porte son fond, une arête haute claire et une ombre basse. **Pourquoi des bordures et pas des `box-shadow` :** une ombre posée par cellule laisse des coutures verticales visibles entre rang, nom et score ; une bordure horizontale se raccorde d'une cellule à l'autre.

**Le podium.** Or, argent et bronze sur le texte, le fond et l'arête. Un `::before` en disque, placé derrière le numéro (`z-index: -1`), fait la médaille, avec son reflet décentré. Ces règles arrivent **après** celles des couleurs de podium : dans l'autre ordre, un `background` en raccourci effacerait le disque.

Ces règles ciblent l'attribut `data-podium`, posé par le JS d'après le rang réel, et non les trois premières lignes du tableau. **Pourquoi :** l'écran fait défiler le classement ; sur la page des rangs 21 à 40, les trois premières lignes du tableau ne sont pas un podium.

**Le filigrane est à 20 % d'opacité.** À 8 %, il était propre de près et invisible depuis le fond d'une salle.

**Le reflet du leader** balaie sa plaque toutes les 7 s. Il exclut la colonne du rang (`td:not(:first-child)`), sinon il écraserait le fond de la médaille.

**Les flèches de mouvement** sont des `::after` sur la cellule du rang, pilotées par l'attribut `data-mouvement` posé en JS : ▲ vert pour une montée, ▼ cuivre pour une descente.

**Dimensionnement.** Tout est en `vh` pour que les 20 lignes tiennent quel que soit l'écran, avec un `line-height` explicite — sans lui, les métriques de la didone (plus hautes que celles du mono) font déborder la vingtième ligne. Une requête média resserre le tout sous 760 px de large.

`prefers-reduced-motion: reduce` coupe les bulles et le reflet.

### `app.js`

```javascript
const REFRESH_MS = 7000;   // intervalle de rafraîchissement des données
const PAR_PAGE = 20;       // lignes affichées à la fois
const PAGE_MS = 15000;     // temps passé sur une page avant de montrer la suite
const MOVE_MS = 700;       // durée de l'animation de dépassement
```

**Le classement défile.** L'écran montre les 20 premiers, puis les 20 suivants, et ainsi de suite jusqu'au dernier avant de revenir en tête. Sans ça, une équipe hors du top 20 n'apparaissait jamais. Deux minuteurs indépendants : un pour les données, un pour la page affichée — le classement reste à jour même pendant qu'on regarde la page des rangs 81 à 100.

Avec 330 participants, un tour complet prend un peu plus de quatre minutes. Pour ne montrer que les premiers, limiter la liste dans `pageSuivante`.

```javascript
let fetchInFlight = false;
```
**Garde-fou contre les requêtes qui se chevauchent.** Si une requête met plus de 7 s, le `setInterval` suivant en lancerait une deuxième en parallèle — avec le risque qu'elle réponde avant la première et qu'un affichage obsolète vienne écraser un affichage récent.

```javascript
const rows = new Map();                 // nom -> <tr>
const positionsPrecedentes = new Map(); // nom -> rang au dernier refresh
```

**`rows` est la clé de toute l'animation.** Chaque équipe garde sa `<tr>` d'un rafraîchissement à l'autre. Si on reconstruisait les lignes à chaque fois, il n'y aurait aucun élément commun entre deux états, donc rien à animer : le tableau sauterait d'un classement à l'autre.

```javascript
function getRow(team) { ... }
```
Récupère ou crée la ligne, met à jour les trois cellules via `textContent`, puis compare le rang au précédent pour poser `data-mouvement`.

`textContent`, jamais `innerHTML` : `team.name` est saisi par les participants et peut contenir n'importe quoi, y compris `<script>`. `textContent` insère du texte brut, jamais interprété comme du HTML — sans quoi la faille XSS serait réelle et triviale à exploiter dans un contexte CTF.

```javascript
function render(data) {
  const before = new Map();
  for (const tr of bodyEl.children) before.set(tr, tr.getBoundingClientRect().top);

  bodyEl.replaceChildren(...data.slice(0, MAX_TEAMS).map(getRow));

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  for (const tr of bodyEl.children) {
    const delta = before.get(tr) - tr.getBoundingClientRect().top;
    if (!delta) continue;
    tr.animate([{ transform: `translateY(${delta}px)` }, { transform: "none" }],
               { duration: MOVE_MS, easing: "cubic-bezier(0.4, 0, 0.2, 1)" });
  }
}
```

C'est la technique **FLIP** (*First, Last, Invert, Play*) : on relève la position de départ, on laisse le navigateur poser la nouvelle mise en page, puis on rejoue l'écart en `transform`. **Pourquoi `transform` :** c'est la seule propriété (avec `opacity`) que le navigateur peut animer sans recalculer la mise en page à chaque image — 20 lignes qui bougent en même temps restent fluides, y compris sur un Raspberry Pi.

L'API Web Animations (`tr.animate`) évite d'avoir à ajouter puis retirer des classes CSS et à écouter la fin de la transition.

```javascript
async function loadScoreboard() { ... }
```

- `fetch("/api/scoreboard")` — URL relative : la requête part toujours vers le serveur qui a servi la page.
- `response.ok` combiné à `payload.success` couvre à la fois les erreurs HTTP et les erreurs métier.
- `response.status === 403` distingue « scores non publics » de « scoreboard indisponible » : deux causes, deux messages, deux remèdes.
- `finally { fetchInFlight = false; }` libère le verrou quoi qu'il arrive.

Les positions précédentes sont mémorisées **pour tout le classement**, pas seulement pour la page visible : sinon une équipe reviendrait à l'écran avec une flèche calculée sur un classement vieux de plusieurs minutes.

```javascript
loadScoreboard();
setInterval(loadScoreboard, REFRESH_MS);
```
Premier appel immédiat, sinon la page resterait vide 7 s.

---

## Variante 40 rangs — `double.html`, `double.css`, `double.js`

Même principe, deux colonnes : rangs 1 à 20 à gauche, 21 à 40 à droite. Servie à `/double.html` par le catch-all de `urls.py`, sans changement côté backend. Le tableau simple reste intact à `/`.

**Une seule coque pour les deux colonnes.** Une équipe qui passe du rang 22 au rang 18 change de `<tbody>`. Dans une seule coque, sa ligne traverse l'écran ; avec deux cadres séparés, chacun en `overflow: hidden`, elle disparaîtrait d'un côté pour réapparaître de l'autre.

**`double.css`** ne contient que les écarts avec `style.css` :

- la grille à deux colonnes (`.colonnes`) ;
- les noms trop longs coupés par « … », sinon un nom long élargit sa colonne et pousse l'autre ;
- la remise à zéro du podium dans la colonne de droite. Les règles de podium de `style.css` visent les trois premières lignes **de chaque** `<tbody>` : à droite, ce sont les rangs 21 à 23, qui prendraient sinon l'or, l'argent et le bronze ;
- l'alignement des lignes entre colonnes. La plaque du leader est plus haute : rang en `1.24em`, marge `.34em`, soit `1.24 × (1.2 + 2 × .34) = 2,331em`. Le rang 21 reçoit une marge de `.479em`, qui donne la même hauteur (`1.08 × (1.2 + 2 × .479)`). Tout étant en `em`, l'alignement tient à toutes les tailles d'écran.

**`double.js`** reprend `app.js` avec deux différences :

- `render` répartit les 40 premières lignes entre `#corps-gauche` et `#corps-droite` ;
- le FLIP mesure la position **horizontale et verticale** (`translate(dx, dy)` au lieu de `translateY`), puisqu'une ligne peut changer de colonne.

Le nom complet est aussi posé en `title` sur la cellule, pour les noms tronqués.

---

## Flux complet d'une requête `/`

```
1. Navigateur ouvre http://localhost:5001/
2. Django (urls.py) → route "" → sert frontend/index.html
3. index.html charge style.css et app.js
4. app.js exécute loadScoreboard() immédiatement
5. fetch("/api/scoreboard") → scoreboard/views.py::get_scoreboard()
   → ctfd_client.py::fetch_scoreboard(CTFD_URL, CTFD_TOKEN)
   → GET {CTFD_URL}/api/v1/scoreboard, en JSON, sans suivre les redirections
6. CTFd répond → le client ne garde que pos/name/score
   → la vue enveloppe dans {"success": true, "data": [...]}
7. app.js réutilise les <tr> existantes, réordonne, rejoue les écarts en FLIP
8. setInterval relance l'étape 4 toutes les 7 secondes
```

---

## Notes d'exploitation

**Cache du navigateur.** Django sert les fichiers du frontend avec un `Last-Modified` : après une mise à jour de `style.css` ou `app.js`, un navigateur déjà ouvert peut continuer à servir l'ancienne version. Forcer le rechargement (Ctrl+F5). À garder en tête sur un affichage en kiosque, qui n'est jamais rechargé à la main.

**Sécurité.** La configuration livrée (`DEBUG = True`, `ALLOWED_HOSTS = ["*"]`, clé secrète en dur) vise un usage local sur le réseau de l'événement. À durcir avant toute exposition publique. Le jeton CTFd ne quitte jamais le serveur : il n'apparaît ni dans le HTML, ni dans le JS, ni dans les URL — un jeton passé en paramètre d'URL finirait dans les journaux d'accès, l'historique du navigateur et l'en-tête `Referer`.
