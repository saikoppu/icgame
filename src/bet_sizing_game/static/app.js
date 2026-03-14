const joinCard = document.getElementById("joinCard");
const gameView = document.getElementById("gameView");
const joinForm = document.getElementById("joinForm");
const nameInput = document.getElementById("nameInput");
const joinError = document.getElementById("joinError");

const bankrollValue = document.getElementById("bankrollValue");
const pnlValue = document.getElementById("pnlValue");
const phaseTitle = document.getElementById("phaseTitle");
const timerPill = document.getElementById("timerPill");
const startGameBtn = document.getElementById("startGameBtn");
const eventTitle = document.getElementById("eventTitle");
const eventDescription = document.getElementById("eventDescription");
const eventMeta = document.getElementById("eventMeta");
const betForm = document.getElementById("betForm");
const fermiForm = document.getElementById("fermiForm");
const oddsDisplayInput = document.getElementById("oddsDisplayInput");
const amountInput = document.getElementById("amountInput");
const doubleDownInput = document.getElementById("doubleDownInput");
const insuranceInput = document.getElementById("insuranceInput");
const volatilityInput = document.getElementById("volatilityInput");
const powerCardStatus = document.getElementById("powerCardStatus");
const fermiGuessInput = document.getElementById("fermiGuessInput");
const betStatus = document.getElementById("betStatus");
const resultList = document.getElementById("resultList");
const podiumPanel = document.getElementById("podiumPanel");
const podiumCards = document.getElementById("podiumCards");

const rulesContent = document.getElementById("rulesContent");

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
const adminStartingBankroll = document.getElementById("adminStartingBankroll");
const adminBustRebuy = document.getElementById("adminBustRebuy");
const adminRoundStipend = document.getElementById("adminRoundStipend");
const adminUniformEventSeconds = document.getElementById("adminUniformEventSeconds");
const adminUniformFermiSeconds = document.getElementById("adminUniformFermiSeconds");

const adminEventForm = document.getElementById("adminEventForm");
const adminEventSelect = document.getElementById("adminEventSelect");
const adminEventTitle = document.getElementById("adminEventTitle");
const adminEventDescription = document.getElementById("adminEventDescription");
const adminTrueProbability = document.getElementById("adminTrueProbability");
const adminOddsNumerator = document.getElementById("adminOddsNumerator");
const adminOddsDenominator = document.getElementById("adminOddsDenominator");
const adminEventSeconds = document.getElementById("adminEventSeconds");

const adminFermiForm = document.getElementById("adminFermiForm");
const adminFermiSelect = document.getElementById("adminFermiSelect");
const adminFermiPrompt = document.getElementById("adminFermiPrompt");
const adminFermiTruth = document.getElementById("adminFermiTruth");
const adminFermiUnit = document.getElementById("adminFermiUnit");
const adminFermiSeconds = document.getElementById("adminFermiSeconds");

const adminReplaceEventsJson = document.getElementById("adminReplaceEventsJson");
const adminReplaceEventsBtn = document.getElementById("adminReplaceEventsBtn");
const adminReplaceFermiJson = document.getElementById("adminReplaceFermiJson");
const adminReplaceFermiBtn = document.getElementById("adminReplaceFermiBtn");
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

const APP_VERSION = "20260314b";
const TOKEN_KEY = `bet-game-token-${APP_VERSION}`;
const ADMIN_KEY = `bet-game-admin-key-${APP_VERSION}`;

function on(el, eventName, handler) {
  if (el) {
    el.addEventListener(eventName, handler);
  }
}

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

