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

const invoke = (command, args) => window.__TAURI__.core.invoke(command, args);

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

// While set to a future timestamp, poll() (both the setInterval tick and any
// re-poll-after-action) is a no-op. Used only by launch_docker below, whose
// `open -a Docker` returns almost instantly — long before the daemon is
// actually up — so an immediate re-poll would still see docker_stopped and
// the button would flash back to "Launch Docker" for a fraction of a second.
let pollSuppressedUntil = 0;

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
  stopBtn.hidden = !cfg || !cfg.stopEnabled;
  stopBtn.disabled = busy;
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
  if (Date.now() < pollSuppressedUntil) return;
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
//
// poll() is awaited *before* busy is cleared so currentState is already
// fresh by the time we render as non-busy — otherwise the button would
// flash back to the pre-action state (busy=false, stale currentState) for
// one frame before the real post-action state lands.
async function runAction(action, labelWhileBusy, { minDurationMs = 0 } = {}) {
  if (busy) return;
  busy = true;
  busyLabel = labelWhileBusy;
  clearError();
  render();
  const startedAt = Date.now();
  try {
    await action();
  } catch (err) {
    showError(errorMessage(err));
  } finally {
    if (minDurationMs > 0) {
      // Hold the busy state (and block polling) until the minimum has
      // elapsed, then let poll() below pick up the real post-action state.
      pollSuppressedUntil = startedAt + minDurationMs;
      const remaining = pollSuppressedUntil - Date.now();
      if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
      pollSuppressedUntil = 0;
    }
    await poll();
    busy = false;
    busyLabel = "";
    render();
  }
}

primaryBtn.addEventListener("click", () => {
  const cfg = STATES[currentState];
  if (!cfg || !cfg.run) return;
  // launch_docker returns almost immediately (it just fires `open -a
  // Docker`) — the daemon isn't actually up yet, so give it a grace period
  // before trusting get_app_state() again. See pollSuppressedUntil above.
  const opts = currentState === "docker_stopped" ? { minDurationMs: 5000 } : {};
  runAction(cfg.run, cfg.busyLabel, opts);
});

stopBtn.addEventListener("click", () =>
  runAction(() => invoke("stop_tracker"), "Stopping…")
);

// --- Update banners -------------------------------------------------
//
// Checked once at startup (not polled) via check_launcher_update() and
// check_image_update() in updates.rs. Both are best-effort: a failed check
// resolves with has_update: false (or, defensively, rejects), so either way
// the banner just stays hidden rather than surfacing an error.

const launcherBanner = document.getElementById("launcher-update-banner");
const launcherTextEl = document.getElementById("launcher-update-text");
const launcherNotesToggle = document.getElementById("launcher-notes-toggle");
const launcherNotesEl = document.getElementById("launcher-release-notes");
const launcherOpenBtn = document.getElementById("launcher-update-open");
const launcherDismissBtn = document.getElementById("launcher-update-dismiss");

const imageBanner = document.getElementById("image-update-banner");
const imageNotesToggle = document.getElementById("image-notes-toggle");
const imageNotesEl = document.getElementById("image-release-notes");
const imageOpenBtn = document.getElementById("image-update-open");
const imageUpdateNowBtn = document.getElementById("image-update-now");
const imageUpdateSkipBtn = document.getElementById("image-update-skip");
const imageDismissBtn = document.getElementById("image-update-dismiss");

let imageRemoteDigest = "";

// --- Dynamic window resize -------------------------------------------
//
// Mirrors nova_manager.py's behavior of expanding the window when its log
// viewer was shown: grow the window while either banner's release notes are
// expanded, shrink back to the base size once both are collapsed again.
// Matches the window's initial height in tauri.conf.json — keep both in
// sync. 436 (not 420) leaves ~20px of breathing room under the tallest
// single collapsed banner (the image-update banner, which carries an extra
// Update Now/Skip row) paired with the longest status detail text
// (docker_missing) — that combination left only ~4px of margin at 420.
const WINDOW_HEIGHT_BASE = 436;
const WINDOW_HEIGHT_EXPANDED = 700;

function updateWindowHeight() {
  const notesOpen =
    (!launcherBanner.hidden && !launcherNotesEl.hidden) ||
    (!imageBanner.hidden && !imageNotesEl.hidden);
  invoke("resize_window", {
    height: notesOpen ? WINDOW_HEIGHT_EXPANDED : WINDOW_HEIGHT_BASE,
  }).catch((err) => showError(errorMessage(err)));
}

