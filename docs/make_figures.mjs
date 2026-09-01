// Regenerate the README figures by driving the running dashboard with headless Chrome.
//
//   pixi run app                  # in one shell
//   node docs/make_figures.mjs    # in another
//
// Env overrides: CHROME (path to chrome.exe), BASE (app url), OUTDIR (where PNGs go),
// MIN_MAG (query floor), COLOR_VAR / ALPHA_VAR (map encodings).
// Zero dependencies — Node >=22 speaks CDP over its built-in WebSocket.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openPage, sleep } from './cdp.mjs';

const BASE = process.env.BASE || 'http://127.0.0.1:8050';
// Default to docs/figures/ next to this script (fileURLToPath handles the
// leading-slash-before-drive-letter quirk of Windows file: URLs).
const OUTDIR = process.env.OUTDIR || fileURLToPath(new URL('./figures/', import.meta.url));
const TARGET_MIN_MAG = parseFloat(process.env.MIN_MAG ?? '2.5');
const COLOR_VAR = process.env.COLOR_VAR || 'mag';
const ALPHA_VAR = process.env.ALPHA_VAR || '';

const page = await openPage({ port: 9333, width: 1600, height: 1000, scale: 2 });
const { S, evalJs, waitFor, pressKey, goto } = page;
const shoot = (name, clip) => page.shoot(join(OUTDIR, name), clip);

// Dash 4 dropdowns are a button + listbox popup; a real click drives them fine.
async function setDropdown(id, value) {
  await evalJs(`document.getElementById(${JSON.stringify(id)}).click()`);
  await sleep(500);
  const found = await evalJs(`(() => {
    const t = [...document.querySelectorAll('[role="option"]')]
      .find(o => o.textContent.trim() === ${JSON.stringify(value)});
    if (!t) return false;
    t.click();
    return true;
  })()`);
  await sleep(900);
  // Close the listbox: it stays open after the click and would sit over the
  // data table in the screenshot.
  await S('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
  await S('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27, nativeVirtualKeyCode: 27 });
  await evalJs(`document.activeElement && document.activeElement.blur()`);
  await sleep(400);
  const now = await evalJs(`(document.querySelector(${JSON.stringify('#' + id + ' .dash-dropdown-value')})||{}).textContent`);
  if (!found || (now || '').trim() !== value) {
    throw new Error(`could not set ${id} to ${value} (reads "${(now || '').trim()}")`);
  }
  console.log(`  ${id} = ${value}`);
}

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
await sleep(3000); // aesthetics dropdowns repopulate from the new data

console.log(`  ${await evalJs(`document.querySelectorAll('#data_table tbody tr').length`)} rows in table`);

// The aesthetics dropdowns are rebuilt from the freshly loaded frame, so set them now.
// Default Color is depth: with most events shallow, magma renders nearly everything
// black against a dark map. Magnitude spreads across the scale instead.
if (COLOR_VAR) await setDropdown('color_dropdown', COLOR_VAR);
if (ALPHA_VAR) await setDropdown('alpha_dropdown', ALPHA_VAR);

console.log('capturing app-ui.png');
await evalJs(`window.scrollTo(0,0)`);
await sleep(500);
// Stop at the bottom of the visualizer controls — below that is the still-empty
// visualization panel, which would leave most of the frame blank.
await shoot('app-ui.png', `(() => {
  const p = document.getElementById('visualizer_control_panel');
  if (!p) return null;
  const r = p.getBoundingClientRect();
  return { x: 0, y: 0,
           w: document.documentElement.clientWidth,
           h: Math.ceil(r.bottom + window.scrollY + 2) };
})()`);

console.log('clicking Visualize');
await evalJs(`document.getElementById('viz_button').click()`);
await waitFor(`document.querySelector('#visualizer_output svg')`, 'vega svg', 300000);
await waitFor(`document.querySelectorAll('#visualizer_output svg path,#visualizer_output svg rect,#visualizer_output svg circle').length > 200`, 'chart marks', 300000);
await sleep(5000); // let vega settle its final layout pass

console.log(`  ${await evalJs(`document.querySelectorAll('#visualizer_output svg path,#visualizer_output svg rect,#visualizer_output svg circle').length`)} marks rendered`);

console.log('capturing dashboard.png (chart only)');
await shoot('dashboard.png', `(() => {
  const s = document.querySelector('#visualizer_output svg');
  if (!s) return null;
  const r = s.getBoundingClientRect();
  return { x: r.x + window.scrollX, y: r.y + window.scrollY, w: Math.ceil(r.width), h: Math.ceil(r.height) };
})()`);

console.log('done');
page.close();
process.exit(0);
