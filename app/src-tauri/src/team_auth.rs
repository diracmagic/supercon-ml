//! A memory-only session bridge. The hosted app may complete one local sign-in;
//! only the bundled app can subsequently make narrowly scoped team requests.
//! Neither a bearer token nor a caller-controlled destination leaves this module.
use reqwest::{blocking::Client, redirect::Policy, Url};
use serde::Serialize;
use serde_json::Value;
use std::{collections::HashSet, io::Read, sync::{Arc, Mutex}, time::{Duration, SystemTime, UNIX_EPOCH}};
use tauri::{State, WebviewWindow};

const LOGIN_URL: &str = "https://diracmagic.github.io/supercon-ml/?team_login=email";
const WORKER: &str = "https://supercon-team-auth.diracmagics.workers.dev";
const ORIGIN: &str = "https://diracmagic.github.io";
const ATTEMPT_TTL: u64 = 20 * 60 * 1000;
const SESSION_TTL: u64 = 60 * 60 * 1000;
const MAX_BODY: usize = 12_288;
const MAX_RESPONSE: u64 = 2 * 1024 * 1024;
type Result<T> = std::result::Result<T, String>;
type Shared = Arc<Mutex<AuthState>>;
fn error(code: &str) -> String { code.to_owned() }
fn now() -> u64 { SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_millis().min(u64::MAX as u128) as u64 }

