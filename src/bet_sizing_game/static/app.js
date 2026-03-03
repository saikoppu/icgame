const joinCard = document.getElementById("joinCard");
const gameView = document.getElementById("gameView");
const joinForm = document.getElementById("joinForm");
const nameInput = document.getElementById("nameInput");
const joinError = document.getElementById("joinError");

const bankrollValue = document.getElementById("bankrollValue");
const pnlValue = document.getElementById("pnlValue");
const rankValue = document.getElementById("rankValue");
const playerCountValue = document.getElementById("playerCountValue");
const phaseTitle = document.getElementById("phaseTitle");
const timerPill = document.getElementById("timerPill");
const eventTitle = document.getElementById("eventTitle");
const eventDescription = document.getElementById("eventDescription");
const eventMeta = document.getElementById("eventMeta");
const betForm = document.getElementById("betForm");
const optionsWrap = document.getElementById("optionsWrap");
const amountInput = document.getElementById("amountInput");
const betStatus = document.getElementById("betStatus");
const leaderboardBody = document.getElementById("leaderboardBody");
const resultList = document.getElementById("resultList");
const podiumPanel = document.getElementById("podiumPanel");
const podiumCards = document.getElementById("podiumCards");

const rulesList = document.getElementById("rulesList");
const rulesEventsBody = document.getElementById("rulesEventsBody");

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanes = document.querySelectorAll(".tab-pane");

const adminKeyInput = document.getElementById("adminKeyInput");
const adminConnectBtn = document.getElementById("adminConnectBtn");
const adminStatus = document.getElementById("adminStatus");
const adminControls = document.getElementById("adminControls");
const adminStartBtn = document.getElementById("adminStartBtn");
const adminAdvanceBtn = document.getElementById("adminAdvanceBtn");
const adminPauseBtn = document.getElementById("adminPauseBtn");
const adminResumeBtn = document.getElementById("adminResumeBtn");
const adminRestartBtn = document.getElementById("adminRestartBtn");
const adminClearPlayers = document.getElementById("adminClearPlayers");
const adminSeedInput = document.getElementById("adminSeedInput");
const adminDownloadBtn = document.getElementById("adminDownloadBtn");
const adminSettingsForm = document.getElementById("adminSettingsForm");
const adminLobbySeconds = document.getElementById("adminLobbySeconds");
const adminStartingBankroll = document.getElementById("adminStartingBankroll");
const adminRoundStipend = document.getElementById("adminRoundStipend");
const adminUniformEventSeconds = document.getElementById("adminUniformEventSeconds");
const adminEventForm = document.getElementById("adminEventForm");
const adminEventSelect = document.getElementById("adminEventSelect");
const adminEventTitle = document.getElementById("adminEventTitle");
const adminEventDescription = document.getElementById("adminEventDescription");
const adminYesLabel = document.getElementById("adminYesLabel");
const adminNoLabel = document.getElementById("adminNoLabel");
const adminYesProbability = document.getElementById("adminYesProbability");
const adminEventSeconds = document.getElementById("adminEventSeconds");
const adminReplaceEventsJson = document.getElementById("adminReplaceEventsJson");
const adminReplaceEventsBtn = document.getElementById("adminReplaceEventsBtn");
const adminLeaderboardBody = document.getElementById("adminLeaderboardBody");
const adminResultsBody = document.getElementById("adminResultsBody");

const appState = {
  token: null,
  ws: null,
  latest: null,
  publicConfig: null,
  admin: {
    key: null,
    state: null,
    poller: null,
  },
};

function toMaybeNumber(rawValue) {
  const value = String(rawValue ?? "").trim();
  if (!value) {
    return null;
  }
  const asNum = Number(value);
  if (!Number.isFinite(asNum)) {
    return null;
  }
  return asNum;
}

function formatMoney(value) {
  const num = Number(value || 0);
  const sign = num >= 0 ? "" : "-";
  return `${sign}$${Math.abs(num).toFixed(2)}`;
}

