const TIER_ORDER = ["top", "medium", "lean"];
const TIER_LABEL = { top: "Top Plays", medium: "Medium Confidence", lean: "Leans" };

function fmtPct(x) {
  if (x === null || x === undefined) return "—";
  return Math.round(x * 100) + "%";
}

function fmtEdge(x) {
  if (x === null || x === undefined) return "—";
  const sign = x > 0 ? "+" : "";
  return `${sign}${x.toFixed(1)}%`;
}

function fmtTimestamp(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric",
    hour: "numeric", minute: "2-digit"
  });
}

function confCell(confidence) {
  const pct = Math.max(0, Math.min(1, confidence ?? 0)) * 100;
  return `
    <span class="conf-bar">
      <span class="conf-bar__track"><span class="conf-bar__fill" style="width:${pct}%"></span></span>
      ${fmtPct(confidence)}
    </span>`;
}

function groupHeaderRow(label, count) {
  return `<tr class="group-row"><td colspan="5">${label} <span class="group-row__count">${count}</span></td></tr>`;
}

function pickRow(row, firstColKey) {
  const edgeClass = (row.edge ?? 0) >= 0 ? "edge-pos" : "edge-neg";
  return `
    <tr>
      <td>${row[firstColKey] ?? "—"}</td>
      <td>${row.market ?? "—"}</td>
      <td class="pick-cell">${row.pick ?? "—"}</td>
      <td class="num">${confCell(row.confidence)}</td>
      <td class="num ${edgeClass}">${fmtEdge(row.edge)}</td>
    </tr>`;
}

function renderBettingModel(rows) {
  const tbody = document.getElementById("rows-betting_model");
  if (!rows.length) { tbody.innerHTML = ""; return false; }

  const byTier = {};
  rows.forEach(r => {
    const t = TIER_ORDER.includes(r.tier) ? r.tier : "lean";
    (byTier[t] ||= []).push(r);
  });

  let html = "";
  TIER_ORDER.forEach(tier => {
    const group = byTier[tier];
    if (!group || !group.length) return;
    html += groupHeaderRow(TIER_LABEL[tier], group.length);
    html += group.map(r => pickRow(r, "matchup")).join("");
  });
  tbody.innerHTML = html;
  return true;
}

function renderPlayerProps(picks) {
  const tbody = document.getElementById("rows-player_props");
  if (!picks.length) { tbody.innerHTML = ""; return false; }

  const bySport = {};
  picks.forEach(r => {
    const s = r.sport || "Other";
    (bySport[s] ||= []).push(r);
  });

  let html = "";
  Object.keys(bySport).sort().forEach(sport => {
    const group = bySport[sport];
    html += groupHeaderRow(sport, group.length);
    html += group.map(r => pickRow(r, "player")).join("");
  });
  tbody.innerHTML = html;
  return true;
}

function parlayCard(parlay) {
  const legs = parlay.selections?.length ?? parlay.legs ?? 0;
  const selections = (parlay.selections || [])
    .map(s => `<li>${s}</li>`)
    .join("");
  return `
    <div class="parlay">
      <div class="parlay__head">
        <span class="parlay__legs">${legs}-Leg Parlay</span>
        ${parlay.odds ? `<span class="parlay__odds">${parlay.odds}</span>` : ""}
      </div>
      <ul class="parlay__legs-list">${selections}</ul>
    </div>`;
}

function renderParlays(parlays) {
  const wrap = document.getElementById("parlays");
  if (!parlays || !parlays.length) { wrap.innerHTML = ""; wrap.hidden = true; return; }
  wrap.hidden = false;
  wrap.innerHTML = `<h2 class="section-label">Parlays</h2>` + parlays.map(parlayCard).join("");
}

function fmtUnits(u) {
  if (u === null || u === undefined) return null;
  const sign = u > 0 ? "+" : "";
  return `${sign}${u.toFixed(1)}u`;
}

function resultClass(result) {
  return result === "win" ? "result-win" : result === "loss" ? "result-loss" : "result-push";
}

function statCard(label, wl) {
  const record = `${wl.wins}-${wl.losses}${wl.pushes ? "-" + wl.pushes : ""}`;
  const units = fmtUnits(wl.units);
  return `
    <div class="stat-card">
      <div class="stat-card__label">${label}</div>
      <div class="stat-card__record">${record}</div>
      ${units !== null ? `<div class="stat-card__units">${units}</div>` : ""}
    </div>`;
}

