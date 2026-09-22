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
