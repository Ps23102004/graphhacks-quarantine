// Browser checks for the hive page. Only HTTP responses are substituted; the real page, its timers,
// canvas rendering and click/keyboard handlers run unchanged.
//   playwright-cli open http://127.0.0.1:8765
//   playwright-cli run-code --filename scripts/check_browser.js
// Requires the demo seeded with `quarantine session1` (the checks derive their fixtures from it).
async (page) => {
  const url = page.url();
  const graphURL = await page.evaluate(() => location.origin + '/graph');
  const source = await (await page.request.get(graphURL)).json();
  if (source.error || !source.nodes.some(n => n.id === 'a_requirements')) {
    throw new Error('Seed the demo with quarantine session1 before running browser checks.');
  }
  const copy = value => JSON.parse(JSON.stringify(value));
  const clean = copy(source);
  clean.nodes = clean.nodes.filter(n => !n.twin_of).map(n => ({ ...n, red: false, naive_agent: false, naive_time: false }));
  clean.docs.forEach(d => { d.flagged = false; });
  const ids = new Set([...clean.nodes, ...clean.docs].map(n => n.id));
  clean.edges = clean.edges.filter(e => ids.has(e.src) && ids.has(e.dst));
  clean.flagged = null;
  clean.counters = null;
  const redIds = ['ep_7a', 'ep_7b', 'f_http_client', 'f_http_pin', 'step_3', 'a_requirements'];
  const flagged = copy(clean);
  flagged.nodes.forEach(n => {
    n.red = redIds.includes(n.id);
    n.naive_agent = true;                                            // all three agents touched the closure
    n.naive_time = n.tick >= 7;                                      // ep_7a is written at tick 7
  });
  flagged.docs.find(d => d.id === 'doc_7').flagged = true;
  flagged.flagged = 'doc_7';
  flagged.counters = { precise: 6, per_agent: 25, time_based: 19 };
  const healed = copy(flagged);
  ['f_http_client', 'step_3', 'a_requirements'].forEach((id, i) => {
    healed.nodes.push({ ...copy(clean.nodes.find(n => n.id === id)), id: id + '_v2', twin_of: id, tick: 41 + i,
                        naive_agent: false, naive_time: false });
    healed.edges.push({ src: id + '_v2', type: 'SUPERSEDES', dst: id });
  });
  const receipt = { shape: 'path', hops: ['a_requirements', 'step_3', 'f_http_client', 'ep_7a', 'doc_7'], len: 4, length: 4,
    via: ['INFLUENCED_BY', 'INFLUENCED_BY', 'CONSOLIDATED_FROM', 'EXTRACTED_FROM'],
    sentence: 'a_requirements was written after reading step_3, which was written after reading f_http_client, which was consolidated from ep_7a, which was extracted from doc_7.' };
  const redIds8 = ['ep_8', 'f_http_usage', 'step_4', 'step_5', 'a_fetch_py'];
  const two = copy(flagged);                                         // two advisories: the server sends no counters
  two.nodes.forEach(n => { n.red = redIds.includes(n.id) || redIds8.includes(n.id); delete n.naive_agent; delete n.naive_time; });
  two.docs.find(d => d.id === 'doc_8').flagged = true;
  two.counters = null;
  const torn = copy(flagged);                                        // doc flagged, closure never applied
  torn.nodes.forEach(n => { n.red = false; n.naive_agent = false; });
  torn.counters = { precise: 0, per_agent: 25, time_based: 19 };
  const second = copy(healed);                                       // doc_2 flagged after the heal: the twins read ep_2
  second.docs.find(d => d.id === 'doc_2').flagged = true; second.counters = null; second.flagged = 'doc_2';
  second.edges.push({ src: 'f_http_client_v2', type: 'CONSOLIDATED_FROM', dst: 'ep_2' },
                    { src: 'step_3_v2', type: 'INFLUENCED_BY', dst: 'f_http_client_v2' }, { src: 'a_requirements_v2', type: 'INFLUENCED_BY', dst: 'step_3_v2' });
  second.nodes.forEach(n => { delete n.naive_agent; delete n.naive_time; if (n.twin_of || n.id === 'ep_2') n.red = true; });
  second.nodes.push({ ...copy(clean.nodes.find(n => n.id === 'f_http_client')), id: 'f_http_client_v2_v2', twin_of: 'f_http_client_v2', tick: 60 },
                    { ...copy(clean.nodes.find(n => n.id === 'step_3')), id: 'step_3_v2_v2', twin_of: 'step_3_v2', tick: 61, needs_regeneration: true });
  second.edges.push({ src: 'f_http_client_v2_v2', type: 'SUPERSEDES', dst: 'f_http_client_v2' }, { src: 'step_3_v2_v2', type: 'SUPERSEDES', dst: 'step_3_v2' });
  const placeholders = copy(healed);                                 // twins the graph wrote with no clean content yet
  placeholders.nodes.forEach(n => { if (n.id === 'step_3_v2' || n.id === 'a_requirements_v2') n.needs_regeneration = true; });
  const stale = copy(flagged);                                       // unflag doc_5 ran, its reconcile did not: ep_5 reaches no flagged doc
  stale.nodes.find(n => n.id === 'ep_5').red = true; stale.counters = { precise: 7, per_agent: 25, time_based: 19 };
  const solo = copy(clean); solo.nodes.forEach(n => { n.agent = 'planner'; });
  const receipt8 = { shape: 'path', hops: ['a_fetch_py', 'step_4', 'f_http_usage', 'ep_8', 'doc_8'], len: 4, length: 4,
    via: ['INFLUENCED_BY', 'INFLUENCED_BY', 'CONSOLIDATED_FROM', 'EXTRACTED_FROM'],
    sentence: 'a_fetch_py was written after reading step_4, which was written after reading f_http_usage, which was consolidated from ep_8, which was extracted from doc_8.' };
  let current = clean, holdReceipt = false, releaseReceipt, receiptStarted;
  const graphRoute = route => route.fulfill({ json: current });
  const receiptRoute = async route => {                              // answers from the graph the page is being shown
    if (holdReceipt) await new Promise(resolve => { releaseReceipt = resolve; receiptStarted(); });
    const id = decodeURIComponent(route.request().url().split('id=')[1] || '');
    const red = current.nodes.find(n => n.id === id)?.red;
    await route.fulfill({ json: !red ? { shape: 'not_in_graph', answer: `${id} has no provenance path to any flagged document.` }
                                     : id === 'a_fetch_py' ? receipt8 : receipt });
  };
  const checks = [];
  const check = (name, ok, detail) => checks.push({ name, passed: !!ok, detail });
  const show = async data => { current = data; await page.evaluate(() => hive.poll()); };
  // Cells are drawn on a canvas, so a click is a real mouse click at the cell's pixel position.
  const clickMemory = async id => {
    const pt = await page.evaluate(id => { const c = hive.cells.get(id), r = document.querySelector('#stage').getBoundingClientRect();
      return { x: r.left + OX + c.x * S, y: r.top + OY + c.y * S }; }, id);
    await page.mouse.click(pt.x, pt.y);
  };
  const receiptShown = () => document.querySelector('#detail').textContent.includes('hops');
  const outside = () => {
    const box = document.querySelector('#stage').getBoundingClientRect();
    return [...hive.cells.values()].filter(c => {
      const x = OX + c.x * S, y = OY + c.y * S;
      const hw = (c.w || 2 * c.r) / 2 * S, hh = (c.h || 2 * c.r) / 2 * S;
      return x - hw < 0 || y - hh < 0 || x + hw > box.width || y + hh > box.height;
    }).map(c => c.id);
  };
  const checkFit = async name => {
    await page.evaluate(() => new Promise(requestAnimationFrame));
    const clipped = await page.evaluate(outside);
    check(name, !clipped.length, clipped);
  };
  const count = cls => page.evaluate(cls => [...hive.cells.values()].filter(c => c.cls === cls).length, cls);
  await page.route('**/graph', graphRoute);
  await page.route('**/receipt?*', receiptRoute);
  try {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(url);
    await page.waitForFunction(() => window.hive && hive.cells.size === 33);
    for (const width of [1920, 960, 375]) {
      await page.setViewportSize({ width, height: width === 375 ? 812 : 1080 });
      await checkFit(`every cell visible at ${width}px`);
    }
    check('no horizontal scroll at 375px', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.setViewportSize({ width: 1920, height: 1080 });

    await show(flagged);
    await page.waitForFunction(() => hive.state.red.size === 6, undefined, { timeout: 8000 });
    check('precise counter reaches 6 with the wave', await page.evaluate(() => document.querySelector('#c-precise').textContent === '6'));
    check('quarantined cells carry a non-colour marker', await page.evaluate(ids => ids.every(id => hive.cells.get(id).glyph === '!'), redIds));
    check('flagged source carries a non-colour marker', await page.evaluate(() => hive.cells.get('doc_7').glyph === '!'));

    await clickMemory('a_requirements');
    await page.waitForFunction(receiptShown);
    check('receipt highlights four arcs', await page.evaluate(() => [...hive.arcs.values()].filter(a => a.path).length === 4));
    check('receipt reads as a sentence', await page.evaluate(() => document.querySelector('#detail').textContent.includes('was extracted from doc_7')));

    await page.evaluate(() => hive.setView('time'));
    check('time-based view paints 13 clean casualties', (await count('collateral')) === 13);
    await page.evaluate(() => hive.setView('agent'));
    check('per-agent view paints 19 clean casualties', (await count('collateral')) === 19);
    await page.evaluate(() => hive.setView('precise'));
    check('graph view shows no casualties', (await count('collateral')) === 0);

    await show(healed);
    check('healed twin carries a non-colour marker', await page.evaluate(() => hive.cells.get('f_http_client_v2').glyph === '+'));
    for (const width of [1920, 960]) {
      await page.setViewportSize({ width, height: 1080 });
      await checkFit(`healed graph fits at ${width}px`);
    }

    await page.locator('#sr-cells button', { hasText: 'step_3 (' }).focus();
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => hive.state.selected === 'step_3');
    check('a cell can be selected from the keyboard', true);

    await show(clean);
    check('reset clears receipt, highlight and selection', await page.evaluate(() => !document.querySelector('#detail').textContent.includes('hops') && ![...hive.arcs.values()].some(a => a.path) && hive.state.selected === null));
    check('reset removes twins and status markers', await page.evaluate(() => hive.cells.size === 33 && hive.state.red.size === 0 && hive.state.pending.size === 0 && ![...hive.cells.values()].some(c => c.cls === 'red' || c.cls === 'twin') && document.querySelector('#c-precise').textContent === '–'));

    await show(flagged);
    await page.waitForFunction(() => hive.state.red.size === 6, undefined, { timeout: 8000 });
    holdReceipt = true;
    const started = new Promise(resolve => { receiptStarted = resolve; });
    await clickMemory('a_requirements');
    await started;
    await show(clean);
    const response = page.waitForResponse('**/receipt?*');
    releaseReceipt();
    await (await response).finished();
    await page.evaluate(() => new Promise(requestAnimationFrame));
    check('late receipt cannot overwrite reset', !(await page.evaluate(receiptShown)));

    holdReceipt = false;
    const text = id => page.evaluate(id => document.getElementById(id).textContent, id);
    await page.evaluate(() => hive.setView('agent'));
    await show(flagged);
    await page.waitForFunction(() => hive.state.red.size === 6, undefined, { timeout: 8000 });
    await show(two);
    await page.waitForFunction(() => hive.state.red.size === 11, undefined, { timeout: 8000 }).catch(() => {});
    check('two advisories: headline counts 11 and names both', (await text('hud-n')) === '11' && /doc_7.*doc_8/.test(await text('hud-line')) && !(await text('hud-line')).includes('no source is flagged'), await text('hud-line'));
    check('two advisories: banner names both', /doc_7.*doc_8/.test(await text('banner')), await text('banner'));
    check('two advisories: counters blank, note says why', (await text('c-agent')) === '–' && /one advisory/.test(await text('view-note')), await text('view-note'));
    check('two advisories: no chip dimmed for a comparison that is not shown', (await count('dim')) === 0 && (await count('collateral')) === 0);
    await page.evaluate(() => hive.setView('precise'));
    await clickMemory('a_fetch_py');
    await page.waitForFunction(() => document.querySelector('#detail').textContent.includes('doc_8'), undefined, { timeout: 4000 }).catch(() => {});
    check('receipt for a memory only doc_8 reached', (await text('detail')).includes('extracted from doc_8'), await text('detail'));
    await show(flagged);                                             // doc_8 retracted
    check('partial unflag: red set and ledger follow the data', await page.evaluate(() => hive.state.red.size === 6 && document.querySelectorAll('#ledger li').length === 6 && hive.cells.get('ep_8').cls === '' && !hive.state.arcing.has('ep_8')));
    await page.waitForFunction(() => document.querySelector('#detail').textContent.includes('not in the graph'), undefined, { timeout: 4000 }).catch(() => {});
    check('partial unflag: stale receipt and path are replaced', await page.evaluate(() => !document.querySelector('#detail').textContent.includes('hops') && ![...hive.arcs.values()].some(a => a.path)), await text('detail'));
    await page.evaluate(() => hive.setView('agent'));
    await show(clean);
    check('policy note follows the poll', !(await text('view-note')).includes('19'), await text('view-note'));
    await page.evaluate(() => hive.setView('precise'));
    await show(torn);
    check('torn flag: no "reached by" claim, counters blank', !(await text('hud-line')).includes('reached by') && /not been applied/.test(await text('hud-line')) && (await text('c-agent')) === '–', await text('hud-line'));
    await show(placeholders);
    check('placeholder twins are drawn as placeholders, not healed', await page.evaluate(() => ['step_3_v2', 'a_requirements_v2'].every(id => hive.cells.get(id).cls === 'pending' && hive.cells.get(id).glyph === '?') && hive.cells.get('f_http_client_v2').cls === 'twin'));
    check('banner counts only grounded twins as rebuilt', /1 memory rebuilt from clean sources · 2 placeholders awaiting regeneration/.test(await text('banner')), await text('banner'));
    check('ledger labels placeholders', (await text('ledger')).includes('placeholder for step_3, needs regeneration'), await text('ledger'));
    await show(second);
    const redN = second.nodes.filter(n => n.red).length;
    await page.waitForFunction(n => hive.state.red.size === n, redN, { timeout: 12000 }).catch(() => {});
    check('a twin a later advisory reaches is drawn red, never green', await page.evaluate(() => ['f_http_client_v2', 'step_3_v2', 'a_requirements_v2'].every(id => hive.cells.get(id).cls === 'red' && hive.cells.get(id).glyph === '!')));
    check('banner never calls a quarantined twin rebuilt', /1 memory rebuilt from clean sources · 1 placeholder awaiting regeneration · 3 replacements quarantined/.test(await text('banner')), await text('banner'));
    check('ledger swatch and label follow red for twins', await page.evaluate(() => [...document.querySelectorAll('#ledger li')].filter(li => li.textContent.includes('quarantined') && li.querySelector('.sw').style.background.includes('red')).length === 3));
    const originals = second.nodes.filter(n => !n.twin_of), redOrig = originals.filter(n => n.red).length;
    check('headline counts originals against originals', (await text('hud-n')) === String(redOrig) && (await text('hud-of')) === `of ${originals.length} memories` && /3<\/b> healed replacements/.test(await page.evaluate(() => document.getElementById('hud-line').innerHTML)), `${await text('hud-n')} ${await text('hud-of')} ${await text('hud-line')}`);
    check('twins of twins get a chip next to their chain', await page.evaluate(() => {
      const c = id => hive.cells.get(id), a = c('f_http_client'), b = c('f_http_client_v2'), t = c('f_http_client_v2_v2'), s = c('step_3_v2_v2');
      return t && s && t.axis === a.axis && t.ty > b.ty && b.ty > a.ty && t.ty - a.ty < 3 * 58 && s.cls === 'pending';
    }));
    await checkFit('second advisory graph fits at 1920px');
    await show(stale);
    check('interrupted retraction: no count, notice shown', (await text('hud-n')) === '–' && /reach(es)? no flagged source/.test(await text('hud-line')) && (await text('c-precise')) === '–' && (await text('c-agent')) === '–', await text('hud-line'));
    await show({ nodes: [], docs: [], edges: [], flagged: null, counters: null });   // a graph that does not exist yet
    check('missing graph shows the empty-state hint', await page.evaluate(() => !document.getElementById('empty').hidden && !document.getElementById('live').classList.contains('down')) && (await text('banner')).includes('Empty graph'), await text('banner'));
    await show(solo);
    check('agent count follows the data', (await text('hud-line')).includes('1 agent ') && (await text('banner')).includes('no source is flagged'), await text('hud-line'));
  } finally {
    if (releaseReceipt) releaseReceipt();
    await page.unroute('**/graph', graphRoute);
    await page.unroute('**/receipt?*', receiptRoute);
    await page.goto(url);
  }
  if (checks.some(c => !c.passed)) throw new Error(JSON.stringify(checks, null, 2));
  return checks;
}