function pickResultRow(label, market, pick, result) {
  return `<tr><td>${label}</td><td>${market ?? "—"}</td><td>${pick ?? "—"}</td><td class="${resultClass(result)}">${(result || "—").toUpperCase()}</td></tr>`;
}

function dayCard(day, isFirst) {
  const bm = day.betting_model || { wins: 0, losses: 0, pushes: 0, picks: [] };
  const pp = day.player_props || { wins: 0, losses: 0, pushes: 0, picks: [] };
  const parlays = day.parlays || [];

  const bmRows = (bm.picks || []).map(p => pickResultRow(p.matchup, p.market, p.pick, p.result)).join("");
  const ppRows = (pp.picks || []).map(p => pickResultRow(p.player, p.market, p.pick, p.result)).join("");
  const parlayRows = parlays.map(p => pickResultRow(`${p.legs}-Leg Parlay`, "", p.odds, p.result)).join("");

  return `
    <details class="record-day" ${isFirst ? "open" : ""}>
      <summary>
        <span class="record-day__date">${day.date}</span>
        <span class="record-day__summary">
          <span>Betting ${bm.wins}-${bm.losses}${bm.pushes ? "-" + bm.pushes : ""}</span>
          <span>Props ${pp.wins}-${pp.losses}${pp.pushes ? "-" + pp.pushes : ""}</span>
        </span>
      </summary>
      <div class="record-day__body">
        ${bmRows ? `<div class="record-day__group-label">Betting Model</div><table class="record-table">${bmRows}</table>` : ""}
        ${ppRows ? `<div class="record-day__group-label">Player Props</div><table class="record-table">${ppRows}</table>` : ""}
        ${parlayRows ? `<div class="record-day__group-label">Parlays</div><table class="record-table">${parlayRows}</table>` : ""}
      </div>
    </details>`;
}

function renderTrackRecord(record) {
  const days = (record?.days || []).slice().sort((a, b) => b.date.localeCompare(a.date));
  const statRow = document.getElementById("stat-row");
  const log = document.getElementById("record-log");
  const empty = document.getElementById("record-empty");

  if (!days.length) {
    statRow.innerHTML = "";
    log.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  const totals = { betting_model: { wins: 0, losses: 0, pushes: 0, units: 0 }, player_props: { wins: 0, losses: 0, pushes: 0, units: 0 }, parlays: { wins: 0, losses: 0, pushes: 0 } };
  days.forEach(d => {
    ["betting_model", "player_props"].forEach(key => {
      const src = d[key];
      if (!src) return;
      totals[key].wins += src.wins || 0;
      totals[key].losses += src.losses || 0;
      totals[key].pushes += src.pushes || 0;
      totals[key].units += src.units || 0;
    });
    (d.parlays || []).forEach(p => {
      if (p.result === "win") totals.parlays.wins++;
      else if (p.result === "loss") totals.parlays.losses++;
      else totals.parlays.pushes++;
    });
  });

  statRow.innerHTML =
    statCard("Betting Model", totals.betting_model) +
    statCard("Player Props", totals.player_props) +
    statCard("Parlays", totals.parlays);

  log.innerHTML = days.map((d, i) => dayCard(d, i === 0)).join("");
}

async function loadRecord() {
  try {
    const res = await fetch("record.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no record.json");
    renderTrackRecord(await res.json());
  } catch (err) {
    renderTrackRecord(null);
  }
}

async function load() {
  const emptyState = document.getElementById("empty-state");
  try {
    const res = await fetch("data.json", { cache: "no-store" });
    if (!res.ok) throw new Error("no data.json");
    const data = await res.json();

    document.getElementById("updated-at").textContent = fmtTimestamp(data.updated_at);

    const bettingRows = data.betting_model || [];
    const props = data.player_props || {};
    const propPicks = props.picks || (Array.isArray(props) ? props : []);
    const parlays = props.parlays || [];

    const hasBetting = renderBettingModel(bettingRows);
    const hasProps = renderPlayerProps(propPicks);
    renderParlays(parlays);

    emptyState.hidden = hasBetting || hasProps;
  } catch (err) {
    emptyState.hidden = false;
    console.error(err);
  }
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tabs__btn");
  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      buttons.forEach(b => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("is-active"));
      document.getElementById(`panel-${btn.dataset.target}`).classList.add("is-active");
    });
  });
}

setupTabs();
load();
loadRecord();
