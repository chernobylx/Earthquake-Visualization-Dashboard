// Regenerate the README figures by driving the running dashboard with headless Chrome.
//
//   pixi run app                  # in one shell
//   node docs/make_figures.mjs    # in another
//
// Env overrides: CHROME (path to chrome.exe), BASE (app url), OUTDIR (where PNGs go),
// MIN_MAG (query floor).
// Zero dependencies — Node >=22 speaks CDP over its built-in WebSocket.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openPage, sleep } from './cdp.mjs';

const BASE = process.env.BASE || 'http://127.0.0.1:8050';
// Default to docs/figures/ next to this script (fileURLToPath handles the
// leading-slash-before-drive-letter quirk of Windows file: URLs).
const OUTDIR = process.env.OUTDIR || fileURLToPath(new URL('./figures/', import.meta.url));
const TARGET_MIN_MAG = parseFloat(process.env.MIN_MAG ?? '2.5');

const page = await openPage({ port: 9333, width: 1600, height: 1000, scale: 2 });
const { evalJs, waitFor, pressKey, goto } = page;
const shoot = (name, clip) => page.shoot(join(OUTDIR, name), clip);

// ---------- drive the app ----------
console.log('navigating to /dashboard');
await goto(`${BASE}/dashboard`);
await waitFor(`document.getElementById('load_button')`, 'controls to build');
await sleep(2000);

// Widen the query: walk the magnitude slider's lower thumb down with real arrow keys.
const startMag = parseFloat(await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').getAttribute('aria-valuenow')`));
// Walk in whichever direction the target lies: the shipped default floor has
// moved before, and a one-way loop silently pressed nothing when it went below
// the target, leaving the figures at the wrong magnitude.
const steps = Math.round(Math.abs(startMag - TARGET_MIN_MAG) / 0.1);
const up = TARGET_MIN_MAG > startMag;
console.log(`moving min magnitude ${startMag} -> ${TARGET_MIN_MAG} (${steps} ${up ? 'right' : 'left'} presses)`);
await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').focus()`);
await pressKey(up ? 'ArrowRight' : 'ArrowLeft', up ? 'ArrowRight' : 'ArrowLeft', up ? 39 : 37, steps);
await sleep(1200);
const nowMag = await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').getAttribute('aria-valuenow')`);
console.log(`  slider now reads ${nowMag}`);
// Fail loudly rather than shooting the figures at the wrong magnitude: a
// synthetic value change re-renders the thumb without reaching Dash's state.
if (Math.abs(parseFloat(nowMag) - TARGET_MIN_MAG) > 0.051) {
  throw new Error(`magnitude slider reads ${nowMag}, expected ${TARGET_MIN_MAG}`);
}

console.log('clicking Count');
await evalJs(`document.getElementById('count_button').click()`);
// Accept both the old and current count copy: the tile said "Found N earthquakes"
// before the controls were relabelled and says "N events match" now.
await waitFor(`/(Found \\d+ earthquakes|[\\d,]+ events match)/.test((document.getElementById('count_output')||{}).innerText||'')`, 'count result');
const countText = await evalJs(`document.getElementById('count_output').innerText.trim()`);
// Rendered with thousands separators, so "2,251 events match" must not parse as 2.
const n = parseInt(countText.match(/[\d,]+/)[0].replace(/,/g, ''), 10);
console.log(`  ${countText}`);
if (n <= 20) {
  throw new Error(`magnitude change did not reach Dash state (count still ${n}); aborting rather than shipping a sparse figure`);
}

console.log('clicking Load');
await evalJs(`document.getElementById('load_button').click()`);
await waitFor(`document.querySelectorAll('#data_table tbody tr').length > 5`, 'table rows', 240000);
await sleep(3000); // let the table render before the chart is waited on

console.log(`  ${await evalJs(`document.querySelectorAll('#data_table tbody tr').length`)} rows in table`);

// The chart draws itself once the table has rows; there is no button to press.
// It is found by class because dash-vega-components never puts the Dash id on
// the DOM.
const CHART = '#visualizer_output .linked-views svg';
await waitFor(`document.querySelector('${CHART}')`, 'vega svg', 300000);
await waitFor(`document.querySelectorAll('#chart_controls .vega-bind').length > 0`, 'chart controls', 60000);
await sleep(5000); // let vega settle its final layout pass
console.log(`  ${await evalJs(`document.querySelectorAll('${CHART} path').length`)} marks rendered`);

console.log('capturing app-ui.png');
await evalJs(`window.scrollTo(0,0)`);
await sleep(500);
// Header, query, table and the chart's controls; the chart itself is the
// other figure.
await shoot('app-ui.png', `(() => {
  const p = document.getElementById('visualizer_control_panel');
  if (!p) return null;
  const r = p.getBoundingClientRect();
  return { x: 0, y: 0,
           w: document.documentElement.clientWidth,
           h: Math.ceil(r.bottom + window.scrollY + 2) };
})()`);

console.log('capturing dashboard.png (chart only)');
await shoot('dashboard.png', `(() => {
  const s = document.querySelector('${CHART}');
  if (!s) return null;
  const r = s.getBoundingClientRect();
  return { x: r.x + window.scrollX, y: r.y + window.scrollY, w: Math.ceil(r.width), h: Math.ceil(r.height) };
})()`);

console.log('done');
page.close();
process.exit(0);
