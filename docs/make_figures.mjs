// Regenerate the README figures by driving the running dashboard with headless Chrome.
//
//   pixi run app                  # in one shell
//   node docs/make_figures.mjs    # in another
//
// Env overrides: CHROME (path to chrome.exe), BASE (app url), OUTDIR (where PNGs go),
// MIN_MAG (query floor), COLOR_VAR / ALPHA_VAR (map encodings).
// Zero dependencies — Node >=22 speaks CDP over its built-in WebSocket.
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const CHROME = process.env.CHROME;
const BASE = process.env.BASE || 'http://127.0.0.1:8050';
// Default to docs/figures/ next to this script (fileURLToPath handles the
// leading-slash-before-drive-letter quirk of Windows file: URLs).
const OUTDIR = process.env.OUTDIR || fileURLToPath(new URL('./figures/', import.meta.url));
const TARGET_MIN_MAG = parseFloat(process.env.MIN_MAG ?? '2.5');
const COLOR_VAR = process.env.COLOR_VAR || 'mag';
const ALPHA_VAR = process.env.ALPHA_VAR || '';
const PORT = 9333;
const W = 1600, H = 1000, SCALE = 2;

const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------- launch ----------
const profile = mkdtempSync(join(tmpdir(), 'cdp-'));
const chrome = spawn(CHROME, [
  '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  'about:blank',
], { stdio: 'ignore' });

let browserWsUrl = null;
for (let i = 0; i < 60; i++) {
  try {
    const r = await fetch(`http://127.0.0.1:${PORT}/json/version`);
    browserWsUrl = (await r.json()).webSocketDebuggerUrl;
    if (browserWsUrl) break;
  } catch { /* not up yet */ }
  await sleep(500);
}
if (!browserWsUrl) { chrome.kill(); throw new Error('Chrome devtools endpoint never came up'); }

// ---------- minimal CDP client ----------
const ws = new WebSocket(browserWsUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let nextId = 1;
const pending = new Map();
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    const { res, rej } = pending.get(m.id); pending.delete(m.id);
    m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
  }
};
function send(method, params = {}, sessionId) {
  const id = nextId++;
  return new Promise((res, rej) => {
    pending.set(id, { res, rej });
    ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('timeout ' + method)); } }, 180000);
  });
}

const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const S = (m, p) => send(m, p, sessionId);

await S('Page.enable');
await S('Runtime.enable');
await S('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: SCALE, mobile: false });

async function evalJs(expression) {
  const r = await S('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' :: ' + expression.slice(0, 120));
  return r.result.value;
}

async function waitFor(expression, label, timeoutMs = 180000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (await evalJs(`!!(${expression})`)) return true;
    await sleep(500);
  }
  throw new Error(`timed out waiting for ${label}`);
}

// Trusted key events — synthetic ones re-render the slider without pushing
// the new value into Dash's callback state.
async function pressKey(key, code, vk, times = 1) {
  for (let i = 0; i < times; i++) {
    await S('Input.dispatchKeyEvent', { type: 'rawKeyDown', key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
    await S('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
    await sleep(40);
  }
}

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
  const now = await evalJs(`(document.querySelector(${JSON.stringify('#' + id + ' .dash-dropdown-value')})||{}).textContent`);
  if (!found || (now || '').trim() !== value) {
    throw new Error(`could not set ${id} to ${value} (reads "${(now || '').trim()}")`);
  }
  console.log(`  ${id} = ${value}`);
}

async function shoot(name, clipExpr) {
  const params = { format: 'png', captureBeyondViewport: true };
  if (clipExpr) {
    const box = await evalJs(clipExpr);
    if (!box) throw new Error('no clip box for ' + name);
    // clip.scale multiplies on top of deviceScaleFactor — keep it at 1 so the
    // output is a crisp 2x, not a bloated 4x.
    params.clip = { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 };
  }
  const { data } = await S('Page.captureScreenshot', params);
  writeFileSync(join(OUTDIR, name), Buffer.from(data, 'base64'));
  console.log(`  wrote ${name}`);
}

// ---------- drive the app ----------
console.log('navigating to /dashboard');
await S('Page.navigate', { url: `${BASE}/dashboard` });
await waitFor(`document.getElementById('load_button')`, 'controls to build');
await sleep(2000);

// Widen the query: walk the magnitude slider's lower thumb down with real arrow keys.
const startMag = parseFloat(await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').getAttribute('aria-valuenow')`));
const steps = Math.round((startMag - TARGET_MIN_MAG) / 0.1);
console.log(`lowering min magnitude ${startMag} -> ${TARGET_MIN_MAG} (${steps} arrow presses)`);
await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').focus()`);
await pressKey('ArrowLeft', 'ArrowLeft', 37, steps);
await sleep(1200);
const nowMag = await evalJs(`document.querySelector('#mag_range_slider [role="slider"]').getAttribute('aria-valuenow')`);
console.log(`  slider now reads ${nowMag}`);

console.log('clicking Count');
await evalJs(`document.getElementById('count_button').click()`);
await waitFor(`/Found \\d+ earthquakes/.test((document.getElementById('count_output')||{}).innerText||'')`, 'count result');
const countText = await evalJs(`document.getElementById('count_output').innerText.trim()`);
const n = parseInt(countText.match(/\d+/)[0], 10);
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
ws.close();
chrome.kill();
process.exit(0);
