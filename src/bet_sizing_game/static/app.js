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

const appState = {
  token: null,
  ws: null,
  latest: null,
};

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

  for (const text of chips) {
    const chip = document.createElement("span");
    chip.className = "event-chip";
    chip.textContent = text;
    eventMeta.appendChild(chip);
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
    }
  }

  playerCountValue.textContent = state.player_count;
  renderLeaderboard(state.leaderboard);
  renderMetaChips(state);

  if (state.phase === "lobby") {
    phaseTitle.textContent = "Lobby";
    timerPill.textContent = `${state.lobby_seconds_remaining}s`;
    eventTitle.textContent = "Waiting for the game to start";
    eventDescription.textContent =
      "All players are loading in. You will receive $100 before each of the 10 events, and everyone sees the same outcomes.";
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
    eventDescription.textContent = "Final standings are locked. Top 10 shown on the leaderboard.";
    betForm.classList.add("hidden");
    podiumPanel.classList.remove("hidden");
    renderPodium(state.podium);
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

joinForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim();
  if (!name) {
    joinError.textContent = "Name is required.";
    return;
  }
  join(name);
});

betForm.addEventListener("submit", (event) => {
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

const storedToken = localStorage.getItem("bet-game-token");
if (storedToken) {
  appState.token = storedToken;
  joinCard.classList.add("hidden");
  gameView.classList.remove("hidden");
  syncState();
  connectSocket();
}

setInterval(syncState, 5000);
