// Run against a page serving the seeded demo fixture. Only HTTP responses are
// substituted; the real page, vis-network, timers and click handler run unchanged.
// playwright-cli open http://127.0.0.1:8765
// playwright-cli run-code --filename scripts/check_browser.js
async (page) => {
  const url = page.url();
  const graphURL = await page.evaluate(() => location.origin + '/graph');
  const source = await (await page.request.get(graphURL)).json();
  if (source.error || !source.nodes.some(n => n.id === 'a_requirements')) {
    throw new Error('Seed the demo with quarantine session1 before running browser checks.');
  }
  const copy = value => JSON.parse(JSON.stringify(value));
  const clean = copy(source);
  clean.nodes = clean.nodes.filter(n => !n.twin_of).map(n => ({ ...n, red: false }));
  clean.docs.forEach(d => { d.flagged = false; });
  const ids = new Set([...clean.nodes, ...clean.docs].map(n => n.id));
  clean.edges = clean.edges.filter(e => ids.has(e.src) && ids.has(e.dst));
  clean.flagged = null;
  clean.counters = null;
  const redIds = ['ep_7a', 'ep_7b', 'f_http_client', 'f_http_pin', 'step_3', 'a_requirements'];
  const flagged = copy(clean);
  flagged.nodes.forEach(n => { n.red = redIds.includes(n.id); });
  flagged.docs.find(d => d.id === 'doc_7').flagged = true;
  flagged.flagged = 'doc_7';
  flagged.counters = { precise: 6, per_agent: 25, time_based: 19 };
  const healed = copy(flagged);
  ['f_http_client', 'step_3', 'a_requirements'].forEach((id, i) => {
    healed.nodes.push({ ...copy(clean.nodes.find(n => n.id === id)),
      id: id + '_v2', twin_of: id, tick: 41 + i });
    healed.edges.push({ src: id + '_v2', type: 'SUPERSEDES', dst: id });
  });
  const receipt = { hops: ['a_requirements', 'step_3', 'f_http_client', 'ep_7a', 'doc_7'],
    len: 4, via: ['INFLUENCED_BY', 'INFLUENCED_BY', 'CONSOLIDATED_FROM', 'EXTRACTED_FROM'] };
  let current = clean, holdReceipt = false, releaseReceipt, receiptStarted;
  const graphRoute = route => route.fulfill({ json: current });
  const receiptRoute = async route => {
    if (holdReceipt) await new Promise(resolve => { releaseReceipt = resolve; receiptStarted(); });
    await route.fulfill({ json: receipt });
  };
  const checks = [];
  const check = (name, ok, detail) => checks.push({ name, passed: !!ok, detail });
  const show = async data => { current = data; await page.evaluate(() => poll()); };
  const clickMemory = async () => {
    const box = await page.locator('#net').boundingBox();
    const p = await page.evaluate(() => net.canvasToDOM(net.getPosition('a_requirements')));
    await page.mouse.click(box.x + p.x, box.y + p.y);
  };
  const staleReceipt = () => document.querySelector('#detail').textContent.includes('shortestPath');
  const allNodesVisible = () => {
    const el = document.querySelector('#net');
    return nodes.getIds().every(id => {
      const b = net.getBoundingBox(id);
      const a = net.canvasToDOM({ x: b.left, y: b.top });
      const z = net.canvasToDOM({ x: b.right, y: b.bottom });
      return a.x >= 0 && a.y >= 0 && z.x <= el.clientWidth && z.y <= el.clientHeight;
    });
  };
  const checkFit = async name => {
    let visible = true;
    try { await page.waitForFunction(allNodesVisible, undefined, { timeout: 3000 }); }
    catch (error) { if (error.name !== 'TimeoutError') throw error; visible = false; }
    check(name, visible);
  };
  await page.route('**/graph', graphRoute);
  await page.route('**/receipt?*', receiptRoute);
  try {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(url);
    await page.waitForFunction(() => nodes.length === 33 && document.querySelector('#net canvas').width === 1920 * devicePixelRatio);
    await page.evaluate(() => { net.fit({ animation: false }); return new Promise(requestAnimationFrame); });
    await page.setViewportSize({ width: 960, height: 1080 });
    await page.waitForFunction(() => document.querySelector('#net canvas').width === 960 * devicePixelRatio);
    await page.evaluate(() => new Promise(requestAnimationFrame));
    const clipped = await page.evaluate(() => {
      const el = document.querySelector('#net');
      return nodes.getIds().filter(id => {
        const b = net.getBoundingBox(id);
        const a = net.canvasToDOM({ x: b.left, y: b.top });
        const z = net.canvasToDOM({ x: b.right, y: b.bottom });
        return a.x < 0 || a.y < 0 || z.x > el.clientWidth || z.y > el.clientHeight;
      });
    });
    check('resize keeps every node visible', !clipped.length, clipped);
    // Restore a usable view so a resize failure does not mask the click checks.
    await page.evaluate(() => net.fit({ animation: false }));
    await show(flagged);
    await page.waitForFunction(() => state.red.size === 6);
    const cues = await page.evaluate(ids => ids.every(id => nodes.get(id).label.startsWith('! ')), redIds);
    check('quarantined memories have non-colour markers', cues);
    check('flagged source has non-colour marker', await page.evaluate(() => nodes.get('doc_7').label.startsWith('! ')));
    await clickMemory();
    await page.waitForFunction(staleReceipt);
    check('clicked receipt highlights four edges', await page.evaluate(() => edges.get().filter(e => e.color.color === C.orange).length === 4));
    await show(healed);
    check('healed twin has non-colour marker', await page.evaluate(() => nodes.get('f_http_client_v2').label.startsWith('+ ')));
    await checkFit('all healed nodes fit after insertion');
    for (const width of [1920, 960]) {
      await page.setViewportSize({ width, height: 1080 });
      await page.waitForFunction(w => document.querySelector('#net canvas').width === w * devicePixelRatio, width);
      await page.evaluate(() => new Promise(requestAnimationFrame));
      await checkFit(`healed graph fits at ${width}px`);
    }
    await show(clean);
    check('reset clears receipt, highlight and selection', await page.evaluate(() =>
      !document.querySelector('#detail').textContent.includes('shortestPath') &&
      !edges.get().some(e => e.color.color === C.orange) && net.getSelectedNodes().length === 0));
    check('reset removes twins and status markers', await page.evaluate(() =>
      nodes.length === 33 && state.red.size === 0 && pending.size === 0 &&
      nodes.get().every(n => n.label === n.id) && document.querySelector('#c-precise').textContent === '-'));
    await show(flagged);
    await page.waitForFunction(() => state.red.size === 6);
    holdReceipt = true;
    const started = new Promise(resolve => { receiptStarted = resolve; });
    await clickMemory();
    await started;
    await show(clean);
    const response = page.waitForResponse('**/receipt?*');
    releaseReceipt();
    await (await response).finished();
    await page.evaluate(() => new Promise(requestAnimationFrame));
    check('late receipt cannot overwrite reset', !(await page.evaluate(staleReceipt)));
  } finally {
    if (releaseReceipt) releaseReceipt();
    await page.unroute('**/graph', graphRoute);
    await page.unroute('**/receipt?*', receiptRoute);
    await page.goto(url);
  }
  if (checks.some(c => !c.passed)) throw new Error(JSON.stringify(checks, null, 2));
  return checks;
}
