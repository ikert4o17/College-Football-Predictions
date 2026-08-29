const state = {
  rankings: [],
  games: [],
  performance: null,
  selectedPerformanceWeek: null,
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

function normalizeRankings(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.rankings)) return data.rankings;
  return [];
}

async function loadRankings() {
  const data = await loadJson("site_data/rankings_2026.json");
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.rankings)) return data.rankings;
  if (Array.isArray(data?.parts)) {
    const pieces = await Promise.all(data.parts.map((path) => loadJson(path)));
    return pieces.flatMap(normalizeRankings);
  }
  return [];
}

function displayWeek(game) {
  if (game?.season === 2026 && game?.start_date) {
    const date = new Date(game.start_date);
    if (!Number.isNaN(date.getTime()) && date.getUTCMonth() === 7) return 0;
  }
  return game?.week ?? "—";
}

function renderSummary() {
  byId("teamCount").textContent = state.rankings.length || "—";
  byId("gameCount").textContent = state.games.length || "—";
  const weeks = new Set(state.games.map(displayWeek).filter((w) => w !== null && w !== undefined));
  byId("weekCount").textContent = weeks.size || "—";

  const hasInseason = state.rankings.some((r) => Number(r.games_inseason || 0) > 0);
  byId("modelStatus").textContent = hasInseason
    ? "2026 in-season ratings loaded"
    : (state.rankings.length ? "2026 Balanced Light preseason ratings loaded" : "Site ready • awaiting production JSON");
}

