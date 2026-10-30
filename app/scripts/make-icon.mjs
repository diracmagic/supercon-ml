// Draws the app icon as a 1024x1024 PNG with no dependencies.
// The mark is a resistance-temperature curve: zero below Tc, a sharp rise,
// then the normal state. `npx tauri icon` turns the PNG into every platform icon.
// Usage: node scripts/make-icon.mjs app-icon.png [size] [full]
// `full` fills the whole square (for iOS and Android maskable icons, which add their own mask).
import { writeFileSync } from 'node:fs';
import { deflateSync } from 'node:zlib';

const D = 1024; // design grid
const SIZE = Number(process.argv[3]) || D;
const SCALE = D / SIZE; // design units per output pixel
const out = process.argv[2] || 'app-icon.png';

const TILE = process.argv[4] === 'full' ? { inset: 0, radius: 0 } : { inset: 72, radius: 210 };
const TOP_LEFT = [0x0d, 0x36, 0x6b];
const BOTTOM_RIGHT = [0x39, 0x87, 0xe5];
const CURVE = [
  [250, 690], [455, 690], [478, 676], [494, 630], [506, 540],
  [518, 462], [536, 432], [566, 420], [790, 336],
];
const STROKE = 30; // half width in px

function roundedRectDistance(x, y) {
  const c = D / 2;
  const half = c - TILE.inset;
  const qx = Math.abs(x - c) - (half - TILE.radius);
  const qy = Math.abs(y - c) - (half - TILE.radius);
  const ox = Math.max(qx, 0);
  const oy = Math.max(qy, 0);
  return Math.hypot(ox, oy) + Math.min(Math.max(qx, qy), 0) - TILE.radius;
}

function segmentDistance(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function curveDistance(x, y) {
  let d = Infinity;
  for (let i = 0; i < CURVE.length - 1; i++) {
    const [ax, ay] = CURVE[i];
    const [bx, by] = CURVE[i + 1];
    d = Math.min(d, segmentDistance(x, y, ax, ay, bx, by));
  }
  return d - STROKE;
}

const coverage = (d) => Math.max(0, Math.min(1, 0.5 - d));

const rowBytes = SIZE * 4 + 1;
const raw = Buffer.alloc(rowBytes * SIZE);
for (let y = 0; y < SIZE; y++) {
  raw[y * rowBytes] = 0; // PNG filter: none
  for (let x = 0; x < SIZE; x++) {
    const px = (x + 0.5) * SCALE;
    const py = (y + 0.5) * SCALE;
    const tile = coverage(roundedRectDistance(px, py) / SCALE);
    const o = y * rowBytes + 1 + x * 4;
    if (tile === 0) continue; // stays transparent
    const g = Math.max(0, Math.min(1, (px + py) / (2 * D)));
    let r = TOP_LEFT[0] + (BOTTOM_RIGHT[0] - TOP_LEFT[0]) * g;
    let gr = TOP_LEFT[1] + (BOTTOM_RIGHT[1] - TOP_LEFT[1]) * g;
    let b = TOP_LEFT[2] + (BOTTOM_RIGHT[2] - TOP_LEFT[2]) * g;
    const ink = coverage(curveDistance(px, py) / SCALE);
    r += (255 - r) * ink;
    gr += (255 - gr) * ink;
    b += (255 - b) * ink;
    raw[o] = Math.round(r);
    raw[o + 1] = Math.round(gr);
    raw[o + 2] = Math.round(b);
    raw[o + 3] = Math.round(tile * 255);
  }
}

const CRC_TABLE = new Uint32Array(256).map((_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let crc = 0xffffffff;
  for (const byte of buf) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

const header = Buffer.alloc(13);
header.writeUInt32BE(SIZE, 0);
header.writeUInt32BE(SIZE, 4);
header[8] = 8; // bit depth
header[9] = 6; // RGBA
header[10] = 0;
header[11] = 0;
header[12] = 0;

const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk('IHDR', header),
  chunk('IDAT', deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0)),
]);
writeFileSync(out, png);
console.log(`wrote ${out} (${png.length} bytes)`);