#[derive(Default)]
pub struct TeamAuthState(Shared);
#[derive(Default)]
struct AuthState { epoch: u64, pending: Option<Attempt>, session: Option<Session> }
struct Attempt { expires_at: u64, completing: bool }
struct Session { token: String, expires_at: u64 }
struct Snapshot { epoch: u64, token: String }
#[derive(Serialize)]
pub struct SignInStart { url: &'static str }
#[derive(Serialize)]
pub struct SignInComplete { local_url: &'static str }
#[derive(Serialize)]
pub struct NativeResponse { status: u16, body: String }

impl AuthState {
    fn clear(&mut self) { self.epoch = self.epoch.wrapping_add(1); self.pending = None; self.session = None; }
    fn expire(&mut self, time: u64) {
        if self.pending.as_ref().is_some_and(|value| value.expires_at <= time)
            || self.session.as_ref().is_some_and(|value| value.expires_at <= time) { self.clear(); }
    }
    fn begin(&mut self, time: u64) -> u64 {
        // Another explicit local attempt cancels every older attempt/request.
        self.clear();
        self.pending = Some(Attempt { expires_at: time.saturating_add(ATTEMPT_TTL), completing: false });
        self.epoch
    }
    fn claim(&mut self, time: u64) -> Result<u64> {
        self.expire(time);
        let pending = self.pending.as_mut().ok_or_else(|| error("team_sign_in_not_started"))?;
        if pending.completing { return Err(error("team_sign_in_busy")); }
        pending.completing = true;
        Ok(self.epoch)
    }
    fn finish(&mut self, epoch: u64, token: String, expires_at: u64, time: u64) -> Result<u64> {
        self.expire(time);
        if self.epoch != epoch || !self.pending.as_ref().is_some_and(|value| value.completing)
            || expires_at <= time { return Err(error("team_sign_in_cancelled")); }
        // The attempt's timer cannot expire this newly established session.
        self.epoch = self.epoch.wrapping_add(1);
        self.session = Some(Session { token, expires_at }); self.pending = None;
        Ok(self.epoch)
    }
    fn retry_completion(&mut self, epoch: u64, time: u64) {
        self.expire(time);
        if self.epoch == epoch { if let Some(pending) = self.pending.as_mut() { pending.completing = false; } }
    }
    fn snapshot(&mut self, time: u64) -> Option<Snapshot> {
        self.expire(time);
        self.session.as_ref().map(|value| Snapshot { epoch: self.epoch, token: value.token.clone() })
    }
    fn current(&mut self, epoch: u64, time: u64) -> bool {
        self.expire(time); self.epoch == epoch && self.session.is_some()
    }
}

fn local(url: &Url, label: &str) -> bool {
    label == "main" && url.username().is_empty() && url.password().is_none() && url.port().is_none()
        && ((url.scheme() == "tauri" && url.host_str() == Some("localhost"))
        || (matches!(url.scheme(), "http" | "https") && url.host_str() == Some("tauri.localhost")))
}
fn hosted(url: &Url, label: &str) -> bool {
    label == "main" && url.scheme() == "https" && url.host_str() == Some("diracmagic.github.io")
        && url.username().is_empty() && url.password().is_none() && url.port().is_none() && url.path() == "/supercon-ml/"
}
fn authorize(window: &WebviewWindow, remote: bool) -> Result<()> {
    let url = window.url().map_err(|_| error("team_origin_denied"))?;
    if if remote { hosted(&url, window.label()) } else { local(&url, window.label()) } { Ok(()) }
    else { Err(error("team_origin_denied")) }
}
fn local_home() -> &'static str {
    if cfg!(target_os = "windows") { "http://tauri.localhost/" } else { "tauri://localhost/" }
}
fn token_valid(token: &str) -> bool {
    token.len() == 43 && token.bytes().all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}
fn text_valid(value: &Value, max: usize, multiline: bool) -> bool {
    value.as_str().is_some_and(|text| text.encode_utf16().count() <= max && text.chars().all(|c| {
        !c.is_control() || (multiline && matches!(c, '\n' | '\r' | '\t'))
    }))
}
fn board_query(path: &str) -> bool {
    if path == "/api/board" { return true; }
    let Some(query) = path.strip_prefix("/api/board?") else { return false; };
    if query.is_empty() { return false; }
    let mut seen = HashSet::new();
    for pair in query.split('&') {
        let Some((key, value)) = pair.split_once('=') else { return false; };
        if !matches!(key, "after" | "before" | "limit") || !seen.insert(key) || value.is_empty()
            || !value.bytes().all(|b| b.is_ascii_digit()) || (value.len() > 1 && value.starts_with('0')) { return false; }
        let Ok(number) = value.parse::<u64>() else { return false; };
        if number > 9_007_199_254_740_991 || (key == "before" && number == 0)
            || (key == "limit" && !(1..=50).contains(&number)) { return false; }
    }
    !(seen.contains("before") && seen.contains("after"))
}
fn request_body(path: &str, method: &str, body: Option<Value>) -> Result<Option<String>> {
    if path.len() > 160 { return Err(error("team_request_denied")); }
    let body = body.filter(|value| !value.is_null());
    if method == "GET" && body.is_none() && (matches!(path, "/api/session" | "/api/memo" | "/api/presence" | "/api/team") || board_query(path)) { return Ok(None); }
    if method == "POST" && path == "/auth/logout" && body.is_none() { return Ok(None); }
    if method != "POST" { return Err(error("team_request_denied")); }
    let body = body.ok_or_else(|| error("team_request_denied"))?;
    let fields = body.as_object().ok_or_else(|| error("team_request_denied"))?;
    let valid = match path {
        "/api/board" => fields.len() == 1 && fields.get("body").is_some_and(|v| text_valid(v, 2000, true) && v.as_str().is_some_and(|s| !s.trim().is_empty())),
        "/api/team/revoke" => fields.len() == 1 && fields.get("member_id").and_then(Value::as_str).is_some_and(token_valid),
        "/api/team/name" => fields.len() == 2 && fields.get("member_id").and_then(Value::as_str).is_some_and(token_valid)
            && fields.get("name").is_some_and(|v| text_valid(v, 80, false)),
        "/api/team/invite" => fields.keys().all(|key| matches!(key.as_str(), "email" | "name"))
            && fields.get("email").is_some_and(|v| text_valid(v, 254, false) && v.as_str().is_some_and(|s| !s.trim().is_empty()))
            && fields.get("name").is_none_or(|v| text_valid(v, 80, false)),
        _ => false,
    };
    if !valid { return Err(error("team_request_denied")); }
    let bytes = serde_json::to_string(&body).map_err(|_| error("team_request_denied"))?;
    if bytes.len() > MAX_BODY || (path.starts_with("/api/team/") && bytes.len() > 4096) { return Err(error("team_request_denied")); }
    Ok(Some(bytes))
}
fn unavailable() -> NativeResponse { NativeResponse { status: 401, body: "{\"error\":\"invalid_session\"}".to_owned() } }

fn transport(path: &str, method: &str, body: Option<&str>, token: &str) -> Result<NativeResponse> {
    // Path is already allowlisted. Credentials cannot be redirected or sent to a
    // caller-supplied host, and request/response bodies are never logged.
    let client = Client::builder().redirect(Policy::none()).connect_timeout(Duration::from_secs(10))
        .timeout(Duration::from_secs(20)).user_agent("Supercon-Progress/team-session")
        .build().map_err(|_| error("team_unavailable"))?;
    let mut request = if method == "GET" { client.get(format!("{WORKER}{path}")) } else { client.post(format!("{WORKER}{path}")) };
    request = request.bearer_auth(token).header("Origin", ORIGIN).header("Accept", "application/json");
    if let Some(body) = body { request = request.header("Content-Type", "application/json").body(body.to_owned()); }
    let response = request.send().map_err(|_| error("team_unavailable"))?;
    if response.status().is_redirection() || response.content_length().is_some_and(|size| size > MAX_RESPONSE) { return Err(error("team_response_invalid")); }
    let status = response.status().as_u16();
    let mut bytes = Vec::new(); response.take(MAX_RESPONSE + 1).read_to_end(&mut bytes).map_err(|_| error("team_unavailable"))?;
    if bytes.len() as u64 > MAX_RESPONSE { return Err(error("team_response_invalid")); }
    let body = String::from_utf8(bytes).map_err(|_| error("team_response_invalid"))?;
    // All permitted Worker responses are JSON. Reject upstream HTML/errors.
    let _: Value = serde_json::from_str(&body).map_err(|_| error("team_response_invalid"))?;
    Ok(NativeResponse { status, body })
}
fn session_expiry(response: &NativeResponse, time: u64) -> Result<u64> {
    if response.status != 200 { return Err(error("team_session_invalid")); }
    let value: Value = serde_json::from_str(&response.body).map_err(|_| error("team_response_invalid"))?;
    let expires = value.get("expires_at").and_then(Value::as_u64).ok_or_else(|| error("team_response_invalid"))?;
    if expires <= time || expires > time.saturating_add(SESSION_TTL)
        || !value.get("user").is_some_and(Value::is_object)
        || !value.get("can_read_memo").is_some_and(Value::is_boolean)
        || !value.get("can_manage_team").is_some_and(Value::is_boolean) { return Err(error("team_response_invalid")); }
    Ok(expires)
}
fn schedule_expiry(state: Shared, epoch: u64, deadline: u64) {
    // No persisted credential or background refresh. This also removes idle
    // sessions even when the UI makes no further requests.
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_millis(deadline.saturating_sub(now())));
        if let Ok(mut state) = state.lock() { if state.epoch == epoch { state.clear(); } };
    });
}
fn complete<F>(state: &Shared, token: String, time: impl Fn() -> u64, fetch: F) -> Result<(u64, u64)>
where F: FnOnce(&str, &str, Option<&str>, &str) -> Result<NativeResponse> {
    if !token_valid(&token) { return Err(error("team_session_invalid")); }
    let epoch = state.lock().map_err(|_| error("team_unavailable"))?.claim(time())?;
    let verified = fetch("/api/session", "GET", None, &token).and_then(|response| session_expiry(&response, time()));
    let mut lock = state.lock().map_err(|_| error("team_unavailable"))?;
    match verified {
        Ok(expires) => { let session_epoch = lock.finish(epoch, token, expires, time())?; Ok((session_epoch, expires)) }
        Err(reason) => { lock.retry_completion(epoch, time()); Err(reason) }
    }
}
fn execute<F>(state: &Shared, path: &str, method: &str, body: Option<Value>, time: impl Fn() -> u64, fetch: F) -> Result<NativeResponse>
where F: FnOnce(&str, &str, Option<&str>, &str) -> Result<NativeResponse> {
    let body = request_body(path, method, body)?;
    let snapshot = {
        let mut lock = state.lock().map_err(|_| error("team_unavailable"))?;
        let snapshot = lock.snapshot(time());
        if path == "/auth/logout" { lock.clear(); }
        snapshot
    };
    let Some(snapshot) = snapshot else { return Ok(if path == "/auth/logout" { NativeResponse { status: 200, body: "{\"logged_out\":true}".to_owned() } } else { unavailable() }); };
    if path == "/auth/logout" {
        // Local logout is immediate, regardless of backend/network availability.
        let _ = fetch(path, method, body.as_deref(), &snapshot.token);
        return Ok(NativeResponse { status: 200, body: "{\"logged_out\":true}".to_owned() });
    }
    let response = fetch(path, method, body.as_deref(), &snapshot.token);
    let mut lock = state.lock().map_err(|_| error("team_unavailable"))?;
    if !lock.current(snapshot.epoch, time()) { return Ok(unavailable()); }
    let response = response?;
    if matches!(response.status, 401 | 403) { lock.clear(); }
    if path == "/api/session" && response.status == 200 {
        let expires = match session_expiry(&response, time()) { Ok(value) => value, Err(reason) => { lock.clear(); return Err(reason); } };
        if let Some(session) = lock.session.as_mut() { session.expires_at = session.expires_at.min(expires); }
    }
    Ok(response)
}

