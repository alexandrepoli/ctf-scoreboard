const REFRESH_MS = 7000;
const PAR_COLONNE = 20;
const PAR_PAGE = 2 * PAR_COLONNE;
const PAGE_MS = 15000;
const MOVE_MS = 700;

let fetchInFlight = false;
// une <tr> par equipe, reutilisee d'un refresh a l'autre : c'est ce qui rend
// l'animation possible, y compris quand la ligne change de colonne
const rows = new Map();
// position au rafraichissement precedent : sert a marquer qui monte et qui descend
const positionsPrecedentes = new Map();

// dernier classement recu, et rang a partir duquel la page affichee commence
let classement = [];
let debutPage = 0;

function getRow(team) {
  let tr = rows.get(team.name);
  if (!tr) {
    tr = document.createElement("tr");
    tr.append(...[0, 1, 2].map(() => document.createElement("td")));
    rows.set(team.name, tr);
  }
  const [pos, name, score] = tr.children;
  pos.textContent = team.pos;
  name.textContent = team.name;
  name.title = team.name;
  score.textContent = team.score;

  // le podium suit le rang reel, pas la position dans la colonne : sans ca,
  // les rangs 21 a 23 prendraient l'or et l'argent en haut de la colonne droite
  if (team.pos <= 3) {
    tr.dataset.podium = ["or", "argent", "bronze"][team.pos - 1];
  } else {
    tr.removeAttribute("data-podium");
  }

  const precedente = positionsPrecedentes.get(team.name);
  if (precedente === undefined || precedente === team.pos) {
    tr.removeAttribute("data-mouvement");
  } else {
    tr.dataset.mouvement = precedente > team.pos ? "monte" : "descend";
  }

  return tr;
}

function render() {
  const gauche = document.getElementById("corps-gauche");
  const droite = document.getElementById("corps-droite");
  const page = classement.slice(debutPage, debutPage + PAR_PAGE);

  // FLIP en deux dimensions : une ligne peut descendre, monter,
  // mais aussi passer d'une colonne a l'autre
  const before = new Map();
  for (const tr of document.querySelectorAll(".colonnes tbody tr")) {
    before.set(tr, tr.getBoundingClientRect());
  }

  const lignes = page.map(getRow);
  gauche.replaceChildren(...lignes.slice(0, PAR_COLONNE));
  droite.replaceChildren(...lignes.slice(PAR_COLONNE));

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  for (const tr of lignes) {
    const avant = before.get(tr);
    if (avant === undefined) continue;
    const apres = tr.getBoundingClientRect();
    const dx = avant.left - apres.left;
    const dy = avant.top - apres.top;
    if (!dx && !dy) continue;
    tr.animate(
      [{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "none" }],
      { duration: MOVE_MS, easing: "cubic-bezier(0.4, 0, 0.2, 1)" }
    );
  }
}

// page suivante, puis retour en tete : l'ecran montre aussi les equipes
// qui ne tiennent pas dans les 40 premiers rangs
function pageSuivante() {
  if (classement.length <= PAR_PAGE) return;
  debutPage += PAR_PAGE;
  if (debutPage >= classement.length) debutPage = 0;
  render();
}

async function loadScoreboard() {
  if (fetchInFlight) return;
  fetchInFlight = true;

  const statusEl = document.getElementById("status");

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
    classement = payload.data;
    if (debutPage >= classement.length) debutPage = 0;
    render();
    // memorise apres l'affichage : les fleches comparent au classement precedent,
    // et pour toutes les equipes, pas seulement celles de la page visible
    for (const team of classement) positionsPrecedentes.set(team.name, team.pos);
  } catch (err) {
    statusEl.textContent = "Scoreboard indisponible.";
  } finally {
    fetchInFlight = false;
  }
}

loadScoreboard();
setInterval(loadScoreboard, REFRESH_MS);
setInterval(pageSuivante, PAGE_MS);