function clearElement(node) {
  while (node && node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function updateMetricValue(node, value, isPnl = false) {
  if (!node) return;
  node.textContent = value;
  if (isPnl) {
    node.classList.toggle("pnl-up", !String(value).startsWith("-"));
    node.classList.toggle("pnl-down", String(value).startsWith("-"));
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

function resetSession() {
  appState.token = null;
  if (appState.ws) {
    appState.ws.close();
    appState.ws = null;
  }
  localStorage.removeItem(TOKEN_KEY);
  joinCard.classList.remove("hidden");
  gameView.classList.add("hidden");
}

function setAdminStatus(text, isError = false) {
  adminStatus.textContent = text;
  adminStatus.className = isError ? "error" : "info-line";
}

function renderLeaderboard(rows) {
  void rows;
}

function renderResults(results, fermiResults) {
  clearElement(resultList);

  const merged = [];
  for (const item of results || []) {
    merged.push({ type: "event", data: item });
  }
  for (const item of fermiResults || []) {
    merged.push({ type: "fermi", data: item });
  }

  const isFinished = appState.latest?.phase === "finished";
  const rows = isFinished ? merged : merged.slice(-10).reverse();

  if (!rows.length) {
    const li = document.createElement("li");
    li.textContent = "No resolved rounds yet.";
    resultList.appendChild(li);
    return;
  }

  for (const row of rows) {
    const li = document.createElement("li");
    if (row.type === "event") {
      const delta = Number(row.data.pnl_delta || 0);
      const outcome = row.data.outcome_hit ? "HIT" : "MISS";
      const powerFlags = [];
      if (row.data.double_down_used) powerFlags.push("DoubleDown");
      if (row.data.insurance_used) powerFlags.push("Insured");
      if (row.data.volatility_used) {
        const mult = row.data.volatility_multiplier ? `x${Number(row.data.volatility_multiplier).toFixed(2)}` : "x?";
        powerFlags.push(`Volatility ${mult}`);
      }
      const powerTag = powerFlags.length ? ` | ${powerFlags.join("+")}` : "";
      const carryTag = Number(row.data.volatility_carry_cost || 0) > 0
        ? ` | Carry ${formatMoney(row.data.volatility_carry_cost)}`
        : "";
      li.textContent = `Event ${row.data.event_id}: Bet ${formatMoney(row.data.bet_amount)}${powerTag} | ${outcome} | Delta ${
        delta >= 0 ? "+" : ""
      }${formatMoney(delta)}${carryTag} | Bankroll ${formatMoney(row.data.bankroll_after)}${row.data.rebuy_applied ? " | Bust reset to $500" : ""}`;
      li.className = delta >= 0 ? "pnl-up" : "pnl-down";
    } else {
      const boost = Number(row.data.boost_pct || 0) * 100;
      li.textContent = `Fermi ${row.data.question_id}: Guess ${
        row.data.guess === null || row.data.guess === undefined ? "-" : row.data.guess
      } | Boost ${boost.toFixed(1)}% | Bankroll ${formatMoney(row.data.bankroll_after)}`;
      li.className = boost > 0 ? "pnl-up" : "";
    }
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
    p2.textContent = `Final Bankroll ${formatMoney(row.bankroll)}`;

    card.append(h4, p1, p2);
    podiumCards.appendChild(card);
  }
}

function renderMetaChips(state) {
  clearElement(eventMeta);
  const chips = [];

  chips.push(state.paused ? "Clock Paused" : "Clock Running");

  if (state.phase === "events") {
    chips.push(`Event ${state.event_index}/${state.total_events}`);
    chips.push(`Resolved ${state.resolved_events.length}/${state.total_events}`);
  } else if (state.phase === "fermi") {
    chips.push(`Fermi ${state.fermi_index}/${state.total_fermi}`);
    chips.push(`Resolved ${state.resolved_fermi.length}/${state.total_fermi}`);
  }

  for (const text of chips) {
    const chip = document.createElement("span");
    chip.className = "event-chip";
    chip.textContent = text;
    eventMeta.appendChild(chip);
  }
}

function renderRules(rules) {
  if (!rulesContent) return;
  const list = Array.isArray(rules) ? rules : [];
  const items = list.map((rule) => `<li>${String(rule)}</li>`).join("");
  rulesContent.innerHTML = `
    <section class="rules-section">
      <h3>How It Works</h3>
      <p>
        This is a single-player betting game. You start with a bankroll and run through sequential probabilistic events.
        For each event, choose a stake and optionally use a powerup.
      </p>
    </section>
    <section class="rules-section">
      <h3>Powerups</h3>
      <ul>
        <li><strong>Double Down</strong>: doubles your stake and payout exposure on that round.</li>
        <li><strong>Insurance</strong>: pays a premium and refunds part of the stake if the round misses.</li>
        <li><strong>Volatility</strong>: applies a fixed payout multiplier (x1.50) when used.</li>
        <li><strong>Volatility Carry</strong>: if unused, the volatility card charges a fixed $100 per round.</li>
      </ul>
    </section>
    <section class="rules-section">
      <h3>Bankroll Rules</h3>
      <ul>
        <li>Bet sizing allows decimals and supports zero bet.</li>
        <li>If bankroll reaches $0, it auto-resets to the configured bust amount.</li>
        <li>Trade history shows every round result and powerup usage.</li>
      </ul>
    </section>
    <section class="rules-section">
      <h3>Game Details</h3>
      <ul>${items}</ul>
    </section>
  `;
}

function renderState(state) {
  appState.latest = state;

  const you = state.you;
  if (you) {
    updateMetricValue(bankrollValue, formatMoney(you.bankroll));
    updateMetricValue(pnlValue, formatMoney(you.pnl), true);
    renderResults(you.results, you.fermi_results);

    if (you.current_bet) {
      betStatus.textContent = `Current bet: ${formatMoney(you.current_bet.amount)} at posted odds`;
    } else if (state.phase === "events") {
      betStatus.textContent = "";
    }

    if (you.current_fermi_guess !== null && you.current_fermi_guess !== undefined && state.phase === "fermi") {
      betStatus.textContent = `Current Fermi guess: ${you.current_fermi_guess}`;
      fermiGuessInput.value = String(you.current_fermi_guess);
    }

    if (powerCardStatus) {
      const holdCost = Number(state.volatility_hold_cost || 0);
      const holdCostTag = holdCost > 0 ? ` | Carry ${formatMoney(holdCost)}/round` : "";
      powerCardStatus.textContent = `Cards: DD ${you.double_down_available} | INS ${you.insurance_available} | VOL ${you.volatility_available}${holdCostTag}`;
    }
    if (doubleDownInput) {
      doubleDownInput.disabled = !(you.double_down_available > 0);
      if (doubleDownInput.disabled) doubleDownInput.checked = false;
    }
    if (insuranceInput) {
      insuranceInput.disabled = !(you.insurance_available > 0);
      if (insuranceInput.disabled) insuranceInput.checked = false;
    }
    if (volatilityInput) {
      volatilityInput.disabled = !(you.volatility_available > 0);
      if (volatilityInput.disabled) volatilityInput.checked = false;
    }
  }

  renderLeaderboard(state.leaderboard);
  renderMetaChips(state);

  if (state.rules) {
    renderRules(state.rules);
  }

  if (state.phase === "lobby") {
    phaseTitle.textContent = "Lobby";
    timerPill.textContent = "Waiting";
    eventTitle.textContent = "Ready to Start";
    eventDescription.textContent = "Press Start Game when you're ready to begin the event sequence.";
    betForm.classList.add("hidden");
    fermiForm.classList.add("hidden");
    podiumPanel.classList.add("hidden");
    if (startGameBtn) {
      startGameBtn.classList.remove("hidden");
      startGameBtn.disabled = !you;
    }
    return;
  }

  if (state.phase === "events" && state.current_event) {
    const eventData = state.current_event;
    phaseTitle.textContent = "Betting Round";
    timerPill.textContent = `${eventData.seconds_remaining}s`;
    eventTitle.textContent = `Event ${eventData.event_id}: ${eventData.title}`;
    eventDescription.textContent = eventData.description;
    if (oddsDisplayInput) {
      oddsDisplayInput.value = eventData.odds_label || "-";
    }
    if (startGameBtn) {
      startGameBtn.classList.add("hidden");
      startGameBtn.disabled = true;
    }
    betForm.classList.remove("hidden");
    fermiForm.classList.add("hidden");
    podiumPanel.classList.add("hidden");
    return;
  }

  if (state.phase === "fermi" && state.current_fermi) {
    const q = state.current_fermi;
    phaseTitle.textContent = "Fermi Finals";
    timerPill.textContent = `${q.seconds_remaining}s`;
    eventTitle.textContent = `Fermi ${q.question_id}: ${q.prompt}`;
    eventDescription.textContent = `Only guesses above or equal to truth are valid for percentile boosts (${q.unit}).`;
    betForm.classList.add("hidden");
    fermiForm.classList.remove("hidden");
    podiumPanel.classList.add("hidden");
    if (startGameBtn) {
      startGameBtn.classList.add("hidden");
      startGameBtn.disabled = true;
    }
    return;
  }

  if (state.phase === "finished") {
    phaseTitle.textContent = "Finished";
    timerPill.textContent = "Done";
    eventTitle.textContent = "Competition complete";
    eventDescription.textContent = you
      ? `Final bankroll: ${formatMoney(you.bankroll)}. Full trade history is listed below.`
      : "Final standings are locked.";
    if (you) {
      betStatus.textContent = `Final bankroll: ${formatMoney(you.bankroll)}`;
      betStatus.className = "info-line";
    }
    betForm.classList.add("hidden");
    fermiForm.classList.add("hidden");
    podiumPanel.classList.remove("hidden");
    if (startGameBtn) {
      startGameBtn.classList.add("hidden");
      startGameBtn.disabled = true;
    }
    renderPodium(state.podium);
  }
}

async function fetchPublicConfig() {
  try {
    const response = await fetch("/api/events");
    const payload = await response.json();
    appState.publicConfig = payload;
    renderRules(payload.rules || []);
  } catch {
    // Ignore boot error.
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
    localStorage.setItem(TOKEN_KEY, payload.token);
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
  if (!adminLeaderboardBody) return;
  clearElement(adminLeaderboardBody);
  for (const row of rows || []) {
    const tr = document.createElement("tr");
    const rank = document.createElement("td");
    rank.textContent = row.rank;
    const name = document.createElement("td");
    name.textContent = row.name;
    const bankroll = document.createElement("td");
    bankroll.textContent = formatMoney(row.bankroll);
    const busts = document.createElement("td");
    busts.textContent = String(row.bust_count || 0);
    const bet = document.createElement("td");
    bet.textContent = row.current_bet ? formatMoney(row.current_bet.amount) : "-";
    const powerCards = document.createElement("td");
    powerCards.textContent = `DD ${row.double_down_available ?? 0} | INS ${row.insurance_available ?? 0} | VOL ${row.volatility_available ?? 0}`;
    tr.append(rank, name, bankroll, busts, bet, powerCards);
    adminLeaderboardBody.appendChild(tr);
  }
}

function renderAdminResults(eventRows, fermiRows) {
  clearElement(adminResultsBody);

  for (const row of eventRows || []) {
    const tr = document.createElement("tr");
    const mode = document.createElement("td");
    mode.textContent = "Event";
    const id = document.createElement("td");
    id.textContent = String(row.event_id);
    const status = document.createElement("td");
    status.textContent = row.resolved ? "Resolved" : "Open";
    const extra = document.createElement("td");
    extra.textContent = row.resolved
      ? `${row.outcome?.outcome_label || "-"} | bets=${row.bets_placed}`
      : `bets=${row.bets_placed} wager=${formatMoney(row.total_wagered)}`;
    tr.append(mode, id, status, extra);
    adminResultsBody.appendChild(tr);
  }

  for (const row of fermiRows || []) {
    const tr = document.createElement("tr");
    const mode = document.createElement("td");
    mode.textContent = "Fermi";
    const id = document.createElement("td");
    id.textContent = String(row.question_id);
    const status = document.createElement("td");
    status.textContent = row.resolved ? "Resolved" : "Open";
    const extra = document.createElement("td");
    extra.textContent = row.resolved
      ? `valid=${row.valid_guess_count}/${row.eligible_count}`
      : `live guesses=${row.live_guesses}`;
    tr.append(mode, id, status, extra);
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

  adminEventTitle.value = event.title;
  adminEventDescription.value = event.description;
  adminTrueProbability.value = event.true_probability ?? 0.5;
  adminOddsNumerator.value = event.odds_numerator ?? 1;
  adminOddsDenominator.value = event.odds_denominator ?? 1;
  adminEventSeconds.value = event.bet_window_seconds;
}

function renderFermiEditorOptions(questions) {
  const selectedValue = adminFermiSelect.value;
  clearElement(adminFermiSelect);

  for (const question of questions || []) {
    const option = document.createElement("option");
    option.value = String(question.question_id);
    option.textContent = `Fermi ${question.question_id}`;
    adminFermiSelect.appendChild(option);
  }

  if (selectedValue) {
    adminFermiSelect.value = selectedValue;
  }

  if (!adminFermiSelect.value && adminFermiSelect.options.length) {
    adminFermiSelect.selectedIndex = 0;
  }

  fillFermiEditorFromSelection(questions);
}

function fillFermiEditorFromSelection(questions) {
  const selectedId = Number(adminFermiSelect.value || 0);
  const question = (questions || []).find((row) => row.question_id === selectedId);
  if (!question) {
    return;
  }

  adminFermiPrompt.value = question.prompt;
  adminFermiTruth.value = question.true_value;
  adminFermiUnit.value = question.unit;
  adminFermiSeconds.value = question.answer_window_seconds;
}

function renderAdminState(state) {
  appState.admin.state = state;
  adminControls.classList.remove("hidden");

  setAdminStatus(
    `Connected. Phase=${state.phase} | Players=${state.player_count}/${state.max_players || state.player_count} | Event ${state.event_index}/${state.total_events} | Fermi ${state.fermi_index}/${state.total_fermi} | ${state.paused ? "PAUSED" : "RUNNING"}`,
  );

  adminStartingBankroll.value = state.starting_bankroll;
  adminBustRebuy.value = state.bust_rebuy_amount;
  adminRoundStipend.value = state.round_stipend;

  renderAdminLeaderboard(state.leaderboard);
  renderAdminResults(state.event_results, state.fermi_results);
  renderEventEditorOptions(state.events);
  renderFermiEditorOptions(state.fermi_questions);
  renderRules(state.rules || []);

  if (!adminReplaceEventsJson.value && state.events) {
    const eventTemplate = state.events.map((event) => {
      return {
        title: event.title,
        description: event.description,
        true_probability: event.true_probability || 0.5,
        odds_numerator: event.odds_numerator || 1,
        odds_denominator: event.odds_denominator || 1,
        bet_window_seconds: event.bet_window_seconds,
      };
    });
    adminReplaceEventsJson.value = JSON.stringify(eventTemplate, null, 2);
  }

  if (!adminReplaceFermiJson.value && state.fermi_questions) {
    const fermiTemplate = state.fermi_questions.map((q) => ({
      prompt: q.prompt,
      true_value: q.true_value,
      unit: q.unit,
      answer_window_seconds: q.answer_window_seconds,
    }));
    adminReplaceFermiJson.value = JSON.stringify(fermiTemplate, null, 2);
  }
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

on(joinForm, "submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim();
  if (!name) {
    joinError.textContent = "Player name is required.";
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

  const amount = Number(amountInput.value || 0);
  if (!Number.isFinite(amount) || amount < 0) {
    betStatus.textContent = "Enter a valid amount >= 0.";
    betStatus.className = "error";
    return;
  }

  appState.ws.send(
    JSON.stringify({
      type: "place_bet",
      amount,
      use_double_down: Boolean(doubleDownInput && doubleDownInput.checked),
      use_insurance: Boolean(insuranceInput && insuranceInput.checked),
      use_volatility: Boolean(volatilityInput && volatilityInput.checked),
    }),
  );

  betStatus.textContent = "Bet submitted.";
  betStatus.className = "info-line";
});

on(startGameBtn, "click", () => {
  if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
    betStatus.textContent = "Connection is not ready yet.";
    betStatus.className = "error";
    return;
  }
  appState.ws.send(JSON.stringify({ type: "start_game" }));
  betStatus.textContent = "Start signal sent.";
  betStatus.className = "info-line";
});

on(fermiForm, "submit", (event) => {
  event.preventDefault();
  if (!appState.ws || appState.ws.readyState !== WebSocket.OPEN) {
    betStatus.textContent = "Connection is not ready yet.";
    betStatus.className = "error";
    return;
  }

  const guess = Number(fermiGuessInput.value || 0);
  if (!Number.isFinite(guess) || guess < 0) {
    betStatus.textContent = "Enter a valid non-negative guess.";
    betStatus.className = "error";
    return;
  }

  appState.ws.send(
    JSON.stringify({
      type: "fermi_guess",
      guess,
    }),
  );

  betStatus.textContent = "Fermi guess submitted.";
  betStatus.className = "info-line";
});

for (const btn of tabButtons) {
  on(btn, "click", () => setActiveTab(btn.dataset.tab));
}

on(adminConnectBtn, "click", async () => {
  const key = adminKeyInput.value.trim();
  if (!key) {
    setAdminStatus("Enter admin key.", true);
    return;
  }

  appState.admin.key = key;
  localStorage.setItem(ADMIN_KEY, key);

  try {
    await refreshAdminState();
    if (appState.admin.poller) {
      clearInterval(appState.admin.poller);
    }
    appState.admin.poller = setInterval(async () => {
      try {
        await refreshAdminState();
      } catch {
        // Keep polling.
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

  const startingBankroll = toMaybeNumber(adminStartingBankroll.value);
  const bustRebuy = toMaybeNumber(adminBustRebuy.value);
  const roundStipend = toMaybeNumber(adminRoundStipend.value);
  const uniformEventSeconds = toMaybeNumber(adminUniformEventSeconds.value);
  const uniformFermiSeconds = toMaybeNumber(adminUniformFermiSeconds.value);

  if (startingBankroll !== null) body.starting_bankroll = Math.floor(startingBankroll);
  if (bustRebuy !== null) body.bust_rebuy_amount = Math.floor(bustRebuy);
  if (roundStipend !== null) body.round_stipend = Math.floor(roundStipend);
  if (uniformEventSeconds !== null) body.uniform_event_seconds = Math.floor(uniformEventSeconds);
  if (uniformFermiSeconds !== null) body.uniform_fermi_seconds = Math.floor(uniformFermiSeconds);

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

  const body = {};
  if (adminEventTitle.value.trim()) body.title = adminEventTitle.value.trim();
  if (adminEventDescription.value.trim()) body.description = adminEventDescription.value.trim();

  const trueProbability = toMaybeNumber(adminTrueProbability.value);
  const oddsNumerator = toMaybeNumber(adminOddsNumerator.value);
  const oddsDenominator = toMaybeNumber(adminOddsDenominator.value);
  const eventSeconds = toMaybeNumber(adminEventSeconds.value);

  if (trueProbability !== null) body.true_probability = trueProbability;
  if (oddsNumerator !== null) body.odds_numerator = oddsNumerator;
  if (oddsDenominator !== null) body.odds_denominator = oddsDenominator;
  if (eventSeconds !== null) body.bet_window_seconds = Math.floor(eventSeconds);

  try {
    await adminAction(`/api/admin/events/${eventId}`, "POST", body);
  } catch (err) {
    setAdminStatus(err.message || "Failed to update event.", true);
  }
});

on(adminFermiSelect, "change", () => {
  fillFermiEditorFromSelection(appState.admin.state?.fermi_questions || []);
});

on(adminFermiForm, "submit", async (event) => {
  event.preventDefault();
  const questionId = Number(adminFermiSelect.value);
  if (!questionId) {
    setAdminStatus("Select a Fermi question.", true);
    return;
  }

  const body = {};
  if (adminFermiPrompt.value.trim()) body.prompt = adminFermiPrompt.value.trim();
  if (adminFermiUnit.value.trim()) body.unit = adminFermiUnit.value.trim();

  const trueValue = toMaybeNumber(adminFermiTruth.value);
  const fermiSeconds = toMaybeNumber(adminFermiSeconds.value);
  if (trueValue !== null) body.true_value = trueValue;
  if (fermiSeconds !== null) body.answer_window_seconds = Math.floor(fermiSeconds);

  try {
    await adminAction(`/api/admin/fermi/${questionId}`, "POST", body);
  } catch (err) {
    setAdminStatus(err.message || "Failed to update Fermi question.", true);
  }
});

on(adminReplaceEventsBtn, "click", async () => {
  try {
    const parsed = JSON.parse(adminReplaceEventsJson.value || "[]");
    if (!Array.isArray(parsed)) {
      throw new Error("Event JSON must be an array.");
    }
    await adminAction("/api/admin/events", "PUT", { events: parsed });
  } catch (err) {
    setAdminStatus(err.message || "Failed to replace events.", true);
  }
});

on(adminReplaceFermiBtn, "click", async () => {
  try {
    const parsed = JSON.parse(adminReplaceFermiJson.value || "[]");
    if (!Array.isArray(parsed)) {
      throw new Error("Fermi JSON must be an array.");
    }
    await adminAction("/api/admin/fermi", "PUT", { questions: parsed });
  } catch (err) {
    setAdminStatus(err.message || "Failed to replace fermi questions.", true);
  }
});

// Clear legacy keys from older builds so stale sessions do not break refresh.
localStorage.removeItem("bet-game-token");
localStorage.removeItem("bet-game-admin-key");

const storedToken = localStorage.getItem(TOKEN_KEY);
if (storedToken) {
  appState.token = storedToken;
  joinCard.classList.add("hidden");
  gameView.classList.remove("hidden");
  syncState();
  connectSocket();
}

const storedAdminKey = localStorage.getItem(ADMIN_KEY);
if (storedAdminKey) {
  adminKeyInput.value = storedAdminKey;
}

setActiveTab("playTab");
fetchPublicConfig();
setInterval(fetchPublicConfig, 15000);
setInterval(syncState, 5000);
