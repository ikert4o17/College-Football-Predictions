const state = {
  rankings: [],
  games: [],
};

const byId = (id) => document.getElementById(id);

const fmt = (value, digits = 1) => {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "—";
};

const escapeHtml = (value = "") => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

function normalizeGames(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.predictions)) return data.predictions;
  if (Array.isArray(data?.games)) return data.games;
  return [];
}

function renderSummary() {
  byId("teamCount").textContent = state.rankings.length || "—";
  byId("gameCount").textContent = state.games.length || "—";
  const weeks = new Set(state.games.map((g) => g.week).filter((w) => w !== null && w !== undefined));
  byId("weekCount").textContent = weeks.size || "—";

  const hasGames = state.games.length > 0;
  byId("modelStatus").textContent = hasGames
    ? "2026 provisional model loaded"
    : "Site ready • awaiting prediction JSON";
}

function renderWeekOptions() {
  const select = byId("weekSelect");
  const weeks = [...new Set(state.games.map((g) => g.week).filter((w) => w !== null && w !== undefined))]
    .sort((a, b) => Number(a) - Number(b));

  select.innerHTML = '<option value="all">All weeks</option>' + weeks
    .map((week) => `<option value="${escapeHtml(week)}">Week ${escapeHtml(week)}</option>`)
    .join("");
}

function gameCard(game) {
  const winner = game.projected_winner || "Pick 'em";
  const margin = Number(game.projected_margin);
  const winnerText = Number.isFinite(margin) && game.projected_winner
    ? `${winner} by ${margin.toFixed(1)}`
    : winner;

  const date = game.start_date
    ? new Date(game.start_date).toLocaleString([], {
        month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
      })
    : "TBD";

  return `
    <article class="game-card panel">
      <div class="game-meta">
        <span>Week ${escapeHtml(game.week ?? "—")} • ${escapeHtml(date)}</span>
        <span class="${game.provisional ? "provisional" : ""}">${game.provisional ? "PROVISIONAL" : "FINAL"}</span>
      </div>
      <div class="matchup">
        <div class="team away">
          <div class="team-name">${escapeHtml(game.away_team)}</div>
          <div class="team-rating">Rating ${fmt(game.away_rating, 1)}</div>
        </div>
        <div class="vs">AT</div>
        <div class="team home">
          <div class="team-name">${escapeHtml(game.home_team)}</div>
          <div class="team-rating">Rating ${fmt(game.home_rating, 1)}</div>
        </div>
      </div>
      <div class="projection-bar">
        <div class="projection"><span>Projected winner</span><strong>${escapeHtml(winnerText)}</strong></div>
        <div class="projection"><span>Projected total</span><strong>${fmt(game.projected_total, 1)}</strong></div>
        <div class="projection"><span>Implied score</span><strong>${fmt(game.away_score ?? game.projected_away_score, 1)}–${fmt(game.home_score ?? game.projected_home_score, 1)}</strong></div>
      </div>
    </article>`;
}

function renderGames() {
  const query = byId("gameSearch").value.trim().toLowerCase();
  const week = byId("weekSelect").value;

  const filtered = state.games.filter((game) => {
    const matchup = `${game.away_team || ""} ${game.home_team || ""}`.toLowerCase();
    const matchesQuery = !query || matchup.includes(query);
    const matchesWeek = week === "all" || String(game.week) === week;
    return matchesQuery && matchesWeek;
  });

  byId("gamesGrid").innerHTML = filtered.map(gameCard).join("");
  byId("gamesEmpty").classList.toggle("hidden", filtered.length > 0);
}

function renderRankings() {
  const query = byId("rankingSearch").value.trim().toLowerCase();
  const rows = state.rankings
    .filter((row) => !query || String(row.team || "").toLowerCase().includes(query))
    .sort((a, b) => Number(a.rank_by_returning_snaps ?? 9999) - Number(b.rank_by_returning_snaps ?? 9999));

  byId("rankingsBody").innerHTML = rows.map((row) => `
    <tr>
      <td>${escapeHtml(row.rank_by_returning_snaps ?? "—")}</td>
      <td><strong>${escapeHtml(row.team)}</strong></td>
      <td>${Number(row.returning_snaps || 0).toLocaleString()}</td>
      <td>${escapeHtml(row.returning_snap_percent ?? "—")}%</td>
      <td>${escapeHtml(row.source || "—")}</td>
    </tr>`).join("");
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
      tab.classList.add("active");
      byId(`${tab.dataset.view}View`).classList.add("active");
    });
  });
}

async function init() {
  setupTabs();

  try {
    state.rankings = await loadJson("2026.json");
  } catch (error) {
    console.warn("Returning-production dataset unavailable", error);
    state.rankings = [];
  }

  try {
    const gameData = await loadJson("data/processed/provisional_game_predictions_2026.json");
    state.games = normalizeGames(gameData);
  } catch (error) {
    console.info("Prediction JSON not available yet; dashboard remains ready.", error);
    state.games = [];
  }

  renderSummary();
  renderWeekOptions();
  renderGames();
  renderRankings();

  byId("weekSelect").addEventListener("change", renderGames);
  byId("gameSearch").addEventListener("input", renderGames);
  byId("rankingSearch").addEventListener("input", renderRankings);
}

init();
