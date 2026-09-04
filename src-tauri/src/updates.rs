//! Launcher self-update check exposed as a Tauri command.
//!
//! Best-effort by design: this runs at startup as background info, not as a
//! user-requested action. On any network or parse failure it reports
//! `has_update: false` rather than an `Err`, so a failed check silently
//! skips the update banner instead of blocking the app or surfacing an
//! error (unlike the Docker action commands, which do surface errors).
//! Docker image update checks come in a separate step.

use std::time::Duration;

use semver::Version;
use serde::Serialize;
use serde_json::Value;

/// GitHub releases API URL for the latest launcher release.
const LATEST_RELEASE_URL: &str =
    "https://api.github.com/repos/mrantonsg/nova-dso-tracker-launcher/releases/latest";

/// `User-Agent` sent with the release request — GitHub's API rejects
/// requests without one.
const USER_AGENT: &str = "nova-dso-tracker-launcher";

/// Latest-launcher-release info as reported to the frontend.
#[derive(Debug, Clone, Serialize)]
pub struct UpdateInfo {
    /// `true` when the latest release is newer than the running app.
    pub has_update: bool,
    /// Latest release version without any leading `v` (e.g. `"1.3.1"`).
    /// Empty when no update info could be retrieved.
    pub latest_version: String,
    /// Raw release notes from the GitHub release body, unmodified —
    /// rendering/stripping markdown is a frontend concern.
    pub release_notes: String,
    /// GitHub release page URL.
    pub release_url: String,
}

/// Update info returned when the check itself failed (network, timeout, or
/// an unparseable response): no update is reported, so the UI simply skips
/// the banner.
fn no_update() -> UpdateInfo {
    UpdateInfo {
        has_update: false,
        latest_version: String::new(),
        release_notes: String::new(),
        release_url: String::new(),
    }
}

/// Checks GitHub for a launcher release newer than the running app.
///
/// Best-effort: network/parse problems yield
/// `Ok(UpdateInfo { has_update: false, .. })` rather than an `Err`.
#[tauri::command]
pub async fn check_launcher_update() -> Result<UpdateInfo, String> {
    // ureq is a blocking client, so run it off the async runtime thread
    // (same pattern as `dashboard_reachable` in docker.rs).
    Ok(
        tokio::task::spawn_blocking(fetch_latest_update)
            .await
            .unwrap_or(no_update()),
    )
}

/// Fetches the latest release from GitHub and compares it against the
/// running app version. Runs on a blocking thread (called from
/// `check_launcher_update`'s `spawn_blocking`).
fn fetch_latest_update() -> UpdateInfo {
    let release = match fetch_latest_release() {
        Ok(release) => release,
        Err(_) => return no_update(),
    };

    // GitHub tags releases like "v1.3.1"; strip the leading `v` and compare
    // as semver — versions don't sort correctly as strings ("1.10.0" would
    // sort before "1.9.0" alphabetically).
    let version_str = release
        .get("tag_name")
        .and_then(|tag| tag.as_str())
        .map(|tag| tag.strip_prefix('v').unwrap_or(tag).to_string())
        .unwrap_or_default();
    let latest = match Version::parse(&version_str) {
        Ok(latest) => latest,
        Err(_) => return no_update(),
    };
    let current = match Version::parse(env!("CARGO_PKG_VERSION")) {
        Ok(current) => current,
        Err(_) => return no_update(),
    };

    UpdateInfo {
        has_update: latest > current,
        latest_version: version_str,
        release_notes: release
            .get("body")
            .and_then(|b| b.as_str())
            .unwrap_or_default()
            .to_string(),
        release_url: release
            .get("html_url")
            .and_then(|u| u.as_str())
            .unwrap_or_default()
            .to_string(),
    }
}

/// GETs the latest release and returns its raw JSON payload.
fn fetch_latest_release() -> Result<Value, String> {
    // 5s cap: this runs at startup, so a slow or wedged network must not
    // hold up the UI.
    let response = ureq::get(LATEST_RELEASE_URL)
        .set("User-Agent", USER_AGENT)
        .timeout(Duration::from_secs(5))
        .call()
        .map_err(|e| format!("failed to fetch latest release: {e}"))?;
    let raw = response
        .into_string()
        .map_err(|e| format!("failed to read release response: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("failed to parse release JSON: {e}"))
}
