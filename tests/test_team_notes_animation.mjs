import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const module = { exports: {} };
vm.runInNewContext(fs.readFileSync(new URL('../app/dist/team-auth.js', import.meta.url), 'utf8'), { module });
const { createNoteAnimation } = module.exports;
class Target {
  constructor() { this.events = new Map(); }
  addEventListener(name, fn) { if (!this.events.has(name)) this.events.set(name, new Set()); this.events.get(name).add(fn); }
  removeEventListener(name, fn) { this.events.get(name)?.delete(fn); }
  emit(name) { for (const fn of [...(this.events.get(name) || [])]) fn({ target: this }); }
  get listenerCount() { return [...this.events.values()].reduce((sum, set) => sum + set.size, 0); }
}
class Element extends Target {
  constructor(tag) { super(); this.tagName = tag.toUpperCase(); this.children = []; this.attrs = {}; this._text = ''; this.hidden = false; this.disabled = false; this.open = false; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return this.attrs[key] ?? null; }
  appendChild(child) { this.children.push(child); return child; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_) { throw new Error('Animation content must be text nodes'); }
  all() { return [this, ...this.children.flatMap(child => child.all())]; }
}
const synthetic = () => [
  { label: 'Synthetic data input', detail: 'Invented numeric records for this test.', status: 'completed', kind: 'data' },
  { label: 'Synthetic computation', detail: 'An invented calculation, not a measurement.', status: 'current', kind: 'calculation' },
  { label: 'Experimental validation', detail: 'Not reported in the invented fixture.', status: 'not_reported', kind: 'experiment' }
];
function harness({ steps = synthetic(), reduced = false } = {}) {
  const doc = new Target(); doc.hidden = false;
  doc.createElement = tag => new Element(tag); doc.createElementNS = (_namespace, tag) => new Element(tag);
  const media = new Target(); media.matches = reduced;
  const observers = [], frames = new Map(), callbacks = [];
  let serial = 0, clock = 0;
  const win = { matchMedia: query => { assert.equal(query, '(prefers-reduced-motion: reduce)'); return media; },
    requestAnimationFrame(fn) { const id = ++serial; frames.set(id, fn); callbacks.push(fn); return id; },
    cancelAnimationFrame(id) { frames.delete(id); },
    IntersectionObserver: class {
      constructor(fn) { this.fn = fn; this.disconnected = false; observers.push(this); }
      observe(target) { this.target = target; }
      disconnect() { this.disconnected = true; }
      emit(ratio) { this.fn([{ target: this.target, isIntersecting: ratio > 0, intersectionRatio: ratio }]); }
    }
  };
  const details = new Element('details');
  const animation = createNoteAnimation({ document: doc, window: win, details, steps });
  const byClass = name => animation.node.all().find(node => (node.attrs.class || '').split(' ').includes(name));
  const byLabel = label => animation.node.all().find(node => node.attrs['aria-label'] === label);
  return { animation, doc, media, details, observers, frames, callbacks, byClass, byLabel,
    open() { details.open = true; details.emit('toggle'); observers[0]?.emit(1); },
    advance(milliseconds) { for (let passed = 0; passed <= milliseconds; passed += 100) { clock += 100; const pending = [...frames]; frames.clear(); for (const [, fn] of pending) fn(clock); } },
    play() { animation.node.all().find(node => node.tagName === 'BUTTON' && /research walkthrough/.test(node.attrs['aria-label'] || '')).emit('click'); }
  };
}

test('no recorded steps means no invented research animation or lifecycle listeners', () => {
  for (const steps of [undefined, [], [{ label: 'Unverified', detail: 'Unknown', status: 'successful' }]]) {
    const h = harness({ steps: steps === undefined ? [] : steps });
    assert.equal(h.animation, null); assert.equal(h.doc.listenerCount, 0); assert.equal(h.media.listenerCount, 0);
  }
});

