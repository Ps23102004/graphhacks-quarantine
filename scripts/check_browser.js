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
  let current = clean, holdReceipt = false, releaseReceipt, receiptStarted;
  const graphRoute = route => route.fulfill({ json: current });
  const receiptRoute = async route => {
    if (holdReceipt) await new Promise(resolve => { releaseReceipt = resolve; receiptStarted(); });
    await route.fulfill({ json: receipt });
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
      return x - c.r * S < 0 || y - c.r * S < 0 || x + c.r * S > box.width || y + c.r * S > box.height;
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
    check('precise view shows no casualties', (await count('collateral')) === 0);

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
  } finally {
    if (releaseReceipt) releaseReceipt();
    await page.unroute('**/graph', graphRoute);
    await page.unroute('**/receipt?*', receiptRoute);
    await page.goto(url);
  }
  if (checks.some(c => !c.passed)) throw new Error(JSON.stringify(checks, null, 2));
  return checks;
}
