import { AuthError, REPOSITORY_ID, OWNER_ID, demand, encoder, hexHash, plainObject } from './security.mjs';

const PARTS = ['external-research-memo/part-01.json', 'external-research-memo/part-02.json', 'external-research-memo/part-03.json'];
const TEXT_FIELDS = ['id', 'heading', 'short', 'year', 'stage', 'headline', 'team', 'publication', 'result', 'boundary', 'reference_point', 'title', 'doi', 'category', 'evidence_type', 'pressure', 'tc_criterion', 'verified_version', 'reviewed_on'];
const text = (value, maximum = 12000) => {
  demand(typeof value === 'string' && value.length <= maximum && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value), 'invalid_memo', 502);
  return value;
};
function safeUrl(value) {
  text(value, 2048);
  try {
    const url = new URL(value);
    demand(url.protocol === 'https:' && !url.username && !url.password, 'invalid_memo', 502);
    return value;
  } catch { throw new AuthError('invalid_memo', 502); }
}
function entry(value) {
  demand(plainObject(value), 'invalid_memo', 502);
  const out = {};
  for (const field of TEXT_FIELDS) {
    // Research programmes can legitimately have no DOI; do not invent one.
    if (field === 'doi' && value[field] === null) continue;
    if (Object.hasOwn(value, field)) out[field] = text(value[field]);
  }
  demand(/^[A-Za-z0-9_-]{1,40}$/.test(out.id || '') && out.heading && out.title && out.result && typeof out.boundary === 'string', 'invalid_memo', 502);
  if (value.url) out.url = safeUrl(value.url);
  demand(Array.isArray(value.primary_refs) && value.primary_refs.length >= 1 && value.primary_refs.length <= 24, 'invalid_memo', 502);
  out.primary_refs = value.primary_refs.map(ref => {
    demand(plainObject(ref), 'invalid_memo', 502);
    const clean = { url: safeUrl(ref.url) };
    for (const field of ['label', 'title', 'doi']) if (Object.hasOwn(ref, field)) clean[field] = text(ref[field], 1000);
    demand(clean.label || clean.title, 'invalid_memo', 502); return clean;
  });
  demand(Array.isArray(value.progress_steps) && value.progress_steps.length <= 12, 'invalid_memo', 502);
  out.progress_steps = value.progress_steps.map(step => {
    demand(plainObject(step) && ['completed', 'current', 'not_reported'].includes(step.status), 'invalid_memo', 502);
    const clean = { label: text(step.label, 200), detail: text(step.detail), status: step.status };
    if (Object.hasOwn(step, 'kind')) clean.kind = text(step.kind, 100);
    return clean;
  });
  if (Object.hasOwn(value, 'extra')) {
    demand(Array.isArray(value.extra) && value.extra.length <= 24, 'invalid_memo', 502);
    out.extra = value.extra.map(pair => {
      demand(Array.isArray(pair) && pair.length === 2, 'invalid_memo', 502);
      return [text(pair[0], 1000), safeUrl(pair[1])];
    });
  }
  return out;
}
async function content(api, token, base, path, commit, maximum) {
  const object = await api(base + '/contents/' + path + '?ref=' + commit, token, Math.ceil(maximum * 1.5) + 16384);
  demand(plainObject(object) && object.type === 'file' && object.path === path && object.encoding === 'base64' && /^[a-f0-9]{40}$/.test(object.sha || ''), 'invalid_memo', 502);
  demand(Number.isSafeInteger(object.size) && object.size >= 1 && object.size <= maximum && typeof object.content === 'string', 'invalid_memo', 502);
  const encoded = object.content.replace(/[\r\n]/g, '');
  demand(/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(encoded), 'invalid_memo', 502);
  const decoded = atob(encoded);
  const bytes = Uint8Array.from(decoded, char => char.charCodeAt(0));
  demand(bytes.length === object.size && bytes.length <= maximum && btoa(decoded) === encoded, 'invalid_memo', 502);
  const prefix = encoder.encode('blob ' + bytes.length + '\0');
  const blob = new Uint8Array(prefix.length + bytes.length); blob.set(prefix); blob.set(bytes, prefix.length);
  demand(await hexHash(blob, 'SHA-1') === object.sha, 'invalid_memo', 502);
  let data;
  try { data = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); } catch { throw new AuthError('invalid_memo', 502); }
  return { bytes, data };
}

export async function verifyMemoRepository(api, token, options = {}) {
  const repository = await api('/repositories/' + REPOSITORY_ID, token);
  // Installation grants are independently pinned/read-only before this internal
  // path is used. Getrepo's user-role permissions can all be false for App tokens;
  // authorization instead comes from the verified grant and actual Contents reads.
  const pull = repository.permissions?.pull;
  const readable = pull === true || options.trustedInstallation === true;
  demand(repository.id === REPOSITORY_ID && repository.private === true && repository.owner?.id === OWNER_ID && repository.full_name === 'diracmagic/supercon-research-notes' && readable, 'memo_unavailable', 403);
}

export async function verifyMemoAccess(api, token, options) {
  await verifyMemoRepository(api, token, options);
  // Repository metadata can remain readable after Contents permission is revoked.
  // Probe only the fixed, bounded manifest; never return it in session metadata.
  await content(api, token, '/repos/diracmagic/supercon-research-notes', 'data/external_research_memo.json', 'main', 32768);
}

export async function readMemo(api, token, options) {
  await verifyMemoRepository(api, token, options);
  const base = '/repos/diracmagic/supercon-research-notes';
  // Resolve the small ref object, not a commit response containing file patches.
  const reference = await api(base + '/git/ref/heads/main', token);
  demand(reference?.object?.type === 'commit' && /^[a-f0-9]{40}$/.test(reference.object.sha || ''), 'invalid_memo', 502);
  const commit = reference.object.sha;
  const { data: manifest } = await content(api, token, base, 'data/external_research_memo.json', commit, 32768);
  demand(plainObject(manifest) && manifest.schema_version === 1 && manifest.language === 'en', 'invalid_memo', 502);
  demand(JSON.stringify(manifest.entry_parts) === JSON.stringify(PARTS), 'invalid_memo', 502);
  demand(Number.isSafeInteger(manifest.entry_count) && manifest.entry_count >= 1 && manifest.entry_count <= 250, 'invalid_memo', 502);
  const hashes = manifest.translation?.part_sha256;
  demand(plainObject(hashes) && Object.keys(hashes).length === PARTS.length && PARTS.every(part => /^[a-f0-9]{64}$/.test(hashes[part] || '')), 'invalid_memo', 502);
  const entries = [];
  for (const part of PARTS) {
    const { bytes, data } = await content(api, token, base, 'data/' + part, commit, 131072);
    demand(await hexHash(bytes) === hashes[part], 'invalid_memo', 502);
    demand(plainObject(data) && data.schema_version === 1 && Array.isArray(data.entries) && data.entries.length <= 100, 'invalid_memo', 502);
    entries.push(...data.entries.map(entry));
  }
  demand(entries.length === manifest.entry_count && new Set(entries.map(item => item.id)).size === entries.length, 'invalid_memo', 502);
  return { entries, reviewed_on: text(manifest.reviewed_on, 100), updated: text(manifest.updated, 100), entry_count: entries.length };
}