test('walkthrough preserves runtime labels and evidence as text without inventing completion', () => {
  const steps = synthetic(); steps[0].label = '<img src=x onerror=alert(1)>';
  steps[0].detail = '<script>PRIVATE_SYNTHETIC_MARKER</script>';
  const original = JSON.stringify(steps); steps.forEach(Object.freeze); Object.freeze(steps);
  const h = harness({ steps });
  assert.match(h.animation.node.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(h.animation.node.all().some(node => ['IMG', 'SCRIPT'].includes(node.tagName)), false);
  assert.equal(h.byClass('team-note-evidence').textContent, 'Reported');
  h.byLabel('Next research step').emit('click');
  assert.equal(h.byClass('team-note-step-title').textContent, steps[1].label);
  assert.equal(h.byClass('team-note-evidence').textContent, 'Current evidence');
  h.byLabel('Next research step').emit('click');
  assert.equal(h.byClass('team-note-evidence').textContent, 'Not reported');
  assert.equal(h.byClass('team-note-step-detail').textContent, steps[2].detail);
  assert.equal(JSON.stringify(steps), original);
});

test('playback is manual, advances recorded steps once, pauses and can replay', () => {
  const h = harness(); h.observers[0].emit(1); h.play();
  assert.equal(h.frames.size, 0, 'Closed entries cannot animate');
  h.open(); assert.equal(h.frames.size, 0, 'Opening an entry must not autoplay');
  h.play(); assert.equal(h.frames.size, 1); h.advance(3800);
  assert.equal(h.byClass('team-note-counter').textContent, 'Step 2 of 3');
  assert.equal(h.byClass('team-note-evidence').textContent, 'Current evidence');
  h.play(); assert.equal(h.frames.size, 0); h.advance(8000);
  assert.equal(h.byClass('team-note-counter').textContent, 'Step 2 of 3');
  h.play(); h.advance(7500);
  assert.equal(h.frames.size, 0); assert.match(h.byClass('team-note-play-state').textContent, /End of/);
  assert.equal(h.byClass('team-note-evidence').textContent, 'Not reported', 'Animation never upgrades an unreported experiment');
  h.play(); assert.equal(h.byClass('team-note-counter').textContent, 'Step 1 of 3'); assert.equal(h.frames.size, 1);
  h.animation.destroy();
});

test('reduced motion provides a complete static walkthrough with no animation frames', () => {
  const h = harness({ reduced: true }); h.open();
  const play = h.byLabel('Play research walkthrough'); assert.equal(play.hidden, true);
  h.play(); assert.equal(h.frames.size, 0);
  h.byLabel('Next research step').emit('click'); h.byLabel('Next research step').emit('click');
  assert.equal(h.byClass('team-note-counter').textContent, 'Step 3 of 3');
  assert.equal(h.byClass('team-note-evidence').textContent, 'Not reported');
  assert.match(h.byClass('team-note-play-state').textContent, /Static walkthrough/);
  h.animation.destroy();
});

test('offscreen, closed, hidden-document and changed motion preferences stop without auto-resume', () => {
  for (const stop of ['offscreen', 'close', 'hidden', 'reduced']) {
    const h = harness(); h.open(); h.play(); assert.equal(h.frames.size, 1);
    if (stop === 'offscreen') h.observers[0].emit(0);
    if (stop === 'close') { h.details.open = false; h.details.emit('toggle'); }
    if (stop === 'hidden') { h.doc.hidden = true; h.doc.emit('visibilitychange'); }
    if (stop === 'reduced') { h.media.matches = true; h.media.emit('change'); }
    assert.equal(h.frames.size, 0, stop);
    h.doc.hidden = false; h.media.matches = false; h.media.emit('change'); h.open();
    assert.equal(h.frames.size, 0, 'Returning to ' + stop + ' requires explicit playback');
    h.animation.destroy();
  }
});

test('destroy cancels work, clears private text and removes observers and event subscriptions', () => {
  const h = harness(); h.open(); h.play();
  const root = h.animation.node, oldNodes = root.all(), lateFrame = h.callbacks.at(-1);
  h.animation.destroy(); h.animation.destroy();
  assert.equal(h.frames.size, 0); assert.equal(root.textContent, '');
  assert.equal(h.observers[0].disconnected, true);
  assert.equal(h.doc.listenerCount, 0); assert.equal(h.media.listenerCount, 0); assert.equal(h.details.listenerCount, 0);
  assert.ok(oldNodes.every(node => node.listenerCount === 0));
  lateFrame(100000); h.observers[0].emit(1); h.doc.emit('visibilitychange');
  assert.equal(h.frames.size, 0); assert.equal(root.textContent, '');
});
