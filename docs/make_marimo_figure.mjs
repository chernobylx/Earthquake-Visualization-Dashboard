// Capture the marimo front-end for the README, the same way make_figures.mjs
// captures the Dash app.
//
//   pixi run -e alt marimo-app          # in one shell
//   node docs/make_marimo_figure.mjs    # in another
//
// Env overrides: CHROME (path to the browser), BASE (app url), OUTDIR.
//
// Two things make marimo harder to drive than Dash. Its widgets live in shadow
// roots, so every query has to descend into them; and the notebook draws
// nothing until Fetch data and Render chart are pressed (issues #17 and #18),
// so the capture has to click, not just wait.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { openPage, sleep } from './cdp.mjs';

const BASE = process.env.BASE || 'http://127.0.0.1:2718';
const OUTDIR = process.env.OUTDIR || fileURLToPath(new URL('./figures/', import.meta.url));

// Injected before every expression: querySelectorAll that walks shadow roots.
const DEEP = `window.__deep = (sel, root = document) => {
  const out = [...root.querySelectorAll(sel)];
  for (const el of root.querySelectorAll('*')) if (el.shadowRoot) out.push(...window.__deep(sel, el.shadowRoot));
  return out;
};`;

const page = await openPage({ port: 9339, width: 1800, height: 1900, scale: 2 });
const { evalJs, waitFor, goto } = page;
const deep = expr => evalJs(`(() => { ${DEEP} return ${expr}; })()`);
const deepWait = (expr, label, ms) => waitFor(`(() => { ${DEEP} return ${expr}; })()`, label, ms);

async function click(label) {
  const ok = await deep(`(() => {
    const b = window.__deep('button').find(b => b.textContent.trim() === ${JSON.stringify(label)});
    if (!b) return false;
    b.scrollIntoView({ block: 'center' });
    b.click();
    return true;
  })()`);
  if (!ok) throw new Error(`no button labelled "${label}"`);
  console.log(`  clicked ${label}`);
}

console.log(`navigating to ${BASE}`);
await goto(BASE);
await deepWait(`window.__deep('button').some(b => b.textContent.trim() === 'Fetch data')`, 'the notebook to render');
await sleep(2000);

await click('Fetch data');
await deepWait(`!document.body.innerText.includes('No data loaded yet')`, 'the USGS query', 300000);
await sleep(6000);

await click('Render chart');
// The dataframe widget draws its own column previews, so wait for a chart wide
// enough to be the dashboard rather than one of those thumbnails.
await deepWait(`window.__deep('.vega-embed').some(e => e.getBoundingClientRect().width > 600)`, 'the chart', 300000);
await sleep(10000);

const marks = await deep(`window.__deep('.vega-embed').sort((a, b) =>
  b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0].querySelectorAll('canvas, svg').length`);
console.log(`  chart rendered (${marks} canvas/svg nodes)`);

// Rewind every scroller first: clicking Render chart scrolls the button into
// view inside marimo's grid container, and the capture would start partway
// down the controls.
await evalJs(`(() => {
  window.scrollTo(0, 0);
  for (const el of document.querySelectorAll('*')) if (el.scrollTop) el.scrollTop = 0;
  return 1;
})()`);
await sleep(1500);

// Shoot the whole app, not just the chart. The grid layout puts the chart in a
// scrollable slot, so clipping to the chart's own box captures a torn-off strip
// of it; the app view also shows what the figure is actually for -- the marimo
// controls beside the same chart the Dash figures show.
await page.shoot(join(OUTDIR, 'marimo-app.png'), `(() => { ${DEEP}
  // Stop at the bottom of the chart: the grid canvas runs on past it, and
  // scrollHeight would pad the figure with a screen of empty white.
  const el = window.__deep('.vega-embed').sort((a, b) =>
    b.getBoundingClientRect().width - a.getBoundingClientRect().width)[0];
  const bottom = el ? el.getBoundingClientRect().bottom + window.scrollY + 12
                    : document.documentElement.scrollHeight;
  return { x: 0, y: 0, w: document.documentElement.clientWidth, h: Math.ceil(bottom) };
})()`);

console.log('done');
page.close();
process.exit(0);
