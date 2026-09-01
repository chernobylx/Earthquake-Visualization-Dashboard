// Minimal Chrome DevTools Protocol client, shared by the figure scripts.
//
// Node >=22 speaks CDP over its built-in WebSocket, so this stays dependency
// free. Callers get a page session with evaluate/wait/screenshot helpers and
// are responsible for calling close().
import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

export const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function openPage({ chrome: chromePath = process.env.CHROME, port = 9333,
                                 width = 1600, height = 1000, scale = 2 } = {}) {
  if (!chromePath) throw new Error('set CHROME to a Chrome or Chromium binary');
  const profile = mkdtempSync(join(tmpdir(), 'cdp-'));
  const chrome = spawn(chromePath, [
    '--headless', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
    `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    'about:blank',
  ], { stdio: 'ignore' });

  let browserWsUrl = null;
  for (let i = 0; i < 60 && !browserWsUrl; i++) {
    try {
      browserWsUrl = (await (await fetch(`http://127.0.0.1:${port}/json/version`)).json()).webSocketDebuggerUrl;
    } catch { await sleep(500); }
  }
  if (!browserWsUrl) { chrome.kill(); throw new Error('Chrome devtools endpoint never came up'); }

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
  await S('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: scale, mobile: false });

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

  // Trusted key events — synthetic ones re-render a slider without pushing the
  // new value into the app's callback state.
  async function pressKey(key, code, vk, times = 1) {
    for (let i = 0; i < times; i++) {
      await S('Input.dispatchKeyEvent', { type: 'rawKeyDown', key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
      await S('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
      await sleep(40);
    }
  }

  async function shoot(path, clipExpr) {
    const params = { format: 'png', captureBeyondViewport: true };
    if (clipExpr) {
      const box = await evalJs(clipExpr);
      if (!box) throw new Error('no clip box for ' + path);
      // clip.scale multiplies on top of deviceScaleFactor — keep it at 1 so the
      // output is a crisp 2x, not a bloated 4x.
      params.clip = { x: box.x, y: box.y, width: box.w, height: box.h, scale: 1 };
    }
    const { data } = await S('Page.captureScreenshot', params);
    writeFileSync(path, Buffer.from(data, 'base64'));
    console.log(`  wrote ${path}`);
  }

  const goto = url => S('Page.navigate', { url });
  const close = () => { ws.close(); chrome.kill(); };

  return { S, evalJs, waitFor, pressKey, shoot, goto, close };
}
