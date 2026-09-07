//! Launcher self-update and tracker image-update checks, exposed as Tauri
//! commands.
//!
//! Best-effort by design: the checks (`check_launcher_update`,
//! `check_image_update`) run at startup as background info, not as
//! user-requested actions. On any network or parse failure they report
//! `has_update: false` rather than an `Err`, so a failed check silently
//! skips the update banner instead of blocking the app or surfacing an
//! error (unlike the Docker action commands, which do surface errors).
//! `skip_image_version` is the one exception: it is a deliberate user
//! action, so I/O failures are surfaced.

use std::fs;
use std::path::PathBuf;
use std::time::Duration;

use semver::Version;
use serde::Serialize;
use serde_json::{Map, Value};

/// GitHub `owner/repo` for the launcher itself (self-update checks).
const LAUNCHER_REPO: &str = "mrantonsg/nova-dso-tracker-launcher";

/// GitHub `owner/repo` for the main Nova DSO Tracker app, used for the
/// tracker image's release notes. Note this is *not* the Docker Hub
/// namespace (`DOCKER_IMAGE` below) — the GitHub repo's owner/name casing
/// and separators differ from the Docker Hub ones.
const NOVA_APP_REPO: &str = "mrantonSG/nova_DSO_tracker";

/// `User-Agent` sent with release requests — GitHub's API rejects requests
/// without one.
const USER_AGENT: &str = "nova-dso-tracker-launcher";

/// Docker Hub `namespace/repo` for the tracker image (matches `DOCKER_IMAGE`
/// in the Python launcher's `config.py`).
const DOCKER_IMAGE: &str = "mrantonsg/nova-dso-tracker";
/// Tag tracked for updates (matches `DOCKER_TAG`).
const DOCKER_TAG: &str = "latest";
/// Fully-qualified image reference passed to `docker` (matches
/// `DOCKER_IMAGE_FULL`).
const DOCKER_IMAGE_FULL: &str = "mrantonsg/nova-dso-tracker:latest";

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
    let release = match fetch_latest_github_release(LAUNCHER_REPO) {
        Ok(release) => release,
        Err(_) => return no_update(),
    };

    // GitHub tags releases like "v1.3.1"; strip the leading `v` and compare
    // as semver — versions don't sort correctly as strings ("1.10.0" would
    // sort before "1.9.0" alphabetically).
    let version_str = release
        .tag_name
        .strip_prefix('v')
        .unwrap_or(&release.tag_name)
        .to_string();
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
        release_notes: release.body,
        release_url: release.html_url,
    }
}

/// Fields pulled out of a GitHub "latest release" API response, shared by
/// the launcher's self-update check and the tracker image's release-notes
/// lookup.
struct GitHubRelease {
    tag_name: String,
    body: String,
    html_url: String,
}

/// GETs `repo`'s latest release from GitHub and pulls out the fields callers
/// need. `repo` is an `owner/name` path, e.g. `"mrantonsg/nova-dso-tracker"`.
fn fetch_latest_github_release(repo: &str) -> Result<GitHubRelease, String> {
    let url = format!("https://api.github.com/repos/{repo}/releases/latest");
    // 5s cap: callers run this at startup or alongside other checks, so a
    // slow or wedged network must not hold up the UI.
    let response = ureq::get(&url)
        .set("User-Agent", USER_AGENT)
        .timeout(Duration::from_secs(5))
        .call()
        .map_err(|e| format!("failed to fetch latest release: {e}"))?;
    let raw = response
        .into_string()
        .map_err(|e| format!("failed to read release response: {e}"))?;
    let value: Value =
        serde_json::from_str(&raw).map_err(|e| format!("failed to parse release JSON: {e}"))?;

    Ok(GitHubRelease {
        tag_name: value
            .get("tag_name")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        body: value
            .get("body")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
        html_url: value
            .get("html_url")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string(),
    })
}