#[tauri::command]
pub fn begin_team_sign_in(window: WebviewWindow, state: State<'_, TeamAuthState>) -> Result<SignInStart> {
    authorize(&window, false)?;
    let time = now(); let epoch = state.0.lock().map_err(|_| error("team_unavailable"))?.begin(time);
    schedule_expiry(state.0.clone(), epoch, time.saturating_add(ATTEMPT_TTL));
    Ok(SignInStart { url: LOGIN_URL })
}
#[tauri::command]
pub async fn complete_team_sign_in(window: WebviewWindow, state: State<'_, TeamAuthState>, session_token: String) -> Result<SignInComplete> {
    authorize(&window, true)?;
    let shared = state.0.clone(); let for_expiry = shared.clone();
    let (epoch, expires) = tauri::async_runtime::spawn_blocking(move || complete(&shared, session_token, now, transport))
        .await.map_err(|_| error("team_unavailable"))??;
    if !for_expiry.lock().map_err(|_| error("team_unavailable"))?.current(epoch, now()) { return Err(error("team_sign_in_cancelled")); }
    schedule_expiry(for_expiry, epoch, expires);
    authorize(&window, true)?;
    Ok(SignInComplete { local_url: local_home() })
}
#[tauri::command]
pub async fn native_team_request(window: WebviewWindow, state: State<'_, TeamAuthState>, path: String, method: String, body: Option<Value>) -> Result<NativeResponse> {
    authorize(&window, false)?;
    let shared = state.0.clone();
    let response = tauri::async_runtime::spawn_blocking(move || execute(&shared, &path, &method, body, now, transport))
        .await.map_err(|_| error("team_unavailable"))??;
    authorize(&window, false)?;
    Ok(response)
}
#[tauri::command]
pub fn clear_team_session(window: WebviewWindow, state: State<'_, TeamAuthState>) -> Result<()> {
    authorize(&window, false)?;
    state.0.lock().map_err(|_| error("team_unavailable"))?.clear();
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    const TIME: u64 = 1_000_000;
    fn token() -> String { "a".repeat(43) }
    fn shared() -> Shared { Arc::new(Mutex::new(AuthState::default())) }
    fn valid(expires: u64) -> NativeResponse { NativeResponse { status: 200, body: json!({"user":{"id":123,"login":"test"},"expires_at":expires,"can_read_memo":true,"can_manage_team":false}).to_string() } }
    fn signed_in() -> Shared {
        let state = shared(); state.lock().unwrap().begin(TIME);
        complete(&state, token(), || TIME, |p,m,b,t| { assert_eq!((p,m,b,t), ("/api/session","GET",None,token().as_str())); Ok(valid(TIME + 60_000)) }).unwrap(); state
    }
    #[test]
    fn origins_are_exact_and_remote_can_only_complete() {
        for raw in ["tauri://localhost/", "http://tauri.localhost/", "https://tauri.localhost/index.html"] {
            let url = Url::parse(raw).unwrap(); assert!(local(&url,"main")); assert!(!hosted(&url,"main")); assert!(!local(&url,"other"));
        }
        for raw in [LOGIN_URL, "https://diracmagic.github.io/supercon-ml/?login_status=ok#team_ticket=ignored"] {
            let url = Url::parse(raw).unwrap(); assert!(hosted(&url,"main")); assert!(!local(&url,"main")); assert!(!hosted(&url,"other"));
        }
        for raw in ["https://evil.example/", "https://diracmagic.github.io/other/", "https://diracmagic.github.io/supercon-ml/child", "https://diracmagic.github.io:444/supercon-ml/", "https://user@diracmagic.github.io/supercon-ml/", "http://diracmagic.github.io/supercon-ml/", "https://diracmagic.github.io.evil/supercon-ml/", "http://tauri.localhost:80/evil", "tauri://localhost:99/", "http://user@tauri.localhost/", "http://localhost/", "https://tauri.localhost.evil/"] {
            let url = Url::parse(raw).unwrap(); assert!(!hosted(&url,"main"), "{raw}");
            // URL normalizes an explicit default port; it remains the same origin.
            if raw != "http://tauri.localhost:80/evil" { assert!(!local(&url,"main"), "{raw}"); }
        }
    }
    #[test]
    fn routes_do_not_allow_arbitrary_destinations_or_auth_creation() {
        for path in ["/api/session", "/api/memo", "/api/presence", "/api/team", "/api/board", "/api/board?after=0&limit=50", "/api/board?before=1"] { assert!(request_body(path,"GET",None).is_ok()); }
        for path in ["https://evil.example/api/session", "//evil.example/api/session", "/api/session?url=x", "/api/session#x", "/api/board?before=0", "/api/board?limit=51", "/api/board?limit=0", "/api/board?after=01", "/api/board?after=9007199254740992", "/api/board?after=0&before=1", "/api/board?after=1&after=1", "/api/board?after=%31", "/api/board?", "/api/board?url=x", "/api/../session", "/auth/firebase", "/auth/exchange"] { assert!(request_body(path,"GET",None).is_err(), "{path}"); }
        assert!(request_body("/auth/firebase","POST",Some(json!({"token":"x"}))).is_err());
        assert!(request_body("/api/session","POST",None).is_err());
        assert!(request_body("/api/session","GET",Some(json!({}))).is_err());
        assert!(request_body("/api/board","POST",Some(json!({"body":"hello\nteam"}))).is_ok());
        assert!(request_body("/api/board","POST",Some(json!({"body":"x","author":"owner"}))).is_err());
        assert!(request_body("/api/board","POST",Some(json!({"body":"x".repeat(2001)}))).is_err());
        assert!(request_body("/api/board","POST",Some(json!({"body":"\u{0}"}))).is_err());
        assert!(request_body("/api/team/invite","POST",Some(json!({"email":"a@example.org","name":"Name"}))).is_ok());
        assert!(request_body("/api/team/invite","POST",Some(json!({"email":"a@example.org","admin":true}))).is_err());
        assert!(request_body("/api/team/name","POST",Some(json!({"member_id":token(),"name":"Team name"}))).is_ok());
        assert!(request_body("/api/team/revoke","POST",Some(json!({"member_id":token()}))).is_ok());
    }
    #[test]
    fn completion_needs_one_active_attempt_and_verified_session() {
        let state = shared();
        assert!(complete(&state,token(),||TIME,|_,_,_,_| panic!("must not fetch")).is_err());
        state.lock().unwrap().begin(TIME);
        assert!(complete(&state,"bad".into(),||TIME,|_,_,_,_| panic!("must not fetch")).is_err());
        assert!(complete(&state,token(),||TIME,|_,_,_,_| Ok(unavailable())).is_err());
        assert!(state.lock().unwrap().session.is_none());
        complete(&state,token(),||TIME,|_,_,_,_| Ok(valid(TIME+60_000))).unwrap();
        assert!(complete(&state,token(),||TIME,|_,_,_,_| panic!("already consumed")).is_err());
        let output = serde_json::to_string(&SignInComplete {local_url:local_home()}).unwrap(); assert!(!output.contains(&token()));
    }
    #[test]
    fn old_completion_cannot_repopulate_after_clear_or_new_attempt() {
        for replacement in [false,true] {
            let state = shared(); state.lock().unwrap().begin(TIME);
            let result = complete(&state,token(),||TIME,|_,_,_,_| {
                if replacement { state.lock().unwrap().begin(TIME+1); } else { state.lock().unwrap().clear(); }
                Ok(valid(TIME+60_000))
            });
            assert!(result.is_err()); assert!(state.lock().unwrap().session.is_none());
        }
    }
    #[test]
    fn completed_session_has_a_new_epoch_so_attempt_timer_cannot_expire_it() {
        let state = shared(); let attempt_epoch = state.lock().unwrap().begin(TIME);
        let (session_epoch, expires) = complete(&state,token(),||TIME,|_,_,_,_| Ok(valid(TIME+SESSION_TTL))).unwrap();
        assert_ne!(session_epoch,attempt_epoch); assert_eq!(expires,TIME+SESSION_TTL);
        let mut lock = state.lock().unwrap();
        if lock.epoch == attempt_epoch { lock.clear(); }
        assert!(lock.current(session_epoch,TIME+ATTEMPT_TTL));
    }
    #[test]
    fn busy_and_expired_attempts_fail_closed() {
        let mut state = AuthState::default(); state.begin(TIME); state.claim(TIME).unwrap(); assert!(state.claim(TIME).is_err());
        assert!(state.finish(state.epoch,token(),TIME+ATTEMPT_TTL+1,TIME+ATTEMPT_TTL).is_err());
        assert!(state.pending.is_none()); assert!(state.session.is_none());
        for expiry in [TIME, TIME+SESSION_TTL+1] { assert!(session_expiry(&valid(expiry),TIME).is_err()); }
    }
    #[test]
    fn logout_clears_before_network_and_stale_responses_never_return_private_body() {
        let state = signed_in();
        let out = execute(&state,"/auth/logout","POST",None,||TIME,|_,_,_,_| { assert!(state.lock().unwrap().session.is_none()); Err(error("offline")) }).unwrap();
        assert_eq!(out.status,200); assert!(state.lock().unwrap().session.is_none());
        let state = signed_in();
        let out = execute(&state,"/api/memo","GET",None,||TIME,|_,_,_,_| {
            state.lock().unwrap().clear(); Ok(NativeResponse {status:200,body:"private memo".into()})
        }).unwrap(); assert_eq!(out.status,401); assert!(!out.body.contains("private"));
    }
    #[test]
    fn missing_expired_or_revoked_sessions_are_removed() {
        let state = shared();
        assert_eq!(execute(&state,"/api/session","GET",None,||TIME,|_,_,_,_| panic!("no credentials")).unwrap().status,401);
        let state = signed_in();
        assert_eq!(execute(&state,"/api/session","GET",None,||TIME+60_000,|_,_,_,_| panic!("expired")).unwrap().status,401);
        assert!(state.lock().unwrap().session.is_none());
        let state = signed_in();
        assert_eq!(execute(&state,"/api/memo","GET",None,||TIME,|_,_,_,_| Ok(NativeResponse {status:403,body:"{\"error\":\"membership_revoked\"}".into()})).unwrap().status,403);
        assert!(state.lock().unwrap().session.is_none());
        let state = signed_in();
        execute(&state,"/api/memo","GET",None,||TIME,|_,_,_,_| Ok(NativeResponse {status:429,body:"{\"error\":\"rate_limited\"}".into()})).unwrap();
        assert!(state.lock().unwrap().session.is_some());
    }
    #[test]
    fn capabilities_expose_only_completion_to_fixed_hosted_page() {
        let remote: Value = serde_json::from_str(include_str!("../capabilities/team-sign-in.json")).unwrap();
        assert_eq!(remote["local"],false);
        assert_eq!(remote["remote"]["urls"],json!(["https://diracmagic.github.io/supercon-ml/"]));
        assert_eq!(remote["permissions"],json!(["allow-complete-team-sign-in"]));
        let local: Value = serde_json::from_str(include_str!("../capabilities/default.json")).unwrap();
        assert!(local.get("remote").is_none()); assert_eq!(local["local"],true);
        assert!(!local["permissions"].as_array().unwrap().contains(&json!("allow-complete-team-sign-in")));
    }
}
