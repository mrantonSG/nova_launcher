/* Nova DSO Tracker — frontend state machine.
 *
 * Talks to the Rust backend through window.__TAURI__.core.invoke, which
 * `app.withGlobalTauri` (src-tauri/tauri.conf.json) exposes to plain
 * <script> tags. No bundler, no imports.
 *
 * State strings come from get_app_state() in src-tauri/src/docker.rs:
 * docker_missing -> docker_stopped -> not_installed -> stopped ->
 * initializing -> running (first failing check wins).
 */

const invoke = (command) => window.__TAURI__.core.invoke(command);

// Poll cadence — mirrors MONITOR_INTERVAL (3s) in config.py.
const POLL_INTERVAL_MS = 3000;

// State -> UI config. Dot colors: running reuses --primary-color (the brand
// teal, matching STATUS_RUNNING in nova_manager.py); the rest are the muted
// tokens added to style.css :root, in the same teal + warm-neutral family as
// the CustomTkinter originals (#FF9500 / #888888 / #a04040).
//
// `run` is null for states where the primary button does nothing (disabled).
const STATES = {
  docker_missing: {
    label: "Docker Missing",
    dotColor: "var(--status-down)",
    detail:
      "Docker Desktop is required to run Nova. Install it, open Docker Desktop, then return here.",
    actionLabel: "Install Docker",
    busyLabel: "Opening Docker downloads…",
    stopEnabled: false,
    run: () => invoke("open_docker_download"),
  },
  docker_stopped: {
    label: "Docker Not Running",
    dotColor: "var(--status-pending)",
    detail: "Please open Docker Desktop to continue.",
    actionLabel: "Launch Docker",
    busyLabel: "Launching Docker…",
    stopEnabled: false,
    run: () => invoke("launch_docker"),
  },
  not_installed: {
    label: "Not Installed",
    dotColor: "var(--status-idle)",
    detail: "Pulls the latest image and starts the tracker.",
    actionLabel: "Install",
    busyLabel: "Installing…",
    stopEnabled: false,
    async run() {
      await invoke("pull_image");
      await invoke("start_tracker");
    },
  },
  stopped: {
    label: "Service Stopped",
    dotColor: "var(--status-idle)",
    detail: "The tracker is installed but not running.",
    actionLabel: "Start",
    busyLabel: "Starting…",
    stopEnabled: false,
    run: () => invoke("start_tracker"),
  },
  initializing: {
    label: "Initializing…",
    dotColor: "var(--status-pending)",
    detail: "Starting up — the dashboard may take a minute.",
    actionLabel: "Starting…",
    stopEnabled: true,
    run: null, // primary button stays disabled while the container comes up
  },
  running: {
    label: "Nova Tracker is Active",
    dotColor: "var(--primary-color)",
    detail: "",
    actionLabel: "Open Dashboard",
    busyLabel: "Opening…",
    stopEnabled: true,
    run: () => invoke("open_dashboard"),
  },
};

const dotEl = document.getElementById("status-dot");
const labelEl = document.getElementById("status-label");
const detailEl = document.getElementById("status-detail");
const primaryBtn = document.getElementById("primary-action");
const primaryLabelEl = document.getElementById("primary-action-label");
const spinnerEl = document.getElementById("spinner");
const stopBtn = document.getElementById("stop-action");
const errorEl = document.getElementById("error-box");

let currentState = null;
let lastRenderedState = null;
let busy = false;
let busyLabel = "";
let polling = false;

function render() {
  const cfg = STATES[currentState];
  if (!cfg) {
    labelEl.textContent = currentState
      ? `Unknown state: ${currentState}`
      : "Checking status…";
    dotEl.style.backgroundColor = "var(--status-idle)";
    detailEl.textContent = "";
    primaryLabelEl.textContent = "…";
  } else {
    labelEl.textContent = cfg.label;
    dotEl.style.backgroundColor = cfg.dotColor;
    detailEl.textContent = cfg.detail;
    primaryLabelEl.textContent = busy ? busyLabel : cfg.actionLabel;
  }

  // Spinner shows while an action is in flight, or whenever the container
  // is mid-initialization.
  spinnerEl.hidden = !(busy || currentState === "initializing");
  primaryBtn.disabled = busy || !cfg || !cfg.run;
  stopBtn.disabled = busy || !cfg || !cfg.stopEnabled;
  lastRenderedState = currentState;
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

function clearError() {
  errorEl.textContent = "";
  errorEl.hidden = true;
}

function errorMessage(err) {
  if (typeof err === "string") return err;
  try {
    return JSON.stringify(err);
  } catch {
    return String(err);
  }
}

// Poll get_app_state(). Overlapping ticks are skipped (a check chain can take
// up to ~12s if the Docker daemon is wedged, so the 3s interval can overlap).
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const state = await invoke("get_app_state");
    if (state !== lastRenderedState) clearError(); // stale error, state moved on
    currentState = state;
    render();
  } catch (err) {
    // get_app_state never Errs, but be defensive rather than going silent.
    showError(`Could not check status: ${errorMessage(err)}`);
  } finally {
    polling = false;
  }
}

// Run a state-changing action, then re-poll immediately so the UI reflects
// the new state without waiting for the next 3s tick.
async function runAction(action, labelWhileBusy) {
  if (busy) return;
  busy = true;
  busyLabel = labelWhileBusy;
  clearError();
  render();
  try {
    await action();
  } catch (err) {
    showError(errorMessage(err));
  } finally {
    busy = false;
    busyLabel = "";
    render();
    poll();
  }
}

primaryBtn.addEventListener("click", () => {
  const cfg = STATES[currentState];
  if (!cfg || !cfg.run) return;
  runAction(cfg.run, cfg.busyLabel);
});

stopBtn.addEventListener("click", () =>
  runAction(() => invoke("stop_tracker"), "Stopping…")
);

if (!window.__TAURI__ || !window.__TAURI__.core) {
  // Opened outside the Tauri webview (e.g. a plain browser tab) — there is
  // no backend to talk to.
  showError("This page must run inside the Nova DSO Tracker desktop app.");
} else {
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
}