/// Docker image-update info as reported to the frontend.
#[derive(Debug, Clone, Serialize)]
pub struct ImageUpdateInfo {
    /// `true` when the remote digest differs from the local image's digest
    /// (and the user hasn't skipped that remote version).
    pub has_update: bool,
    /// Digest of `mrantonsg/nova-dso-tracker:latest` on the registry. Empty
    /// if it could not be determined.
    pub remote_digest: String,
    /// Digest of the locally pulled image. Empty if no local image is
    /// found (in which case `has_update` is `true` whenever a remote digest
    /// was found, mirroring `docker_ops.py`'s `_compare_digests`).
    pub local_digest: String,
    /// Raw release notes from the Nova app repo's latest GitHub release
    /// body, unmodified. Only populated when `has_update` is `true`; empty
    /// if there's no update or the release fetch failed.
    pub release_notes: String,
    /// GitHub release page URL for the Nova app's latest release. Same
    /// population rule as `release_notes`.
    pub release_url: String,
    /// `org.opencontainers.image.version` label of the locally pulled
    /// image, without a leading `v`. Empty if no local image is found, the
    /// label is missing (older images predate the version-label fix), or
    /// the check failed. Display-only — `has_update` stays digest-based.
    pub local_version: String,
    /// Version of the Nova app repo's latest GitHub release (its `tag_name`
    /// with a leading `v` stripped, same convention as the launcher's own
    /// version comparison). Same population rule as `release_notes`.
    pub remote_version: String,
}

fn no_image_update() -> ImageUpdateInfo {
    ImageUpdateInfo {
        has_update: false,
        remote_digest: String::new(),
        local_digest: String::new(),
        release_notes: String::new(),
        release_url: String::new(),
        local_version: String::new(),
        remote_version: String::new(),
    }
}

/// Checks Docker Hub for a tracker image update, folding in the
/// skipped-version preference so a deliberately-skipped remote digest is
/// reported as "no update".
///
/// Best-effort like `check_launcher_update`: any failure yields
/// `Ok(ImageUpdateInfo { has_update: false, .. })` rather than an `Err`.
#[tauri::command]
pub async fn check_image_update() -> Result<ImageUpdateInfo, String> {
    let local_digest = get_local_image_digest().await;
    let remote_digest = match get_remote_digest().await {
        Some(digest) => digest,
        None => return Ok(no_image_update()),
    };

    // Mirrors `_compare_digests` in docker_ops.py: no local image means an
    // update is available by definition.
    let mut has_update = match &local_digest {
        Some(local) => normalize_digest(local) != normalize_digest(&remote_digest),
        None => true,
    };

    // Mirrors the caller-side skip check in nova_manager.py, folded in here
    // per this command's contract.
    if has_update {
        if let Some(skipped) = read_skipped_digest() {
            if normalize_digest(&skipped) == normalize_digest(&remote_digest) {
                has_update = false;
            }
        }
    }

    // Release notes/version are a nice-to-have on top of the digest
    // comparison above, which is already complete by this point: only fetch
    // them when there's actually an update to report, and never let a
    // failure here turn into a failed command — just leave them empty.
    let (release_notes, release_url, remote_version) = if has_update {
        fetch_nova_app_release_info().await
    } else {
        (String::new(), String::new(), String::new())
    };

    let local_version = get_local_image_version().await.unwrap_or_default();

    Ok(ImageUpdateInfo {
        has_update,
        remote_digest,
        local_digest: local_digest.unwrap_or_default(),
        release_notes,
        release_url,
        local_version,
        remote_version,
    })
}

/// Fetches the Nova app repo's latest release notes, URL, and version for
/// the update banner. Best-effort: any failure (network, timeout, parse)
/// yields empty strings rather than propagating an error, since
/// `has_update` must still reflect the digest comparison regardless of
/// whether this succeeds.
async fn fetch_nova_app_release_info() -> (String, String, String) {
    match tokio::task::spawn_blocking(|| fetch_latest_github_release(NOVA_APP_REPO)).await {
        Ok(Ok(release)) => {
            // Same "v" stripping convention as `fetch_latest_update`'s
            // launcher version comparison.
            let version = release
                .tag_name
                .strip_prefix('v')
                .unwrap_or(&release.tag_name)
                .to_string();
            (release.body, release.html_url, version)
        }
        _ => (String::new(), String::new(), String::new()),
    }
}

