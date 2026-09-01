// Assert the heatmap's Location tooltip resolves under both Vega-Lite majors.
//
//   node docs/check_heatmap_tooltip.mjs
//
// The unit tests can only check the shape of the spec. This runs it: it builds
// the chart, compiles it with Vega-Lite 5 and 6, executes the dataflow, and
// reads the tooltip value off the rendered scenegraph -- the same value the
// browser shows on hover, without needing a browser.
//
// Both majors matter because the front-ends do not agree. dash-vega-components
// renders with Vega 5, marimo bundles Vega 6, and issue #27 was a tooltip that
// read "undefined" under 6 only, while every test and the Dash app stayed green.
//
// vega and vega-lite are installed into a temporary directory on each run, so
// the repo keeps its zero-npm-dependency setup.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = fileURLToPath(new URL('..', import.meta.url));
const MAJORS = (process.env.VEGA_MAJORS || '5,6').split(',');

const GEN = `
import json
import altair as alt, pandas as pd, numpy as np
from earthquake_dashboard.visualizer import DataVisualizer
n = 200
rng = np.random.default_rng(0)
df = pd.DataFrame({
    'place': [f'{i} km SE of Somewhere' for i in range(n)],
    'time': pd.to_datetime(pd.date_range('2026-01-01', periods=n, freq='4h'), utc=True),
    'lat': rng.uniform(-60, 60, n), 'lon': rng.uniform(-180, 180, n),
    'mag': rng.uniform(2, 8, n), 'sig': rng.integers(50, 900, n),
    'depth': rng.uniform(-10, 700, n), 'tsunami': rng.integers(0, 2, n).astype(bool),
    'cdi': rng.uniform(0, 9, n), 'alert': rng.choice(['green', 'yellow'], n),
}).astype({'sig': 'int64'})
chart = DataVisualizer(df).create_heatmap(
    filters=[alt.selection_interval(name='b')], width=400, height=300,
    color_var='max(mag)').add_params(alt.selection_interval(name='b'))
print(json.dumps(chart.to_dict()))
`;

console.log('building the heatmap spec');
const specJson = execFileSync('pixi', ['run', '--manifest-path', join(REPO, 'pixi.toml'), 'python', '-c', GEN],
  { cwd: REPO, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })
  .split('\n').filter(l => l.startsWith('{')).pop();
const spec = JSON.parse(specJson);

const dir = mkdtempSync(join(tmpdir(), 'vl-check-'));
writeFileSync(join(dir, 'spec.json'), specJson);

// Run inside the temp directory so plain `import 'vega-lite'` resolves, rather
// than guessing at build filenames that differ between majors.
const PROBE = `
import * as vl from 'vega-lite';
import * as vega from 'vega';
import fs from 'node:fs';
const spec = JSON.parse(fs.readFileSync('./spec.json', 'utf8'));
const errors = [];
const view = new vega.View(vega.parse(vl.compile(spec).spec), {
  renderer: 'none',
  logger: { error: m => errors.push(String(m)), warn() {}, info() {}, debug() {}, level() { return this; } },
});
await view.runAsync();
const tooltips = [];
const walk = it => { if (!it) return; if (Array.isArray(it)) return it.forEach(walk);
  if (it.tooltip && typeof it.tooltip === 'object' && 'Location' in it.tooltip) tooltips.push(it.tooltip);
  if (it.items) walk(it.items); };
walk(view.scenegraph().root);
console.log(JSON.stringify({ version: vl.version, tooltips, errors: errors.slice(0, 3) }));
`;
writeFileSync(join(dir, 'probe.mjs'), PROBE);

let failed = false;
for (const major of MAJORS) {
  console.log(`\ninstalling vega-lite@${major}`);
  execFileSync('npm', ['install', '--silent', '--no-audit', '--no-fund',
    `vega@${major}`, `vega-lite@${major}`], { cwd: dir, stdio: 'ignore' });

  const raw = execFileSync('node', ['probe.mjs'], { cwd: dir, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  const { version, tooltips, errors } = JSON.parse(raw.split('\n').filter(l => l.startsWith('{')).pop());

  const bad = tooltips.filter(t => !t.Location || t.Location === 'undefined' || t.Location === 'null');
  console.log(`vega-lite ${version}: ${tooltips.length} cells, ${bad.length} without a location`);
  if (tooltips.length) console.log(`  sample: ${JSON.stringify(tooltips[0])}`);
  if (errors.length) console.log(`  runtime errors: ${errors.join('; ')}`);

  if (!tooltips.length) { console.log('  FAIL: the heatmap produced no Location tooltip at all'); failed = true; }
  else if (bad.length) { console.log(`  FAIL: ${bad.length} cells read "${bad[0].Location}"`); failed = true; }
  else if (errors.length) { console.log('  FAIL: the dataflow logged errors'); failed = true; }
  else console.log('  OK');
}

console.log(failed ? '\nFAILED' : '\nall majors OK');
process.exit(failed ? 1 : 0);
