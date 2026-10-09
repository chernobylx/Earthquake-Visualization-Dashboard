// Assert the linked-views spec works once Dash has fed it rows.
//
//   node docs/check_linked_views.mjs
//
// tests/test_spec.py checks the spec's shape. This runs it: build_spec() fills
// the template with a synthetic query, Vega-Lite compiles it, and the dataflow
// executes headlessly. It fails on the three things that broke silently while
// the chart was being moved here:
//
//   - a time domain of NaN -> NaN, which is what ISO-string times produce;
//   - camera params that compile but do not move the map;
//   - a map brush that empties a view instead of filtering it, which is what
//     happens when a layer reads its own copy of the data.
//
// Versions are pinned to what dash-vega-components 0.11 bundles, since that is
// the renderer this spec ships to. They install into a temporary directory so
// the repo keeps its zero-npm-dependency setup. The basemap is fetched from
// jsdelivr, so this needs network access.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = fileURLToPath(new URL('..', import.meta.url));
const VEGA = process.env.VEGA || '5.30.0';
const VEGA_LITE = process.env.VEGA_LITE || '5.20.1';

const GEN = `
import json
import numpy as np, pandas as pd
from earthquake_dashboard.spec import build_spec
n = 300
rng = np.random.default_rng(0)
df = pd.DataFrame({
    'place': [f'{i} km SE of Somewhere' for i in range(n)],
    'time': pd.to_datetime(pd.date_range('2026-08-01', periods=n, freq='2h'), utc=True),
    'lat': rng.uniform(-60, 60, n), 'lon': rng.uniform(-180, 180, n),
    'mag': rng.uniform(2, 8, n), 'sig': rng.integers(50, 900, n),
    'depth': rng.uniform(-10, 700, n), 'tsunami': rng.integers(0, 2, n).astype(bool),
    'cdi': rng.uniform(0, 9, n), 'alert': rng.choice(['green', 'yellow'], n),
    'url': [f'https://earthquake.usgs.gov/earthquakes/eventpage/x{i}' for i in range(n)],
}).astype({'sig': 'int64'})
print(json.dumps(build_spec(df)))
`;

console.log('building the spec');
const specJson = execFileSync('pixi', ['run', '--manifest-path', join(REPO, 'pixi.toml'), 'python', '-c', GEN],
  { cwd: REPO, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  .split('\n').filter(l => l.startsWith('{')).pop();

const dir = mkdtempSync(join(tmpdir(), 'vl-linked-'));
writeFileSync(join(dir, 'spec.json'), specJson);

const PROBE = `
import * as vl from 'vega-lite';
import * as vega from 'vega';
import fs from 'node:fs';
const spec = JSON.parse(fs.readFileSync('./spec.json', 'utf8'));
const warnings = [], errors = [];
const compiled = vl.compile(spec, { logger: {
  warn: m => warnings.push(String(m)), info() {}, debug() {}, error: m => errors.push(String(m)), level() { return this; } } }).spec;
const view = new vega.View(vega.parse(compiled), { renderer: 'svg', logger: {
  error: m => errors.push(String(m)), warn() {}, info() {}, debug() {}, level() { return this; } } });
await view.runAsync();

const out = { version: vl.version, warnings, errors };
out.timeExtent = view.signal('timeExtent').map(d => +d);

const paths = async () => [...(await view.toSVG()).matchAll(/<path[^>]*\\bd="([^"]*)"/g)].map(m => m[1]);
const changed = (a, b) => a.reduce((n, p, i) => n + (p !== b[i] ? 1 : 0), 0);
const base = await paths();
out.camera = {};
for (const [name, value] of [['rotate0', 60], ['zoom', 400], ['PROJECTION', 'orthographic']]) {
  view.signal(name, value); await view.runAsync();
  out.camera[name] = changed(base, await paths());
}
// Show every point, so the brush has the whole frame to choose from.
view.signal('rotate0', 0); view.signal('zoom', 200); view.signal('PROJECTION', 'equirectangular');
await view.runAsync();

const marks = [];
(function walk(g) { for (const m of g.marks || []) {
  if (m.from && m.from.data) marks.push({ type: m.type, data: m.from.data });
  if (m.type === 'group') walk(m); } })(compiled);
const points = view.data(marks.find(m => m.type === 'symbol').data);
const lons = points.map(r => r.lon).sort((a, b) => a - b);
const cut = lons[Math.floor(lons.length / 2)];
const store = points.filter(r => r.lon <= cut).sort((a, b) => a._vgsid_ - b._vgsid_);
const rects = marks.filter(m => m.type === 'rect');
const before = rects.map(m => view.data(m.data).length);
view.data('BRUSH_MAP_store', store); await view.runAsync();
const after = rects.map(m => view.data(m.data).length);
out.brush = { selected: store.length, of: points.length, before, after };
console.log(JSON.stringify(out));
`;
writeFileSync(join(dir, 'probe.mjs'), PROBE);

console.log(`installing vega@${VEGA} vega-lite@${VEGA_LITE}`);
execFileSync('npm', ['install', '--silent', '--no-audit', '--no-fund', `vega@${VEGA}`, `vega-lite@${VEGA_LITE}`],
  { cwd: dir, stdio: 'ignore' });
const raw = execFileSync('node', ['probe.mjs'], { cwd: dir, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const r = JSON.parse(raw.split('\n').filter(l => l.startsWith('{')).pop());

const failures = [];
console.log(`\nvega-lite ${r.version}`);

const [t0, t1] = r.timeExtent;
console.log(`  time domain: ${Number.isFinite(t0) ? new Date(t0).toISOString() : t0} -> ${Number.isFinite(t1) ? new Date(t1).toISOString() : t1}`);
if (!Number.isFinite(t0) || !Number.isFinite(t1)) failures.push('the time domain is not a finite range');

for (const [name, n] of Object.entries(r.camera)) {
  console.log(`  ${name}: ${n} paths redrawn`);
  if (n < 100) failures.push(`${name} did not move the map`);
}

const { selected, of, before, after } = r.brush;
console.log(`  map brush on ${selected} of ${of} points:`);
let filtered = 0;
before.forEach((b, i) => {
  const a = after[i];
  const verdict = b > 0 && a === 0 ? 'EMPTIED' : a !== b ? 'filtered' : 'unchanged';
  if (verdict === 'filtered') filtered++;
  if (verdict === 'EMPTIED') failures.push(`a view emptied under the map brush (${b} -> 0)`);
  console.log(`    rect view ${i}: ${String(b).padStart(4)} -> ${String(a).padStart(4)}  ${verdict}`);
});
// The time histogram, the magnitude histogram and the heatmap each have a
// filtered layer; the grey static layers behind them should not move.
if (filtered !== 3) failures.push(`expected 3 views to filter under the map brush, got ${filtered}`);

const noisy = r.warnings.filter(w => !/aggregate function|Cannot project a selection on encoding channel "y"/.test(w));
if (noisy.length) console.log(`  compile warnings:\n    ${[...new Set(noisy)].join('\n    ')}`);
if (r.errors.length) { console.log(`  runtime errors: ${r.errors.join('; ')}`); failures.push('the dataflow logged errors'); }

console.log(failures.length ? `\nFAILED\n  ${failures.join('\n  ')}` : '\nOK');
process.exit(failures.length ? 1 : 0);