/// Records a remote digest the user has chosen to skip, so
/// `check_image_update` stops reporting it. Preserves any other existing
/// keys in the prefs file (read-modify-write).
///
/// Unlike the read-only checks above, this is a deliberate user action, so
/// I/O failures are surfaced as `Err` rather than swallowed.
#[tauri::command]
pub fn skip_image_version(digest: String) -> Result<(), String> {
    let path = launcher_prefs_path().ok_or("could not determine home directory")?;
    let mut prefs = read_prefs_file(&path).unwrap_or_default();
    prefs.insert("skipped_digest".to_string(), Value::String(digest));
    write_prefs_file(&path, &prefs)
}

/// Digest of the locally pulled tracker image, via `docker image inspect`'s
/// `.RepoDigests` (the registry digest saved at pull time — distinct from
/// `.Id`, the image config digest). Mirrors `get_local_image_digest` in
/// docker_ops.py. `None` on any failure or if no local image exists.
async fn get_local_image_digest() -> Option<String> {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.arg("image")
        .arg("inspect")
        .arg(DOCKER_IMAGE_FULL)
        .arg("--format")
        .arg("{{index .RepoDigests 0}}");
    let output = tokio::time::timeout(Duration::from_secs(5), cmd.output())
        .await
        .ok()?
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if stdout.is_empty() {
        return None;
    }
    extract_repo_digest(&stdout)
}