function renderWeekOptions() {
  const select = byId("weekSelect");
  const weeks = [...new Set(state.games.map(displayWeek).filter((w) => w !== null && w !== undefined))]
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
    ? new Date(game.start_date).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : "TBD";

  return `
    <article class="game-card panel">
      <div class="game-meta">
        <span>Week ${escapeHtml(displayWeek(game))} • ${escapeHtml(date)}</span>
        <span>${game.provisional ? "PROVISIONAL" : "PRODUCTION"}</span>
      </div>
      <div class="matchup">
        <div class="team away"><div class="team-name">${escapeHtml(game.away_team)}</div><div class="team-rating">Rating ${fmt(game.away_rating, 1)}</div></div>
        <div class="vs">AT</div>
        <div class="team home"><div class="team-name">${escapeHtml(game.home_team)}</div><div class="team-rating">Rating ${fmt(game.home_rating, 1)}</div></div>
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
    return (!query || matchup.includes(query)) && (week === "all" || String(displayWeek(game)) === week);
  });
  byId("gamesGrid").innerHTML = filtered.map(gameCard).join("");
  byId("gamesEmpty").classList.toggle("hidden", filtered.length > 0);
}

function renderRankings() {
  const query = byId("rankingSearch").value.trim().toLowerCase();
  const rows = state.rankings
    .filter((row) => !query || String(row.team || "").toLowerCase().includes(query))
    .sort((a, b) => Number(a.rank ?? 9999) - Number(b.rank ?? 9999));

  byId("rankingsBody").innerHTML = rows.map((row) => {
    const seasonAdj = row.inseason_adjustment ?? row.preseason_v4_adjustment ?? 0;
    return `
    <tr>
      <td>${escapeHtml(row.rank ?? "—")}</td>
      <td><strong>${escapeHtml(row.team)}</strong></td>
      <td>${fmt(row.power_rating, 2)}</td>
      <td>${Number(seasonAdj) > 0 ? "+" : ""}${fmt(seasonAdj, 2)}</td>
      <td>${escapeHtml(row.games_inseason ?? 0)}</td>
      <td>${fmt((Number(row.returning_production || 0) * 100), 0)}%</td>
      <td>${Number(row.transfer_talent || 0) > 0 ? "+" : ""}${fmt(row.transfer_talent, 0)}</td>
    </tr>`;
  }).join("");
}

function resultCard(game) {
  const projectedWinner = game.projected_winner || "—";
  const actualWinner = game.actual_winner || "—";
  const resultClass = game.winner_correct ? "result-win" : "result-loss";
  const resultLabel = game.winner_correct ? "WIN" : "LOSS";
  const projectedScore = `${fmt(game.projected_away_score, 1)}–${fmt(game.projected_home_score, 1)}`;
  const actualScore = `${fmt(game.actual_away_score, 0)}–${fmt(game.actual_home_score, 0)}`;
  const date = game.start_date
    ? new Date(game.start_date).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : "TBD";

  return `
    <article class="result-card panel ${resultClass}">
      <div class="result-card-top">
        <div>
          <span class="result-badge ${resultClass}">${resultLabel}</span>
          <span class="result-date">${escapeHtml(date)}</span>
        </div>
        <span class="result-model">${escapeHtml(game.model_version || "")}</span>
      </div>
      <h4>${escapeHtml(game.away_team)} at ${escapeHtml(game.home_team)}</h4>
      <div class="result-grid">
        <div><span>Projected winner</span><strong>${escapeHtml(projectedWinner)}</strong></div>
        <div><span>Actual winner</span><strong>${escapeHtml(actualWinner)}</strong></div>
        <div><span>Projected score</span><strong>${projectedScore}</strong></div>
        <div><span>Actual score</span><strong>${actualScore}</strong></div>
        <div><span>Margin error</span><strong>${fmt(game.margin_error, 2)}</strong></div>
        <div><span>Total error</span><strong>${fmt(game.total_error, 2)}</strong></div>
      </div>
    </article>`;
}

function renderPerformanceDetails() {
  const details = byId("performanceDetails");
  const title = byId("performanceDetailsTitle");
  const summary = byId("performanceDetailsSummary");
  const gamesWrap = byId("performanceGames");
  const week = state.selectedPerformanceWeek;

  if (week === null) {
    details.classList.add("hidden");
    return;
  }

  const allGames = Array.isArray(state.performance?.games) ? state.performance.games : [];
  const games = allGames.filter((game) => String(game.week) === String(week));
  const wins = games.filter((game) => game.winner_correct === true).length;
  const losses = games.filter((game) => game.winner_correct === false).length;

  title.textContent = `Week ${week} results`;
  summary.textContent = `${wins}-${losses} straight-up • ${games.length} graded game${games.length === 1 ? "" : "s"}`;
  gamesWrap.innerHTML = games.map(resultCard).join("");
  details.classList.remove("hidden");
  details.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function renderPerformance() {
  const cumulative = state.performance?.cumulative || {};
  const games = Number(cumulative.games || 0);
  byId("perfGames").textContent = games || "—";
  byId("perfWinner").textContent = games && Number.isFinite(Number(cumulative.winner_accuracy))
    ? `${(Number(cumulative.winner_accuracy) * 100).toFixed(1)}%`
    : "—";
  byId("perfMargin").textContent = games ? fmt(cumulative.margin_mae, 2) : "—";
  byId("perfTotal").textContent = games ? fmt(cumulative.total_mae, 2) : "—";

  const weekly = state.performance?.by_week || {};
  const rows = Object.entries(weekly).sort((a, b) => Number(a[0]) - Number(b[0]));
  byId("performanceBody").innerHTML = rows.map(([week, row]) => `
    <tr class="performance-row" data-week="${escapeHtml(week)}" tabindex="0" role="button" aria-label="View Week ${escapeHtml(week)} results">
      <td><strong>Week ${escapeHtml(week)}</strong></td>
      <td>${escapeHtml(row.games ?? 0)}</td>
      <td>${Number.isFinite(Number(row.winner_accuracy)) ? `${(Number(row.winner_accuracy) * 100).toFixed(1)}%` : "—"}</td>
      <td>${fmt(row.margin_mae, 2)}</td>
      <td>${fmt(row.total_mae, 2)}</td>
      <td>${fmt(row.score_mae, 2)}</td>
      <td><button class="details-button" type="button" data-week="${escapeHtml(week)}">View results</button></td>
    </tr>`).join("");
  byId("performanceEmpty").classList.toggle("hidden", rows.length > 0);

  document.querySelectorAll(".performance-row").forEach((row) => {
    const openWeek = () => {
      state.selectedPerformanceWeek = row.dataset.week;
      renderPerformanceDetails();
    };
    row.addEventListener("click", openWeek);
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openWeek();
      }
    });
  });
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
  try { state.rankings = await loadRankings(); }
  catch (error) { console.warn("2026 production rankings unavailable", error); state.rankings = []; }
  try { state.games = normalizeGames(await loadJson("site_data/game_predictions_2026.json")); }
  catch (error) { console.info("2026 production predictions unavailable", error); state.games = []; }
  try { state.performance = await loadJson("site_data/model_performance_2026.json"); }
  catch (error) { console.info("2026 performance data unavailable", error); state.performance = null; }

  renderSummary();
  renderWeekOptions();
  renderGames();
  renderRankings();
  renderPerformance();

  byId("weekSelect").addEventListener("change", renderGames);
  byId("gameSearch").addEventListener("input", renderGames);
  byId("rankingSearch").addEventListener("input", renderRankings);
  byId("closePerformanceDetails").addEventListener("click", () => {
    state.selectedPerformanceWeek = null;
    renderPerformanceDetails();
  });
}

init();
