//! Downloads only this application's published installer. No caller-supplied
//! URL, filename or command is accepted. GitHub's SHA-256 metadata is an integrity
//! check over HTTPS, not a replacement for publisher code signing.
use reqwest::{blocking::Client, redirect::Policy, Url};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{fs::{self, File, OpenOptions}, io::{Read, Write}, path::{Path, PathBuf}, process::Command, sync::{Arc, Mutex}, time::Duration};
use tauri::{AppHandle, Manager, State, WebviewWindow};
use tempfile::TempDir;

const RELEASE_API: &str = "https://api.github.com/repos/diracmagic/supercon-ml/releases/latest";
const MAX_METADATA: u64 = 1024 * 1024;
const MAX_INSTALLER: u64 = 512 * 1024 * 1024;
type Result<T> = std::result::Result<T, String>;
fn error(code: &str) -> String { code.to_owned() }

#[derive(Default)]
pub struct UpdateState(Arc<Mutex<DownloadState>>);
#[derive(Default)]
struct DownloadState { busy: bool, ready: Option<Ready> }
struct Ready { info: DownloadInfo, directory: TempDir, hash: String, launched: bool }
#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct DownloadInfo { download_id: String, version: String, platform: String, size: u64 }
#[derive(Serialize)]
pub struct InstallInfo { launched: bool, version: String, platform: String }
#[derive(Deserialize)]
struct Release { tag_name: String, draft: bool, prerelease: bool, assets: Vec<Asset> }
#[derive(Deserialize)]
struct Asset { name: String, state: String, size: u64, digest: Option<String>, browser_download_url: String }
struct ChosenAsset { version: String, size: u64, hash: String, url: String }