function updateMetricValue(node, value, isPnl = false) {
  node.textContent = value;
  if (isPnl) {
    node.classList.toggle("pnl-up", !String(value).startsWith("-"));
    node.classList.toggle("pnl-down", String(value).startsWith("-"));
  }
}

function clearElement(node) {
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function setActiveTab(tabId) {
  for (const btn of tabButtons) {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  }
  for (const pane of tabPanes) {
    pane.classList.toggle("hidden", pane.id !== tabId);
  }
}

function on(el, eventName, handler) {
  if (el) {
    el.addEventListener(eventName, handler);
  }
}

function resetSession() {
  appState.token = null;
  if (appState.ws) {
    appState.ws.close();
    appState.ws = null;
  }
  localStorage.removeItem("bet-game-token");
  joinCard.classList.remove("hidden");
  gameView.classList.add("hidden");
}

function setAdminStatus(text, isError = false) {
  adminStatus.textContent = text;
  adminStatus.className = isError ? "error" : "info-line";
}

function renderLeaderboard(rows) {
  clearElement(leaderboardBody);
  for (const row of rows || []) {
    const tr = document.createElement("tr");
    const rankTd = document.createElement("td");
    rankTd.textContent = row.rank;
    const nameTd = document.createElement("td");
    nameTd.textContent = row.name;
    const pnlTd = document.createElement("td");
    pnlTd.textContent = formatMoney(row.pnl);
    pnlTd.className = Number(row.pnl) >= 0 ? "pnl-up" : "pnl-down";
    const bankTd = document.createElement("td");
    bankTd.textContent = formatMoney(row.bankroll);

    tr.append(rankTd, nameTd, pnlTd, bankTd);
    leaderboardBody.appendChild(tr);
  }
}

function renderResults(results) {
  clearElement(resultList);
  const reversed = [...(results || [])].reverse();
  if (!reversed.length) {
    const li = document.createElement("li");
    li.textContent = "No resolved bets yet.";
    resultList.appendChild(li);
    return;
  }

  for (const row of reversed) {
    const li = document.createElement("li");
    const delta = Number(row.pnl_delta || 0);
    li.textContent = `Event ${row.event_id} (${row.title}): ${delta >= 0 ? "+" : ""}${formatMoney(delta)} | Bankroll ${formatMoney(
      row.bankroll_after,
    )}`;
    li.className = delta >= 0 ? "pnl-up" : "pnl-down";
    resultList.appendChild(li);
  }
}

function renderPodium(podiumRows) {
  clearElement(podiumCards);
  for (const row of podiumRows || []) {
    const card = document.createElement("div");
    card.className = "podium-card";

    const h4 = document.createElement("h4");
    h4.textContent = `#${row.rank}`;
    const p1 = document.createElement("p");
    p1.textContent = row.name;
    const p2 = document.createElement("p");
    p2.textContent = `PnL ${formatMoney(row.pnl)}`;
    p2.className = Number(row.pnl) >= 0 ? "pnl-up" : "pnl-down";

    card.append(h4, p1, p2);
    podiumCards.appendChild(card);
  }
}

function renderEventOptions(eventData, currentBet) {
  clearElement(optionsWrap);

  for (const option of eventData.options || []) {
    const label = document.createElement("label");
    label.className = "option-card";

    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "betOption";
    radio.value = option.key;

    if (currentBet && currentBet.option_key === option.key) {
      radio.checked = true;
    }

    const wrapper = document.createElement("div");
    const top = document.createElement("strong");
    top.textContent = `${option.label} (x${option.payout_multiplier.toFixed(2)})`;
    const bottom = document.createElement("small");
    bottom.textContent = `Probability ${Math.round(option.probability * 10000) / 100}%`;

    wrapper.append(top, bottom);
    label.append(radio, wrapper);
    optionsWrap.appendChild(label);
  }
}

function renderMetaChips(state) {
  clearElement(eventMeta);

  const chips = [];
  chips.push(`Round ${state.event_index}/${state.total_events}`);
  chips.push(`Resolved ${state.resolved_events.length}/${state.total_events}`);
  chips.push(state.paused ? "Clock Paused" : "Clock Running");

  for (const text of chips) {
    const chip = document.createElement("span");
    chip.className = "event-chip";
    chip.textContent = text;
    eventMeta.appendChild(chip);
  }
}

function renderRules(rules, events) {
  clearElement(rulesList);
  clearElement(rulesEventsBody);

  for (const rule of rules || []) {
    const li = document.createElement("li");
    li.textContent = rule;
    rulesList.appendChild(li);
  }

  for (const event of events || []) {
    const yesOption = (event.options || []).find((option) => option.key === "yes");
    const tr = document.createElement("tr");
    const idTd = document.createElement("td");
    idTd.textContent = event.event_id;
    const titleTd = document.createElement("td");
    titleTd.textContent = event.title;
    const probTd = document.createElement("td");
    probTd.textContent = yesOption ? `${(yesOption.probability * 100).toFixed(3)}%` : "-";
    const timerTd = document.createElement("td");
    timerTd.textContent = `${event.bet_window_seconds}s`;
    tr.append(idTd, titleTd, probTd, timerTd);
    rulesEventsBody.appendChild(tr);
  }
}

function renderState(state) {
  appState.latest = state;

  const you = state.you;
  if (you) {
    updateMetricValue(bankrollValue, formatMoney(you.bankroll));
    updateMetricValue(pnlValue, formatMoney(you.pnl), true);
    rankValue.textContent = you.rank ? `#${you.rank}` : "-";
    renderResults(you.results);

    if (you.current_bet) {
      let optionLabel = you.current_bet.option_key.toUpperCase();
      if (state.current_event && Array.isArray(state.current_event.options)) {
        const match = state.current_event.options.find((option) => option.key === you.current_bet.option_key);
        if (match) {
          optionLabel = match.label;
        }
      }
      betStatus.textContent = `Current bet: ${you.current_bet.amount} on ${optionLabel}`;
      betStatus.className = "info-line";
      amountInput.value = String(you.current_bet.amount);
    } else {
      betStatus.textContent = "";
      betStatus.className = "info-line";
    }
  }

  playerCountValue.textContent = state.player_count;
  renderLeaderboard(state.leaderboard);
  renderMetaChips(state);

  if (state.rules && appState.publicConfig?.events) {
    renderRules(state.rules, appState.publicConfig.events);
  }

  if (state.phase === "lobby") {
    phaseTitle.textContent = "Lobby";
    timerPill.textContent = `${state.lobby_seconds_remaining}s`;
    eventTitle.textContent = "Waiting for the game to start";
    eventDescription.textContent =
      "All outcomes are randomized by the server. No automatic bankroll top-ups happen between events.";
    betForm.classList.add("hidden");
    podiumPanel.classList.add("hidden");
    return;
  }

  if (state.phase === "running" && state.current_event) {
    const eventData = state.current_event;
    phaseTitle.textContent = "Live Round";
    timerPill.textContent = `${eventData.seconds_remaining}s`;
    eventTitle.textContent = `Event ${eventData.event_id}: ${eventData.title}`;
    eventDescription.textContent = eventData.description;
    betForm.classList.remove("hidden");
    podiumPanel.classList.add("hidden");
    renderEventOptions(eventData, you ? you.current_bet : null);
    return;
  }

  if (state.phase === "finished") {
    phaseTitle.textContent = "Finished";
    timerPill.textContent = "0s";
    eventTitle.textContent = "Competition complete";
    eventDescription.textContent = "Final standings are locked. Top 10 shown on leaderboard and top 3 on podium.";
    betForm.classList.add("hidden");
    podiumPanel.classList.remove("hidden");
    renderPodium(state.podium);
  }
}

async function fetchPublicConfig() {
  try {
    const response = await fetch("/api/events");
    const payload = await response.json();
    appState.publicConfig = payload;
    renderRules(payload.rules || [], payload.events || []);

    if (!adminReplaceEventsJson.value && payload.events) {
      const seedTemplate = payload.events.map((event) => {
        const yesOption = event.options.find((option) => option.key === "yes");
        const noOption = event.options.find((option) => option.key === "no");
        return {
          title: event.title,
          description: event.description,
          yes_label: yesOption?.label || "YES",
          no_label: noOption?.label || "NO",
          yes_probability: yesOption?.probability || 0.5,
          bet_window_seconds: event.bet_window_seconds,
        };
      });
      adminReplaceEventsJson.value = JSON.stringify(seedTemplate, null, 2);
    }
  } catch {
    // Ignore on boot and retry on next state sync.
  }
}

async function join(name) {
  joinError.textContent = "";
  try {
    const response = await fetch("/api/join", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    const payload = await response.json();
    if (!response.ok || !payload.token) {
      throw new Error(payload.detail || payload.error || "Failed to join.");
    }

    appState.token = payload.token;
    localStorage.setItem("bet-game-token", payload.token);
    joinCard.classList.add("hidden");
    gameView.classList.remove("hidden");
    renderState(payload.state);
    connectSocket();
  } catch (err) {
    joinError.textContent = err.message || "Could not join.";
  }
}

function connectSocket() {
  if (!appState.token) {
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${window.location.host}/ws/${appState.token}`);
  appState.ws = ws;

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "state") {
        renderState(msg.payload);
      } else if (msg.type === "error") {
        betStatus.textContent = msg.message || "Action failed.";
        betStatus.className = "error";
      }
    } catch {
      // Ignore malformed frame.
    }
  };

  ws.onclose = () => {
    if (appState.token) {
      setTimeout(syncState, 400);
      setTimeout(connectSocket, 1200);
    }
  };
}

async function syncState() {
  if (!appState.token) {
    return;
  }
  try {
    const response = await fetch(`/api/state/${appState.token}`);
    const payload = await response.json();
    if (payload.error === "unknown session") {
      resetSession();
      return;
    }
    if (payload.state) {
      renderState(payload.state);
    }
  } catch {
    // Ignore polling errors.
  }
}

async function adminFetch(path, options = {}) {
  if (!appState.admin.key) {
    throw new Error("Admin key required.");
  }

  const headers = {
    ...(options.headers || {}),
    "x-admin-key": appState.admin.key,
  };

  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `Admin request failed (${response.status})`);
  }

  return payload;
}

function renderAdminLeaderboard(rows) {
  clearElement(adminLeaderboardBody);
  for (const row of rows || []) {
    const tr = document.createElement("tr");
    const rank = document.createElement("td");
    rank.textContent = row.rank;
    const name = document.createElement("td");
    name.textContent = row.name;
    const pnl = document.createElement("td");
    pnl.textContent = formatMoney(row.pnl);
    pnl.className = Number(row.pnl) >= 0 ? "pnl-up" : "pnl-down";
    const bankroll = document.createElement("td");
    bankroll.textContent = formatMoney(row.bankroll);
    const bet = document.createElement("td");
    bet.textContent = row.current_bet ? `${row.current_bet.amount} on ${row.current_bet.option_key}` : "-";
    tr.append(rank, name, pnl, bankroll, bet);
    adminLeaderboardBody.appendChild(tr);
  }
}

function renderAdminResults(rows) {
  clearElement(adminResultsBody);
  for (const row of rows || []) {
    const tr = document.createElement("tr");
    const id = document.createElement("td");
    id.textContent = row.event_id;
    const title = document.createElement("td");
    title.textContent = row.title;
    const status = document.createElement("td");
    status.textContent = row.resolved ? "Resolved" : "Open";
    const outcome = document.createElement("td");
    outcome.textContent = row.outcome ? row.outcome.outcome_label : "-";
    const bets = document.createElement("td");
    bets.textContent = row.bets_placed;
    const wagered = document.createElement("td");
    wagered.textContent = formatMoney(row.total_wagered);
    tr.append(id, title, status, outcome, bets, wagered);
    adminResultsBody.appendChild(tr);
  }
}

function renderEventEditorOptions(events) {
  const selectedValue = adminEventSelect.value;
  clearElement(adminEventSelect);

  for (const event of events || []) {
    const option = document.createElement("option");
    option.value = String(event.event_id);
    option.textContent = `Event ${event.event_id}: ${event.title}`;
    adminEventSelect.appendChild(option);
  }

  if (selectedValue) {
    adminEventSelect.value = selectedValue;
  }

  if (!adminEventSelect.value && adminEventSelect.options.length) {
    adminEventSelect.selectedIndex = 0;
  }

  fillEventEditorFromSelection(events);
}

function fillEventEditorFromSelection(events) {
  const selectedId = Number(adminEventSelect.value || 0);
  const event = (events || []).find((row) => row.event_id === selectedId);
  if (!event) {
    return;
  }

  const yesOption = (event.options || []).find((option) => option.key === "yes");
  const noOption = (event.options || []).find((option) => option.key === "no");

  adminEventTitle.value = event.title;
  adminEventDescription.value = event.description;
  adminYesLabel.value = yesOption?.label || "YES";
  adminNoLabel.value = noOption?.label || "NO";
  adminYesProbability.value = yesOption?.probability ?? 0.5;
  adminEventSeconds.value = event.bet_window_seconds;
}

function renderAdminState(state) {
  appState.admin.state = state;
  adminControls.classList.remove("hidden");

  setAdminStatus(
    `Connected. Phase=${state.phase} | Players=${state.player_count} | Event ${state.event_index}/${state.total_events} | ${state.paused ? "PAUSED" : "RUNNING"}`,
  );

  adminLobbySeconds.value = state.lobby_seconds;
  adminStartingBankroll.value = state.starting_bankroll;
  adminRoundStipend.value = state.round_stipend;

  renderAdminLeaderboard(state.leaderboard);
  renderAdminResults(state.event_results);
  renderEventEditorOptions(state.events);
  renderRules(state.rules || [], state.events || []);
}

async function refreshAdminState() {
  const payload = await adminFetch("/api/admin/state");
  renderAdminState(payload.state);
}

async function adminAction(path, method = "POST", bodyObj = null) {
  const payload = await adminFetch(path, {
    method,
    body: bodyObj ? JSON.stringify(bodyObj) : undefined,
  });
  if (payload.state) {
    renderAdminState(payload.state);
  } else {
    await refreshAdminState();
  }
  setAdminStatus("Action applied.");
}

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

tabButtons.forEach((btn) => {
  on(btn, "click", () => setActiveTab(btn.dataset.tab));
});

on(joinForm, "submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim();
  if (!name) {
    joinError.textContent = "Name is required.";
    return;
  }
  join(name);
});

on(betForm, "submit", (event) => {
  event.preventDefault();
  if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
    betStatus.textContent = "Connection is not ready yet.";
    betStatus.className = "error";
    return;
  }

  const selected = document.querySelector('input[name="betOption"]:checked');
  if (!selected) {
    betStatus.textContent = "Pick an option before placing the bet.";
    betStatus.className = "error";
    return;
  }

  const amount = Number(amountInput.value || 0);
  if (!Number.isFinite(amount) || amount <= 0) {
    betStatus.textContent = "Enter a valid positive amount.";
    betStatus.className = "error";
    return;
  }

  appState.ws.send(
    JSON.stringify({
      type: "place_bet",
      option: selected.value,
      amount: Math.floor(amount),
    }),
  );

  betStatus.textContent = "Bet submitted.";
  betStatus.className = "info-line";
});

on(adminConnectBtn, "click", async () => {
  const key = adminKeyInput.value.trim();
  if (!key) {
    setAdminStatus("Enter admin key.", true);
    return;
  }

  appState.admin.key = key;
  localStorage.setItem("bet-game-admin-key", key);

  try {
    await refreshAdminState();
    if (appState.admin.poller) {
      clearInterval(appState.admin.poller);
    }
    appState.admin.poller = setInterval(async () => {
      try {
        await refreshAdminState();
      } catch {
        // Keep polling; status updates on next success/failure action.
      }
    }, 3000);
  } catch (err) {
    adminControls.classList.add("hidden");
    setAdminStatus(err.message || "Admin auth failed.", true);
  }
});

on(adminStartBtn, "click", async () => {
  try {
    await adminAction("/api/admin/start");
  } catch (err) {
    setAdminStatus(err.message || "Failed to start.", true);
  }
});

on(adminAdvanceBtn, "click", async () => {
  try {
    await adminAction("/api/admin/advance");
  } catch (err) {
    setAdminStatus(err.message || "Failed to advance.", true);
  }
});

on(adminPauseBtn, "click", async () => {
  try {
    await adminAction("/api/admin/pause");
  } catch (err) {
    setAdminStatus(err.message || "Failed to pause.", true);
  }
});

on(adminResumeBtn, "click", async () => {
  try {
    await adminAction("/api/admin/resume");
  } catch (err) {
    setAdminStatus(err.message || "Failed to resume.", true);
  }
});

on(adminRestartBtn, "click", async () => {
  try {
    await adminAction("/api/admin/restart", "POST", {
      new_seed: toMaybeNumber(adminSeedInput.value),
      clear_players: adminClearPlayers.checked,
    });
  } catch (err) {
    setAdminStatus(err.message || "Failed to restart.", true);
  }
});

on(adminDownloadBtn, "click", () => {
  if (!appState.admin.state) {
    setAdminStatus("No admin state yet.", true);
    return;
  }
  downloadJson(`bet-game-admin-state-${Date.now()}.json`, appState.admin.state);
});

on(adminSettingsForm, "submit", async (event) => {
  event.preventDefault();
  const body = {};
  const lobbySeconds = toMaybeNumber(adminLobbySeconds.value);
  const startingBankroll = toMaybeNumber(adminStartingBankroll.value);
  const roundStipend = toMaybeNumber(adminRoundStipend.value);
  const uniformEventSeconds = toMaybeNumber(adminUniformEventSeconds.value);

  if (lobbySeconds !== null) {
    body.lobby_seconds = Math.floor(lobbySeconds);
  }
  if (startingBankroll !== null) {
    body.starting_bankroll = Math.floor(startingBankroll);
  }
  if (roundStipend !== null) {
    body.round_stipend = Math.floor(roundStipend);
  }
  if (uniformEventSeconds !== null) {
    body.uniform_event_seconds = Math.floor(uniformEventSeconds);
  }

  try {
    await adminAction("/api/admin/settings", "POST", body);
  } catch (err) {
    setAdminStatus(err.message || "Failed to save settings.", true);
  }
});

on(adminEventSelect, "change", () => {
  fillEventEditorFromSelection(appState.admin.state?.events || []);
});

on(adminEventForm, "submit", async (event) => {
  event.preventDefault();
  const eventId = Number(adminEventSelect.value);
  if (!eventId) {
    setAdminStatus("Select an event.", true);
    return;
  }

  const body = {
    title: adminEventTitle.value.trim(),
    description: adminEventDescription.value.trim(),
    yes_label: adminYesLabel.value.trim(),
    no_label: adminNoLabel.value.trim(),
    yes_probability: Number(adminYesProbability.value),
    bet_window_seconds: Number(adminEventSeconds.value),
  };

  try {
    await adminAction(`/api/admin/events/${eventId}`, "POST", body);
  } catch (err) {
    setAdminStatus(err.message || "Failed to update event.", true);
  }
});

on(adminReplaceEventsBtn, "click", async () => {
  try {
    const parsed = JSON.parse(adminReplaceEventsJson.value || "[]");
    if (!Array.isArray(parsed)) {
      throw new Error("JSON must be an array.");
    }
    await adminAction("/api/admin/events", "PUT", { events: parsed });
  } catch (err) {
    setAdminStatus(err.message || "Failed to replace events.", true);
  }
});

const storedToken = localStorage.getItem("bet-game-token");
if (storedToken) {
  appState.token = storedToken;
  joinCard.classList.add("hidden");
  gameView.classList.remove("hidden");
  syncState();
  connectSocket();
}

const storedAdminKey = localStorage.getItem("bet-game-admin-key");
if (storedAdminKey) {
  adminKeyInput.value = storedAdminKey;
}

setActiveTab("playTab");
fetchPublicConfig();
setInterval(fetchPublicConfig, 15000);
setInterval(syncState, 5000);