// Renders GitHub release-note markdown (a narrow, predictable subset —
// headings, bold, bullet lists, paragraphs) to HTML. Escapes the input
// first since this is untrusted text from a GitHub API response, then
// pattern-matches rather than pulling in a markdown library for a feature
// this small.
function renderReleaseNotes(text) {
  const escapeHtml = (s) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const applyInline = (line) => line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  const lines = escapeHtml(text || "").split(/\r?\n/);
  const html = [];
  let list = [];
  let para = [];

  const flushList = () => {
    if (list.length) {
      html.push(`<ul>${list.join("")}</ul>`);
      list = [];
    }
  };
  const flushPara = () => {
    if (para.length) {
      html.push(`<p>${para.join("<br>")}</p>`);
      para = [];
    }
  };

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) {
      flushList();
      flushPara();
      continue;
    }

    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (heading) {
      flushList();
      flushPara();
      html.push(`<h4>${applyInline(heading[1])}</h4>`);
      continue;
    }

    const bullet = line.match(/^-\s+(.*)$/);
    if (bullet) {
      flushPara();
      list.push(`<li>${applyInline(bullet[1])}</li>`);
      continue;
    }

    flushList();
    para.push(applyInline(line));
  }
  flushList();
  flushPara();

  return html.join("");
}

async function checkLauncherUpdate() {
  try {
    const info = await invoke("check_launcher_update");
    if (!info || !info.has_update) return;
    launcherTextEl.textContent = `A new version (v${info.latest_version}) is available`;
    launcherNotesEl.innerHTML = renderReleaseNotes(info.release_notes);
    launcherOpenBtn.onclick = () =>
      invoke("open_url", { url: info.release_url }).catch((err) =>
        showError(errorMessage(err))
      );
    launcherBanner.hidden = false;
  } catch {
    // best-effort — no banner if the check itself rejects
  }
}

launcherNotesToggle.addEventListener("click", () => {
  launcherNotesEl.hidden = !launcherNotesEl.hidden;
  launcherNotesToggle.textContent = launcherNotesEl.hidden
    ? "View Release Notes"
    : "Hide Release Notes";
  updateWindowHeight();
});

launcherDismissBtn.addEventListener("click", () => {
  launcherBanner.hidden = true;
  updateWindowHeight();
});

async function checkImageUpdate() {
  try {
    const info = await invoke("check_image_update");
    if (!info || !info.has_update) return;
    imageRemoteDigest = info.remote_digest;

    // Reset each run rather than trusting the DOM's initial `hidden` —
    // this may be a re-check after a prior run left notes expanded.
    imageNotesEl.hidden = true;
    imageNotesToggle.textContent = "View Release Notes";
    const hasNotes = Boolean(info.release_notes);
    imageNotesToggle.hidden = !hasNotes;
    imageOpenBtn.hidden = !hasNotes;
    if (hasNotes) {
      imageNotesEl.innerHTML = renderReleaseNotes(info.release_notes);
      imageOpenBtn.onclick = () =>
        invoke("open_url", { url: info.release_url }).catch((err) =>
          showError(errorMessage(err))
        );
    }

    imageBanner.hidden = false;
  } catch {
    // best-effort — no banner if the check itself rejects
  }
}

imageNotesToggle.addEventListener("click", () => {
  imageNotesEl.hidden = !imageNotesEl.hidden;
  imageNotesToggle.textContent = imageNotesEl.hidden
    ? "View Release Notes"
    : "Hide Release Notes";
  updateWindowHeight();
});

imageUpdateNowBtn.addEventListener("click", async () => {
  imageUpdateNowBtn.disabled = true;
  imageUpdateSkipBtn.disabled = true;
  const originalLabel = imageUpdateNowBtn.textContent;
  imageUpdateNowBtn.textContent = "Updating…";
  try {
    await invoke("pull_image");
    await invoke("recreate_tracker");
    imageBanner.hidden = true;
    updateWindowHeight();
    poll();
  } catch (err) {
    showError(errorMessage(err));
  } finally {
    imageUpdateNowBtn.disabled = false;
    imageUpdateSkipBtn.disabled = false;
    imageUpdateNowBtn.textContent = originalLabel;
  }
});

imageUpdateSkipBtn.addEventListener("click", async () => {
  try {
    await invoke("skip_image_version", { digest: imageRemoteDigest });
  } catch (err) {
    showError(errorMessage(err));
    return;
  }
  imageBanner.hidden = true;
  updateWindowHeight();
});

imageDismissBtn.addEventListener("click", () => {
  imageBanner.hidden = true;
  updateWindowHeight();
});

if (!window.__TAURI__ || !window.__TAURI__.core) {
  // Opened outside the Tauri webview (e.g. a plain browser tab) — there is
  // no backend to talk to.
  showError("This page must run inside the Nova DSO Tracker desktop app.");
} else {
  poll();
  setInterval(poll, POLL_INTERVAL_MS);
  checkLauncherUpdate();
  checkImageUpdate();
}