fn version(value: &str) -> Option<[u64; 3]> {
    if value.len() > 40 { return None; }
    let values = value.split('.').collect::<Vec<_>>();
    if values.len() != 3 { return None; }
    let mut out = [0; 3];
    for (index, part) in values.iter().enumerate() {
        if part.is_empty() || !part.bytes().all(|b| b.is_ascii_digit()) || (part.len() > 1 && part.starts_with('0')) { return None; }
        out[index] = part.parse().ok()?;
    }
    Some(out)
}
fn platform() -> Result<&'static str> {
    if cfg!(target_os = "windows") { Ok("windows") }
    else if cfg!(target_os = "macos") { Ok("macos") }
    else { Err(error("update_unsupported_platform")) }
}
fn installer_name(platform: &str) -> Result<&'static str> {
    match platform {
        "windows" => Ok("SuperconProgress-windows-x64-setup.exe"),
        "macos" => Ok("SuperconProgress-macos-universal.dmg"),
        _ => Err(error("update_unsupported_platform")),
    }
}
fn trusted_redirect(url: &Url) -> bool {
    url.scheme() == "https" && url.username().is_empty() && url.password().is_none()
        && url.port().is_none() && url.fragment().is_none()
        && matches!(url.host_str(), Some("github.com" | "release-assets.githubusercontent.com" | "objects.githubusercontent.com"))
}
fn local_origin(url: &Url, label: &str) -> bool {
    label == "main" && url.username().is_empty() && url.password().is_none() && url.port().is_none()
        && ((url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (matches!(url.scheme(), "http" | "https") && url.host_str() == Some("tauri.localhost")))
}
fn authorize(window: &WebviewWindow) -> Result<()> {
    let url = window.url().map_err(|_| error("update_origin_denied"))?;
    if local_origin(&url, window.label()) { Ok(()) } else { Err(error("update_origin_denied")) }
}
fn choose(release: Release, expected: &str, running: &str, platform: &str) -> Result<ChosenAsset> {
    let expected_parts = version(expected).ok_or_else(|| error("update_release_changed"))?;
    let running_parts = version(running).ok_or_else(|| error("update_not_newer"))?;
    if expected_parts <= running_parts { return Err(error("update_not_newer")); }
    if release.draft || release.prerelease || release.tag_name != format!("app-v{expected}") { return Err(error("update_release_changed")); }
    let name = installer_name(platform)?;
    let mut matches = release.assets.into_iter().filter(|asset| asset.name == name);
    let asset = matches.next().ok_or_else(|| error("update_asset_unavailable"))?;
    if matches.next().is_some() || asset.state != "uploaded" || asset.size == 0 || asset.size > MAX_INSTALLER { return Err(error("update_asset_unavailable")); }
    let expected_url = format!("https://github.com/diracmagic/supercon-ml/releases/download/app-v{expected}/{name}");
    if asset.browser_download_url != expected_url { return Err(error("update_asset_unavailable")); }
    let hash = asset.digest.and_then(|value| value.strip_prefix("sha256:").map(str::to_owned)).ok_or_else(|| error("update_digest_unavailable"))?;
    if hash.len() != 64 || !hash.bytes().all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)) { return Err(error("update_digest_unavailable")); }
    Ok(ChosenAsset { version: expected.to_owned(), size: asset.size, hash, url: expected_url })
}
fn client(download: bool) -> Result<Client> {
    let redirects = if download { Policy::custom(|attempt| {
        if attempt.previous().len() <= 4 && trusted_redirect(attempt.url()) { attempt.follow() }
        else { attempt.error("untrusted update redirect") }
    }) } else { Policy::none() };
    Client::builder().user_agent(concat!("SuperconProgress/", env!("CARGO_PKG_VERSION")))
        .connect_timeout(Duration::from_secs(15)).timeout(Duration::from_secs(if download { 600 } else { 30 }))
        .redirect(redirects).build().map_err(|_| error("update_unavailable"))
}
fn copy_checked<R: Read, W: Write>(reader: &mut R, writer: &mut W, expected_size: u64, expected_hash: &str) -> Result<()> {
    if expected_size == 0 || expected_size > MAX_INSTALLER { return Err(error("update_integrity_failed")); }
    let mut hasher = Sha256::new(); let mut count = 0u64; let mut buffer = [0u8; 65536];
    loop {
        let length = reader.read(&mut buffer).map_err(|_| error("update_download_failed"))?;
        if length == 0 { break; }
        count += length as u64;
        if count > expected_size { return Err(error("update_integrity_failed")); }
        hasher.update(&buffer[..length]);
        writer.write_all(&buffer[..length]).map_err(|_| error("update_download_failed"))?;
    }
    if count != expected_size || format!("{:x}", hasher.finalize()) != expected_hash { return Err(error("update_integrity_failed")); }
    Ok(())
}
fn download(root: PathBuf, expected: String, target: &'static str) -> Result<Ready> {
    let response = client(false)?.get(RELEASE_API).header("Accept", "application/vnd.github+json")
        .header("X-GitHub-Api-Version", "2022-11-28").send().map_err(|_| error("update_unavailable"))?;
    if !response.status().is_success() || response.content_length().is_some_and(|length| length > MAX_METADATA) { return Err(error("update_unavailable")); }
    let mut bytes = Vec::new(); response.take(MAX_METADATA + 1).read_to_end(&mut bytes).map_err(|_| error("update_unavailable"))?;
    if bytes.len() as u64 > MAX_METADATA { return Err(error("update_unavailable")); }
    let release: Release = serde_json::from_slice(&bytes).map_err(|_| error("update_unavailable"))?;
    let asset = choose(release, &expected, env!("CARGO_PKG_VERSION"), target)?;
    fs::create_dir_all(&root).map_err(|_| error("update_download_failed"))?;
    let root = root.canonicalize().map_err(|_| error("update_download_failed"))?;
    let directory = tempfile::Builder::new().prefix("verified-update-").tempdir_in(&root).map_err(|_| error("update_download_failed"))?;
    let resolved = directory.path().canonicalize().map_err(|_| error("update_download_failed"))?;
    if !resolved.starts_with(&root) || resolved == root { return Err(error("update_download_failed")); }
    let path = resolved.join(installer_name(target)?);
    let mut file = OpenOptions::new().write(true).create_new(true).open(path).map_err(|_| error("update_download_failed"))?;
    let mut response = client(true)?.get(asset.url).send().map_err(|_| error("update_download_failed"))?;
    if !response.status().is_success() || !trusted_redirect(response.url()) || response.content_length().is_some_and(|length| length != asset.size) { return Err(error("update_download_failed")); }
    copy_checked(&mut response, &mut file, asset.size, &asset.hash)?;
    file.sync_all().map_err(|_| error("update_download_failed"))?;
    Ok(Ready { info: DownloadInfo { download_id: uuid::Uuid::new_v4().to_string(), version: asset.version, platform: target.to_owned(), size: asset.size }, directory, hash: asset.hash, launched: false })
}

