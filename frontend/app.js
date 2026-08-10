const REFRESH_MS = 7000;
const MAX_TEAMS = 20;
const MOVE_MS = 700;

let fetchInFlight = false;
// une <tr> par equipe, reutilisee d'un refresh a l'autre : c'est ce qui rend
// l'animation de depassement possible (meme noeud DOM = meme element anime)
const rows = new Map();

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
  score.textContent = team.score;
  return tr;
}

function render(data) {
  const bodyEl = document.getElementById("scoreboard-body");

  // FLIP : on note ou chaque ligne etait, on reordonne, on rejoue l'ecart
  const before = new Map();
  for (const tr of bodyEl.children) before.set(tr, tr.getBoundingClientRect().top);

  bodyEl.replaceChildren(...data.slice(0, MAX_TEAMS).map(getRow));

  for (const tr of bodyEl.children) {
    const from = before.get(tr);
    if (from === undefined) continue;
    const delta = from - tr.getBoundingClientRect().top;
    if (!delta) continue;
    tr.animate(
      [{ transform: `translateY(${delta}px)` }, { transform: "none" }],
      { duration: MOVE_MS, easing: "cubic-bezier(0.4, 0, 0.2, 1)" }
    );
  }
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
    render(payload.data);
  } catch (err) {
    statusEl.textContent = "Scoreboard indisponible.";
  } finally {
    fetchInFlight = false;
  }
}

loadScoreboard();
setInterval(loadScoreboard, REFRESH_MS);