/// Version of the locally pulled tracker image, via `docker image inspect`'s
/// `org.opencontainers.image.version` label. `None` on any failure, if no
/// local image exists, or if the label is empty/missing — which is expected
/// for any image pulled before the version-label fix shipped on the Nova
/// side, so this must degrade gracefully rather than error.
async fn get_local_image_version() -> Option<String> {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.arg("image")
        .arg("inspect")
        .arg(DOCKER_IMAGE_FULL)
        .arg("--format")
        .arg(r#"{{index .Config.Labels "org.opencontainers.image.version"}}"#);
    let output = tokio::time::timeout(Duration::from_secs(5), cmd.output())
        .await
        .ok()?
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if stdout.is_empty() || stdout == "<no value>" {
        return None;
    }
    Some(stdout)
}

/// Parses a `.RepoDigests` entry (`"image@sha256:..."`) down to just the
/// digest, matching `get_local_image_digest`'s fallback handling for
/// unexpected formats.
fn extract_repo_digest(repo_digest: &str) -> Option<String> {
    if let Some((_, digest)) = repo_digest.split_once('@') {
        return Some(digest.to_string());
    }
    if repo_digest.starts_with("sha256:") {
        return Some(repo_digest.to_string());
    }
    if repo_digest.len() >= 12 {
        return Some(format!("sha256:{repo_digest}"));
    }
    Some(repo_digest.to_string())
}

/// Remote digest for `mrantonsg/nova-dso-tracker:latest`: `docker manifest
/// inspect --verbose` first (matches `check_dockerhub_version`'s primary
/// method), falling back to the Docker Hub REST API.
async fn get_remote_digest() -> Option<String> {
    if let Some(digest) = get_remote_digest_via_manifest().await {
        return Some(digest);
    }
    get_remote_digest_via_hub_api().await
}

/// Runs `docker manifest inspect --verbose` and picks the digest out of
/// whichever shape the JSON comes back in — a single digest field, a
/// manifest list (preferring an amd64/arm64 entry), or a schema-2 manifest —
/// matching `check_dockerhub_version`'s parsing in docker_ops.py.
async fn get_remote_digest_via_manifest() -> Option<String> {
    let mut cmd = tokio::process::Command::new("docker");
    cmd.arg("manifest")
        .arg("inspect")
        .arg(DOCKER_IMAGE_FULL)
        .arg("--verbose");
    let output = tokio::time::timeout(Duration::from_secs(5), cmd.output())
        .await
        .ok()?
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let stdout = String::from_utf8_lossy(&output.stdout);
    let data: Value = serde_json::from_str(&stdout).ok()?;
    extract_manifest_digest(&data)
}

fn extract_manifest_digest(data: &Value) -> Option<String> {
    if let Some(digest) = data.get("digest").and_then(Value::as_str) {
        return Some(digest.to_string());
    }
    if let Some(digest) = data
        .get("Descriptor")
        .and_then(|d| d.get("digest"))
        .and_then(Value::as_str)
    {
        return Some(digest.to_string());
    }
    if let Some(manifests) = data.get("manifests").and_then(Value::as_array) {
        for manifest in manifests {
            let arch = manifest
                .get("platform")
                .and_then(|p| p.get("architecture"))
                .and_then(Value::as_str);
            if matches!(arch, Some("amd64") | Some("arm64")) {
                if let Some(digest) = manifest.get("digest").and_then(Value::as_str) {
                    return Some(digest.to_string());
                }
            }
        }
    }
    data.get("manifest")
        .and_then(|m| m.get("config"))
        .and_then(|c| c.get("digest"))
        .and_then(Value::as_str)
        .map(|s| s.to_string())
}

/// Docker Hub REST API fallback for the remote digest, used when `docker
/// manifest inspect` is unavailable or fails. Matches `check_dockerhub_version`'s
/// method 2.
async fn get_remote_digest_via_hub_api() -> Option<String> {
    tokio::task::spawn_blocking(fetch_hub_digest).await.ok()?
}

fn fetch_hub_digest() -> Option<String> {
    let (namespace, repo) = DOCKER_IMAGE.split_once('/')?;
    let url = format!("https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/{DOCKER_TAG}");
    let response = ureq::get(&url)
        .set("User-Agent", "NovaLauncher/1.0")
        .timeout(Duration::from_secs(5))
        .call()
        .ok()?;
    let raw = response.into_string().ok()?;
    let data: Value = serde_json::from_str(&raw).ok()?;
    if let Some(digest) = data.get("digest").and_then(Value::as_str) {
        return Some(digest.to_string());
    }
    data.get("images")
        .and_then(Value::as_array)
        .and_then(|images| images.first())
        .and_then(|image| image.get("digest"))
        .and_then(Value::as_str)
        .map(|s| s.to_string())
}

/// Normalizes a digest for comparison: strips `sha256:` prefix, lowercases,
/// and keeps only the first 64 hex chars — matching `_compare_digests`'s
/// `remote_normalized[:64] != local_normalized[:64]` comparison.
fn normalize_digest(digest: &str) -> String {
    digest
        .replace("sha256:", "")
        .to_lowercase()
        .chars()
        .take(64)
        .collect()
}

/// Path to `~/nova/.launcher_prefs.json`. `None` if the home directory can't
/// be determined.
fn launcher_prefs_path() -> Option<PathBuf> {
    dirs::home_dir().map(|home| home.join("nova").join(".launcher_prefs.json"))
}

/// Reads the prefs file's `{ "skipped_digest": "..." }` field, if any.
fn read_skipped_digest() -> Option<String> {
    let path = launcher_prefs_path()?;
    let prefs = read_prefs_file(&path)?;
    prefs.get("skipped_digest")?.as_str().map(|s| s.to_string())
}

/// Reads the prefs file as a JSON object. `None` if it doesn't exist, isn't
/// valid JSON, or isn't an object.
fn read_prefs_file(path: &PathBuf) -> Option<Map<String, Value>> {
    let raw = fs::read_to_string(path).ok()?;
    let value: Value = serde_json::from_str(&raw).ok()?;
    value.as_object().cloned()
}

/// Writes the prefs file, creating `~/nova` if it doesn't exist yet.
fn write_prefs_file(path: &PathBuf, prefs: &Map<String, Value>) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("failed to create nova directory: {e}"))?;
    }
    let json = serde_json::to_string_pretty(prefs)
        .map_err(|e| format!("failed to serialize launcher prefs: {e}"))?;
    fs::write(path, json).map_err(|e| format!("failed to write launcher prefs file: {e}"))
}