fn downloaded_or_cached<F>(cached: Option<Ready>, expected: &str, target: &str, fetch: F) -> Result<Ready>
where F: FnOnce() -> Result<Ready> {
    if let Some(ready) = cached {
        if ready.info.version == expected && ready.info.platform == target && !ready.launched && verified_file(&ready).is_ok() {
            return Ok(ready);
        }
        // Drop the invalid cache before fetching, including its temporary directory.
    }
    fetch()
}

#[tauri::command]
pub async fn download_app_update(app: AppHandle, window: WebviewWindow, state: State<'_, UpdateState>, expected_version: String) -> Result<DownloadInfo> {
    authorize(&window)?;
    if version(&expected_version).is_none() { return Err(error("update_release_changed")); }
    let target = platform()?;
    let root = app.path().app_cache_dir().map_err(|_| error("update_download_failed"))?.join("verified-updates");
    let cached = {
        let mut data = state.0.lock().map_err(|_| error("update_unavailable"))?;
        if data.busy { return Err(error("update_busy")); }
        data.busy = true;
        data.ready.take()
    };
    let result = tauri::async_runtime::spawn_blocking(move || {
        downloaded_or_cached(cached, &expected_version, target, || download(root, expected_version.clone(), target))
    }).await
        .map_err(|_| error("update_download_failed")).and_then(|result| result);
    let mut data = state.0.lock().map_err(|_| error("update_unavailable"))?;
    data.busy = false;
    let ready = result?; let info = ready.info.clone(); data.ready = Some(ready); Ok(info)
}

fn verified_file(ready: &Ready) -> Result<File> {
    let path = ready.directory.path().join(installer_name(&ready.info.platform)?);
    let metadata = fs::symlink_metadata(&path).map_err(|_| error("update_integrity_failed"))?;
    if !metadata.is_file() || metadata.file_type().is_symlink() || metadata.len() != ready.info.size { return Err(error("update_integrity_failed")); }
    let mut options = OpenOptions::new(); options.read(true);
    #[cfg(target_os = "windows")]
    { use std::os::windows::fs::OpenOptionsExt; options.share_mode(1); } // Read sharing only: deny replacement/writes during launch.
    let mut file = options.open(&path).map_err(|_| error("update_integrity_failed"))?;
    copy_checked(&mut file, &mut std::io::sink(), ready.info.size, &ready.hash)?;
    Ok(file)
}
fn install_file(data: &mut DownloadState, download_id: &str) -> Result<File> {
    if data.busy { return Err(error("update_busy")); }
    let ready = data.ready.as_ref().filter(|ready| ready.info.download_id == download_id && !ready.launched).ok_or_else(|| error("update_not_downloaded"))?;
    match verified_file(ready) {
        Ok(file) => Ok(file),
        Err(_) => {
            data.ready = None;
            Err(error("update_integrity_failed"))
        }
    }
}
fn launch(path: &Path) -> Result<()> {
    #[cfg(target_os = "windows")]
    let child = { use std::os::windows::process::CommandExt; Command::new(path).creation_flags(0x08000000).spawn() };
    #[cfg(target_os = "macos")]
    let child = Command::new("/usr/bin/open").arg(path).spawn();
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    return Err(error("update_unsupported_platform"));
    #[cfg(any(target_os = "windows", target_os = "macos"))]
    child.map(|_| ()).map_err(|_| error("update_launch_failed"))
}
#[tauri::command]
pub async fn install_app_update(window: WebviewWindow, state: State<'_, UpdateState>, download_id: String) -> Result<InstallInfo> {
    authorize(&window)?;
    if uuid::Uuid::parse_str(&download_id).is_err() { return Err(error("update_not_downloaded")); }
    let shared = state.0.clone();
    tauri::async_runtime::spawn_blocking(move || {
        let mut data = shared.lock().map_err(|_| error("update_unavailable"))?;
        let held = install_file(&mut data, &download_id)?;
        let ready = data.ready.as_mut().ok_or_else(|| error("update_not_downloaded"))?;
        let path = ready.directory.path().join(installer_name(&ready.info.platform)?);
        launch(&path)?; ready.launched = true; drop(held);
        Ok(InstallInfo { launched: true, version: ready.info.version.clone(), platform: ready.info.platform.clone() })
    }).await.map_err(|_| error("update_launch_failed"))?
}

#[cfg(test)]
mod tests {
    use super::*;
    fn cached_fixture() -> Ready {
        let directory = tempfile::tempdir().unwrap(); let bytes = b"installer fixture";
        fs::write(directory.path().join(installer_name("windows").unwrap()), bytes).unwrap();
        Ready { info: DownloadInfo { download_id: uuid::Uuid::new_v4().to_string(), version: "1.2.3".into(), platform: "windows".into(), size: bytes.len() as u64 }, directory, hash: format!("{:x}", Sha256::digest(bytes)), launched: false }
    }
    fn release() -> Release { Release { tag_name: "app-v1.2.3".into(), draft: false, prerelease: false, assets: vec![Asset { name: "SuperconProgress-windows-x64-setup.exe".into(), state: "uploaded".into(), size: 3, digest: Some(format!("sha256:{}", "a".repeat(64))), browser_download_url: "https://github.com/diracmagic/supercon-ml/releases/download/app-v1.2.3/SuperconProgress-windows-x64-setup.exe".into() }] } }
    #[test] fn only_exact_new_stable_version_and_asset() {
        assert!(choose(release(), "1.2.3", "1.2.2", "windows").is_ok());
        for v in ["1.2.3-beta", "../1.2.3", "01.2.3", "1.2.3.4", "999999999999999999999.1.1"] { assert!(version(v).is_none()); }
        assert!(choose(release(), "1.2.3", "1.2.3", "windows").is_err());
        assert!(choose(release(), "1.2.4", "1.2.2", "windows").is_err());
        let mut r = release(); r.draft = true; assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.prerelease = true; assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets[0].browser_download_url = "https://evil.example/install.exe".into(); assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets[0].digest = None; assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets[0].digest = Some(format!("sha256:{}", "g".repeat(64))); assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets[0].size = MAX_INSTALLER + 1; assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets.push(release().assets.remove(0)); assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        let mut r = release(); r.assets[0].name = "SuperconProgress-windows-x64.msi".into(); assert!(choose(r, "1.2.3", "1.2.2", "windows").is_err());
        assert!(choose(release(), "1.2.3", "1.2.2", "macos").is_err());
    }
    #[test] fn redirects_and_origins_are_restricted() {
        for url in ["http://github.com/x", "https://evil.example/x", "https://github.com.evil.example/x", "https://user@github.com/x", "https://github.com:444/x"] { assert!(!trusted_redirect(&Url::parse(url).unwrap())); }
        assert!(trusted_redirect(&Url::parse("https://release-assets.githubusercontent.com/signed?token=test").unwrap()));
        assert!(local_origin(&Url::parse("http://tauri.localhost/").unwrap(), "main"));
        assert!(local_origin(&Url::parse("tauri://localhost/").unwrap(), "main"));
        for url in ["https://diracmagic.github.io/", "http://localhost/", "https://evil.example/"] { assert!(!local_origin(&Url::parse(url).unwrap(), "main")); }
        assert!(!local_origin(&Url::parse("tauri://localhost/").unwrap(), "secondary"));
    }
    #[test] fn downloaded_bytes_must_match_exact_size_and_digest() {
        let bytes = b"installer fixture"; let hash = format!("{:x}", Sha256::digest(bytes)); let mut out = Vec::new();
        assert!(copy_checked(&mut &bytes[..], &mut out, bytes.len() as u64, &hash).is_ok()); assert_eq!(out, bytes);
        assert!(copy_checked(&mut &bytes[..], &mut Vec::new(), bytes.len() as u64 - 1, &hash).is_err());
        assert!(copy_checked(&mut &bytes[..], &mut Vec::new(), bytes.len() as u64 + 1, &hash).is_err());
        assert!(copy_checked(&mut &bytes[..], &mut Vec::new(), bytes.len() as u64, &"0".repeat(64)).is_err());
    }
    #[test] fn modified_cached_installer_cannot_be_launched() {
        let directory = tempfile::tempdir().unwrap(); let bytes = b"installer fixture";
        let path = directory.path().join(installer_name("windows").unwrap()); fs::write(&path, bytes).unwrap();
        let ready = Ready { info: DownloadInfo { download_id: uuid::Uuid::new_v4().to_string(), version: "1.2.3".into(), platform: "windows".into(), size: bytes.len() as u64 }, directory, hash: format!("{:x}", Sha256::digest(bytes)), launched: false };
        assert!(verified_file(&ready).is_ok());
        fs::write(path, b"tampered contents").unwrap(); assert!(verified_file(&ready).is_err());
    }
    #[test] fn cached_download_is_reverified_and_invalid_cache_is_refetched() {
        let ready = cached_fixture(); let id = ready.info.download_id.clone();
        let reused = downloaded_or_cached(Some(ready), "1.2.3", "windows", || panic!("valid cache must be reused")).unwrap();
        assert_eq!(reused.info.download_id, id);
        for deleted in [false, true] {
            let ready = cached_fixture(); let old_id = ready.info.download_id.clone();
            let old_dir = ready.directory.path().to_owned();
            let path = old_dir.join(installer_name("windows").unwrap());
            if deleted { fs::remove_file(path).unwrap(); } else { fs::write(path, b"tampered contents").unwrap(); }
            let mut fetched = false;
            let replacement = downloaded_or_cached(Some(ready), "1.2.3", "windows", || {
                assert!(!old_dir.exists()); fetched = true; Ok(cached_fixture())
            }).unwrap();
            assert!(fetched); assert_ne!(replacement.info.download_id, old_id);
            assert!(verified_file(&replacement).is_ok());
        }
    }
    #[test] fn failed_install_verification_evicts_cache_and_allows_redownload() {
        let ready = cached_fixture(); let id = ready.info.download_id.clone();
        fs::write(ready.directory.path().join(installer_name("windows").unwrap()), b"tampered contents").unwrap();
        let mut data = DownloadState { busy: false, ready: Some(ready) };
        assert_eq!(install_file(&mut data, &id).unwrap_err(), "update_integrity_failed");
        assert!(data.ready.is_none());
        let mut fetched = false;
        data.ready = Some(downloaded_or_cached(data.ready.take(), "1.2.3", "windows", || { fetched = true; Ok(cached_fixture()) }).unwrap());
        assert!(fetched); assert_ne!(data.ready.as_ref().unwrap().info.download_id, id);
    }
    #[cfg(unix)]
    #[test] fn cached_installer_symlink_is_rejected() {
        let directory = tempfile::tempdir().unwrap(); let bytes = b"installer fixture";
        let target = directory.path().join("other-file"); fs::write(&target, bytes).unwrap();
        std::os::unix::fs::symlink(&target, directory.path().join(installer_name("macos").unwrap())).unwrap();
        let ready = Ready { info: DownloadInfo { download_id: uuid::Uuid::new_v4().to_string(), version: "1.2.3".into(), platform: "macos".into(), size: bytes.len() as u64 }, directory, hash: format!("{:x}", Sha256::digest(bytes)), launched: false };
        assert!(verified_file(&ready).is_err());
    }
}
