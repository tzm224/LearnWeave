/* Standalone course viewer. All data is embedded; no network requests. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const KIND_LABELS = { source: '课件内容', supplement: '补充解释', inference: '教学推断', uncertain: '待确认' };
  const RELATION_LABELS = { prerequisite: '前置依赖', derivation: '推导', application: '应用', comparison: '对比', problem_solution: '问题与解决', evidence: '证据支持' };
  const PALETTE = ['#44866a', '#b28c42', '#648ba1', '#9686a0', '#a47564', '#739887', '#879b4d', '#628586'];
  // Auto-framing must not reduce the 14 px concept labels below 13 px.
  // Larger graphs intentionally extend beyond the canvas and remain pannable.
  const READABLE_ZOOM = .93;
  let lesson, source;
  try {
    lesson = JSON.parse($('lesson-data').textContent);
    source = JSON.parse($('source-data').textContent);
    if (!Array.isArray(lesson.pages) || !lesson.pages.length || !Array.isArray(source.pages)) throw new Error('课程没有可读页面');
  } catch (error) {
    $('fatal-error').hidden = false;
    $('fatal-error').textContent = `无法读取课程数据：${error.message}。请重新生成完整学习网页。`;
    return;
  }
  const sourceByPage = new Map(source.pages.map((page) => [page.page, page]));
  const pageByNumber = new Map(lesson.pages.map((page) => [page.page, page]));
  const conceptById = new Map(lesson.concepts.map((concept) => [concept.id, concept]));
  const relationById = new Map(lesson.relations.map((relation) => [relation.id, relation]));
  const pageSearchText = new Map(lesson.pages.map((page) => [page.page, JSON.stringify(page).toLocaleLowerCase() + ' ' + (sourceByPage.get(page.page)?.text || '').toLocaleLowerCase()]));
  const state = { page: lesson.pages[0].page, view: 'overview', concept: null, relation: null, graphReady: false, zoom: 1, tx: 0, ty: 0, width: 1000, height: 530, graphWidth: 1000, graphHeight: 530, search: '' };
  const nodePositions = new Map();
  const graphGroups = [];
  const navButtons = new Map();
  let ignoreHash = false;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }
  function button(text, className, action, label) {
    const element = node('button', className, text); element.type = 'button';
    if (label) element.setAttribute('aria-label', label);
    element.addEventListener('click', action); return element;
  }
  function provenance(kind) {
    const known = KIND_LABELS[kind] ? kind : 'uncertain';
    return node('span', `provenance ${known}`, KIND_LABELS[known]);
  }
  function learnerWarnings(warnings) {
    const rules = [
      [/parser reported.*recoverable|wrong pointing object|xref.*repair/i, '原文件结构存在可恢复问题，已保留原页图，请对照检查。'],
      [/logical page labels/i, '已单独保留文档页码标签；请核对它是否与页面上印刷的页码一致。'],
      [/Text extraction failed|No extractable/i, '这一页的文字无法完整提取，内容以原页图像为准。'],
      [/PPTX is shown as static/i, '原课件以静态页面呈现；动画、视频、交互内容和字体显示需要结合原文件核对。'],
      [/Hidden slide retained/i, '这是原课件中的隐藏页，已按它在原文件中的位置保留。'],
      [/Contains animation|build timing/i, '这一页包含逐步演示或动画，静态图像可能未呈现所有中间状态或最终状态。'],
      [/Contains media|playback content/i, '这一页包含媒体，静态图像未包含视频或音频中的内容。'],
      [/Chart\/diagram labels/i, '图表中的部分标签可能未包含在提取文字中，请对照原页图像。'],
      [/rendering failed; used|renderer was not found; used|LibreOffice rendering/i, '页面已使用备用方式转换，请检查版式和字体是否与原文件一致。'],
      [/Legacy \.ppt converted/i, '旧版演示文稿已转换为静态页面；转换可能影响版式或部分功能，原文件保持不变。']
    ];
    return [...new Set((warnings || []).map((warning) => {
      const message = String(warning); const match = rules.find(([pattern]) => pattern.test(message)); return match ? match[1] : message;
    }))];
  }
  function addInlineText(parent, text) {
    String(text).split(/(`[^`\n]+`)/g).forEach((part) => {
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) parent.append(node('code', '', part.slice(1, -1)));
      else parent.append(document.createTextNode(part));
    });
  }
  function prose(text) {
    const container = node('div', 'prose');
    String(text || '').split(/(```[^\n]*\n[\s\S]*?```)/g).forEach((part) => {
      if (part.startsWith('```') && part.endsWith('```')) {
        const firstLine = part.indexOf('\n'); const language = part.slice(3, firstLine).trim();
        const pre = node('pre'); const code = node('code', '', part.slice(firstLine + 1, -3).replace(/\n$/, ''));
        if (language) code.dataset.language = language;
        pre.append(code); container.append(pre);
      } else {
        // Preserve complete display-math spans, including blank lines, as one
        // text node so auto-render can find both delimiters.
        part.split(/(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])/g).forEach((piece) => {
          if (piece.startsWith('$$') || piece.startsWith('\\[')) {
            container.append(node('div', 'math-source', piece));
          } else {
            piece.split(/\n\s*\n/).filter((paragraph) => paragraph.trim()).forEach((paragraph) => {
              const p = node('p'); addInlineText(p, paragraph); container.append(p);
            });
          }
        });
      }
    });
    return container;
  }
  function mathWithin(element) {
    if (typeof window.renderMathInElement !== 'function') {
      if (element.textContent.includes('$') || /\\[([]/.test(element.textContent)) element.append(node('p', 'warning-box', '数学排版资源未加载，公式以原始文本保留。请检查网页旁的 assets 文件夹。'));
      return;
    }
    const errors = [];
    window.renderMathInElement(element, {
      delimiters: [{ left: '$$', right: '$$', display: true }, { left: '\\[', right: '\\]', display: true }, { left: '\\(', right: '\\)', display: false }, { left: '$', right: '$', display: false }],
      throwOnError: false, trust: false, strict: 'warn',
      ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code', 'option'],
      errorCallback: (message) => errors.push(message)
    });
    if (errors.length || element.querySelector('.katex-error')) element.append(node('p', 'warning-box', '部分公式未能排版，已保留可见原文；请对照原课件确认。'));
  }
  function teachingBlock(block, title, tag = 'section', className = '') {
    const section = node(tag, `teaching-block ${className}`.trim()); const heading = node('div', 'block-heading');
    heading.append(node(tag === 'section' ? 'h2' : 'h3', '', title), provenance(block.kind));
    section.append(heading, prose(block.text)); return section;
  }
  function setHash(hash) {
    if (window.location.hash === hash) return;
    ignoreHash = true; window.location.hash = hash;
  }
  function showView(view) {
    state.view = view;
    ['overview', 'reading', 'graph'].forEach((name) => { $(`${name}-view`).hidden = name !== view; });
    $('reading-tab').setAttribute('aria-pressed', String(view === 'reading'));
    $('graph-tab').setAttribute('aria-pressed', String(view === 'graph'));
    $('overview-btn').classList.toggle('active', view === 'overview');
    navButtons.forEach((element, page) => { if (view === 'reading' && page === state.page) element.setAttribute('aria-current', 'page'); else element.removeAttribute('aria-current'); });
    if (view === 'graph') requestAnimationFrame(() => { if (!state.graphReady) buildGraph(); resizeGraph(); });
  }
  function announce(message) { $('live-status').textContent = message; }
  function showOverview(updateHash = true) { showView('overview'); if (updateHash) setHash('#overview'); window.scrollTo({ top: 0 }); }
  function pageLink(pageNumber, label) { return button(label || `第 ${pageNumber} 页`, 'page-link', () => showPage(pageNumber), `前往第 ${pageNumber} 页：${pageByNumber.get(pageNumber)?.title || ''}`); }

  function buildOverview() {
    const root = $('overview-view'); const hero = node('div', 'hero');
    hero.append(node('p', 'eyebrow', '一份课件 · 两种理解路径'));
    const title = node('h1', '', lesson.title); title.id = 'overview-title';
    hero.append(title, node('p', 'hero-subtitle', lesson.subtitle));
    const meta = node('div', 'hero-meta');
    [[lesson.pages.length, '页原课件'], [lesson.concepts.length, '个知识点'], [lesson.relations.length, '条知识关联']].forEach(([count, label]) => {
      const span = node('span'); span.append(node('b', '', count), document.createTextNode(` ${label}`)); meta.append(span);
    });
    hero.append(meta); const actions = node('div', 'hero-actions');
    actions.append(button('开始逐页学习 →', 'primary-button', () => showPage(lesson.pages[0].page)), button('探索知识图 ↗', 'secondary-button', () => showGraph()));
    hero.append(actions); root.append(hero);
    const overview = node('section', 'overview-section'); const heading = node('div', 'section-heading');
    const h2 = node('h2'); h2.append(node('span', 'section-number', '01'), document.createTextNode('先看这门课要解决什么'));
    heading.append(h2); overview.append(heading, prose(lesson.overview.summary));
    const goals = node('div', 'learning-goals');
    [['学完能够做到', lesson.overview.objectives], ['开始前需要的基础', lesson.overview.prerequisites]].forEach(([label, items]) => {
      const section = node('section'); section.append(node('h3', '', label)); const ul = node('ul');
      items.forEach((item) => { const li = node('li'); addInlineText(li, item); ul.append(li); }); section.append(ul); goals.append(section);
    });
    overview.append(goals); root.append(overview);
    const route = node('section', 'overview-section'); const routeHeading = node('div', 'section-heading');
    const routeTitle = node('h2'); routeTitle.append(node('span', 'section-number', '02'), document.createTextNode('沿着这条主线学习'));
    routeHeading.append(routeTitle); route.append(routeHeading); const storyline = node('div', 'storyline');
    lesson.overview.storyline.forEach((chapter, index) => {
      const item = node('section', 'story-item');
      item.append(node('span', 'story-index', String(index + 1).padStart(2, '0')), node('h3', '', chapter.title), node('p', '', chapter.summary));
      if (chapter.pages.length) item.append(pageLink(chapter.pages[0], `第 ${chapter.pages[0]}–${chapter.pages[chapter.pages.length - 1]} 页 →`));
      storyline.append(item);
    });
    route.append(storyline, node('p', 'source-note', `来源：${source.source.filename}。页面编号按原文件顺序排列；讲解中的补充与推断均单独标记。`));
    if (source.warnings?.length) { const warnings = node('details', 'warning-box'); warnings.append(node('summary', '', '原文件处理说明')); learnerWarnings(source.warnings).forEach((warning) => warnings.append(node('p', '', warning))); route.append(warnings); }
    root.append(route); mathWithin(root);
  }
  function buildPageList(query = '') {
    const needle = query.trim().toLocaleLowerCase(); const list = $('page-list'); list.replaceChildren(); navButtons.clear();
    let lastSection = null; let count = 0;
    lesson.pages.forEach((page) => {
      if (needle && !pageSearchText.get(page.page).includes(needle)) return;
      count += 1;
      if (page.section !== lastSection) { list.append(node('h2', 'chapter-heading', page.section)); lastSection = page.section; }
      const item = button('', 'page-nav-button', () => showPage(page.page)); item.dataset.page = page.page;
      item.append(node('span', 'page-nav-number', String(page.page).padStart(2, '0')), node('span', 'page-nav-title', page.title));
      if (state.view === 'reading' && page.page === state.page) item.setAttribute('aria-current', 'page');
      list.append(item); navButtons.set(page.page, item);
    });
    $('search-count').textContent = needle ? `找到 ${count} 页` : `${lesson.pages.length} 页 · 按原课件顺序`;
    if (!count) list.append(node('p', 'empty-message', '没有匹配页面，试试更短的关键词。'));
  }
  function showPage(pageNumber, updateHash = true) {
    const page = pageByNumber.get(Number(pageNumber)); const original = sourceByPage.get(Number(pageNumber));
    if (!page || !original) { announce('没有找到该页，请检查页码。'); return; }
    state.page = page.page; $('page-title').textContent = page.title; $('page-section').textContent = page.section;
    $('page-jump').value = page.page; $('page-jump').max = lesson.pages.length; $('page-total').textContent = `/ ${lesson.pages.length}`;
    const printed = page.printed_page ?? original.printed_page;
    const printedText = printed !== null && printed !== undefined ? ` · 印刷页码 ${printed}` : '';
    $('source-page-label').textContent = `原文件第 ${page.page} 页${printedText}`;
    const image = $('slide-image'); image.src = original.image; image.alt = `原课件第 ${page.page} 页：${page.title}`;
    if (original.width && original.height) { image.width = original.width; image.height = original.height; }
    $('source-warnings').replaceChildren(); learnerWarnings(original.warnings).forEach((warning) => $('source-warnings').append(node('p', 'warning-box', warning)));
    image.onerror = () => $('source-warnings').replaceChildren(node('p', 'warning-box', '原页图像无法加载。请保留网页旁的 pages 文件夹，并重新校验导出结果。'));
    $('speaker-notes').hidden = !original.notes; $('speaker-notes').open = false; $('speaker-notes-text').replaceChildren();
    if (original.notes) { $('speaker-notes-text').append(prose(original.notes)); mathWithin($('speaker-notes-text')); }
    const concepts = $('page-concepts'); concepts.replaceChildren(); concepts.hidden = !page.concept_ids.length;
    if (page.concept_ids.length) {
      concepts.append(node('h2', '', '本页在知识图中的位置')); const chips = node('div', 'concept-chips');
      page.concept_ids.forEach((id) => { const concept = conceptById.get(id); if (concept) { const chip = button(`${concept.label} ↗`, 'concept-chip', () => showGraph(id)); chip.dataset.concept = id; chips.append(chip); } });
      concepts.append(chips);
    }
    const explanation = $('page-explanation'); explanation.replaceChildren();
    explanation.append(teachingBlock(page.role, '为什么在这里讲这一页', 'section', 'teaching-role'));
    page.blocks.forEach((block, index) => explanation.append(teachingBlock(block, block.title || `内容讲解 ${index + 1}`)));
    explanation.append(teachingBlock(page.takeaway, '这一页，记住这件事', 'section', 'takeaway'));
    const transitions = node('div', 'transition-grid'); transitions.append(teachingBlock(page.bridge_prev, '← 承接前文', 'div'), teachingBlock(page.bridge_next, '引出后文 →', 'div'));
    explanation.append(transitions); mathWithin(explanation);
    const first = page.page === lesson.pages[0].page; const last = page.page === lesson.pages[lesson.pages.length - 1].page;
    ['prev-page', 'bottom-prev'].forEach((id) => { $(id).disabled = first; }); ['next-page', 'bottom-next'].forEach((id) => { $(id).disabled = last; });
    $('reading-progress').textContent = `第 ${page.page} 页 / 共 ${lesson.pages.length} 页`; showView('reading');
    if (updateHash) setHash(`#page-${page.page}`);
    document.querySelector('.sidebar').classList.remove('expanded'); $('sidebar-toggle').setAttribute('aria-expanded', 'false'); $('sidebar-toggle').textContent = '展开目录';
    window.scrollTo({ top: 0 }); announce(`第 ${page.page} 页，${page.title}`);
  }
  function advancePage(delta) { const index = lesson.pages.findIndex((page) => page.page === state.page); const next = lesson.pages[index + delta]; if (next) showPage(next.page); }

  function svgNode(tag, attrs = {}, text) {
    const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (text !== undefined) element.textContent = text;
    return element;
  }
  function wrapLabel(text, maxUnits = 22) {
    const lines = []; let current = ''; let units = 0;
    for (const char of [...String(text)]) {
      const size = char.codePointAt(0) > 255 ? 2 : 1;
      if (units + size > maxUnits && current) { lines.push(current); current = ''; units = 0; }
      current += char; units += size;
    }
    if (current) lines.push(current);
    if (lines.length > 2) return [lines[0], `${lines[1].slice(0, -1)}…`];
    return lines;
  }
  function buildGraph() {
    const groups = new Map();
    lesson.concepts.forEach((concept) => { if (!groups.has(concept.group)) groups.set(concept.group, []); groups.get(concept.group).push(concept); });
    const columns = Math.min(3, Math.max(groups.size, 1)); const groupWidth = 266; const columnGap = 34; const rowGap = 42;
    let rowY = 30; let rowHeight = 0;
    [...groups.entries()].forEach(([label, concepts], index) => {
      if (index % columns === 0 && index) { rowY += rowHeight + rowGap; rowHeight = 0; }
      const x = 30 + (index % columns) * (groupWidth + columnGap); const height = 62 + concepts.length * 86;
      const group = { label, x, y: rowY, width: groupWidth, height, color: PALETTE[index % PALETTE.length], ids: concepts.map((concept) => concept.id) };
      graphGroups.push(group); rowHeight = Math.max(rowHeight, height);
      concepts.forEach((concept, conceptIndex) => nodePositions.set(concept.id, { x: x + 20, y: rowY + 46 + conceptIndex * 86, width: groupWidth - 40, height: 66, color: group.color }));
    });
    state.graphWidth = Math.max(350, columns * (groupWidth + columnGap) + 26); state.graphHeight = Math.max(300, rowY + rowHeight + 30);
    const world = $('graph-world'); world.replaceChildren();
    graphGroups.forEach((group) => {
      const groupElement = svgNode('g', { class: 'graph-group', 'data-group': group.label });
      groupElement.append(svgNode('rect', { class: 'graph-group-box', x: group.x, y: group.y, width: group.width, height: group.height }), svgNode('text', { class: 'graph-group-title', x: group.x + 20, y: group.y + 27 }, group.label));
      world.append(groupElement);
    });
    lesson.relations.forEach((relation) => {
      const from = nodePositions.get(relation.from); const to = nodePositions.get(relation.to); if (!from || !to) return;
      const sameColumn = Math.abs(from.x - to.x) < 5; let x1, y1, x2, y2, path;
      if (sameColumn) {
        x1 = from.x + from.width; y1 = from.y + from.height / 2; x2 = to.x + to.width; y2 = to.y + to.height / 2;
        const bend = 30 + Math.min(Math.abs(y2 - y1) * .1, 70); path = `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 + bend} ${y2}, ${x2} ${y2}`;
      } else {
        const rightward = to.x > from.x; x1 = from.x + (rightward ? from.width : 0); y1 = from.y + from.height / 2;
        x2 = to.x + (rightward ? 0 : to.width); y2 = to.y + to.height / 2; const controlX = (x1 + x2) / 2;
        path = `M ${x1} ${y1} C ${controlX} ${y1}, ${controlX} ${y2}, ${x2} ${y2}`;
      }
      const edge = svgNode('g', { class: 'graph-edge', 'data-relation': relation.id, role: 'button', tabindex: 0, 'aria-label': `${conceptById.get(relation.from).label}，${relation.label}，${conceptById.get(relation.to).label}` });
      const visible = svgNode('path', { class: 'edge-visible', d: path }); if (relation.type !== 'comparison') visible.setAttribute('marker-end', 'url(#edge-arrow)');
      edge.append(visible, svgNode('path', { class: 'edge-hit', d: path }), svgNode('text', { class: 'edge-label', x: (x1 + x2) / 2 + (sameColumn ? 25 : 0), y: (y1 + y2) / 2 - 6, 'text-anchor': 'middle' }, relation.label));
      edge.addEventListener('click', () => selectRelation(relation.id));
      edge.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectRelation(relation.id); } });
      world.append(edge);
    });
    lesson.concepts.forEach((concept) => {
      const pos = nodePositions.get(concept.id); const item = svgNode('g', { class: 'graph-node', 'data-concept': concept.id, role: 'button', tabindex: 0, 'aria-label': `${concept.label}，来源第 ${concept.pages.join('、')} 页` });
      item.append(svgNode('title', {}, concept.label), svgNode('rect', { x: pos.x, y: pos.y, width: pos.width, height: pos.height }), svgNode('rect', { class: 'node-accent', x: pos.x, y: pos.y + 12, width: 3, height: pos.height - 24, fill: pos.color }));
      const lines = wrapLabel(concept.label); const text = svgNode('text', { class: 'node-label', x: pos.x + 14, y: pos.y + (lines.length > 1 ? 22 : 27) });
      lines.forEach((line, index) => text.append(svgNode('tspan', { x: pos.x + 14, dy: index ? 17 : 0 }, line)));
      item.append(text, svgNode('text', { class: 'node-pages', x: pos.x + 14, y: pos.y + 55 }, concept.pages.length > 4 ? `第 ${concept.pages.slice(0, 3).join('、')}… 页 · 共 ${concept.pages.length} 页` : `第 ${concept.pages.join('、')} 页`));
      item.addEventListener('click', () => selectConcept(concept.id));
      item.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectConcept(concept.id); } });
      world.append(item);
    });
    $('graph-legend').replaceChildren();
    graphGroups.forEach((group) => { const item = node('span', 'legend-item'); const dot = node('span', 'legend-dot'); dot.style.background = group.color; item.append(dot, document.createTextNode(group.label)); $('graph-legend').append(item); });
    state.graphReady = true; buildConceptList(); updateGraphStyles(); resizeGraph(true);
  }
  function visibleConceptIds() {
    if (!$('neighbors-only').checked || !state.concept) return null;
    const ids = new Set([state.concept]);
    lesson.relations.forEach((relation) => { if (relation.from === state.concept) ids.add(relation.to); if (relation.to === state.concept) ids.add(relation.from); });
    return ids;
  }
  function graphBounds() {
    const visible = visibleConceptIds();
    if (!visible) return { x: 0, y: 0, width: state.graphWidth, height: state.graphHeight };
    const positions = [...visible].map((id) => nodePositions.get(id)).filter(Boolean);
    if (!positions.length) return { x: 0, y: 0, width: state.graphWidth, height: state.graphHeight };
    const minX = Math.min(...positions.map((pos) => pos.x)) - 40; const minY = Math.min(...positions.map((pos) => pos.y)) - 45;
    const maxX = Math.max(...positions.map((pos) => pos.x + pos.width)) + 40; const maxY = Math.max(...positions.map((pos) => pos.y + pos.height)) + 45;
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }
  function applyTransform() { $('graph-world').setAttribute('transform', `translate(${state.tx} ${state.ty}) scale(${state.zoom})`); }
  function fitGraph() {
    const bounds = graphBounds();
    state.zoom = Math.max(READABLE_ZOOM, Math.min((state.width - 32) / bounds.width, (state.height - 32) / bounds.height, 1));
    if (state.concept && nodePositions.has(state.concept)) {
      focusGraphOn(state.concept);
    } else {
      // Start at the first rows when the graph is taller than the canvas,
      // rather than centering a clipped overview somewhere in its middle.
      state.tx = (bounds.width * state.zoom <= state.width - 32 ? (state.width - bounds.width * state.zoom) / 2 : 16) - bounds.x * state.zoom;
      state.ty = (bounds.height * state.zoom <= state.height - 32 ? (state.height - bounds.height * state.zoom) / 2 : 16) - bounds.y * state.zoom;
      applyTransform();
    }
  }
  function focusGraphOn(id) {
    const position = nodePositions.get(id); if (!position) return;
    state.zoom = Math.max(READABLE_ZOOM, state.zoom);
    state.tx = state.width / 2 - (position.x + position.width / 2) * state.zoom;
    state.ty = state.height / 2 - (position.y + position.height / 2) * state.zoom;
    applyTransform();
  }
  function showWholeGraph() {
    // Small labels are permitted only after this explicit overview action.
    $('neighbors-only').checked = false; updateGraphStyles();
    state.zoom = Math.max(.05, Math.min((state.width - 28) / state.graphWidth, (state.height - 28) / state.graphHeight, 1));
    state.tx = (state.width - state.graphWidth * state.zoom) / 2;
    state.ty = (state.height - state.graphHeight * state.zoom) / 2;
    applyTransform();
    announce('已缩小查看完整结构。选择知识点或点击可读视图，恢复清晰字号。');
  }
  function resizeGraph(force = false) {
    if (state.view !== 'graph' || !state.graphReady) return;
    const box = $('knowledge-graph').getBoundingClientRect(); if (!box.width || !box.height) return;
    if (force || state.width !== box.width || state.height !== box.height) { state.width = box.width; state.height = box.height; $('knowledge-graph').setAttribute('viewBox', `0 0 ${state.width} ${state.height}`); fitGraph(); }
  }
  function zoomGraph(factor, centerX = state.width / 2, centerY = state.height / 2) {
    const next = Math.max(.12, Math.min(4, state.zoom * factor)); const ratio = next / state.zoom;
    state.tx = centerX - (centerX - state.tx) * ratio; state.ty = centerY - (centerY - state.ty) * ratio; state.zoom = next; applyTransform();
  }
  function buildConceptList() {
    const list = $('concept-list'); list.replaceChildren(); const needle = state.search.toLocaleLowerCase().trim(); let count = 0;
    lesson.concepts.forEach((concept) => {
      if (needle && !`${concept.label} ${concept.description} ${concept.group}`.toLocaleLowerCase().includes(needle)) return;
      const item = button(concept.label, 'concept-list-button', () => selectConcept(concept.id)); item.dataset.concept = concept.id; item.setAttribute('aria-pressed', String(concept.id === state.concept)); list.append(item); count += 1;
    });
    if (!count) list.append(node('p', 'empty-message', '没有匹配的知识点。'));
  }
  function updateGraphStyles() {
    if (!state.graphReady) return;
    const neighbors = new Set(); const relatedEdges = new Set();
    if (state.concept) { neighbors.add(state.concept); lesson.relations.forEach((relation) => { if (relation.from === state.concept || relation.to === state.concept) { neighbors.add(relation.from); neighbors.add(relation.to); relatedEdges.add(relation.id); } }); }
    const selectedRelation = state.relation ? relationById.get(state.relation) : null; if (selectedRelation) { neighbors.add(selectedRelation.from); neighbors.add(selectedRelation.to); }
    const visible = visibleConceptIds(); const needle = state.search.toLocaleLowerCase().trim();
    document.querySelectorAll('.graph-node').forEach((element) => {
      const id = element.dataset.concept; const concept = conceptById.get(id); const matches = !needle || `${concept.label} ${concept.description} ${concept.group}`.toLocaleLowerCase().includes(needle);
      element.classList.toggle('selected', id === state.concept); element.classList.toggle('neighbor', neighbors.has(id) && id !== state.concept); element.classList.toggle('dim', !matches || (neighbors.size > 0 && !neighbors.has(id))); element.style.display = visible && !visible.has(id) ? 'none' : '';
    });
    document.querySelectorAll('.graph-edge').forEach((element) => {
      const relation = relationById.get(element.dataset.relation); element.classList.toggle('active', relatedEdges.has(relation.id) || relation.id === state.relation); element.classList.toggle('selected', relation.id === state.relation); element.classList.toggle('dim', neighbors.size > 0 && !relatedEdges.has(relation.id) && relation.id !== state.relation); element.style.display = visible && (!visible.has(relation.from) || !visible.has(relation.to)) ? 'none' : '';
    });
    document.querySelectorAll('.graph-group').forEach((element) => { element.style.display = visible ? 'none' : ''; });
    document.querySelectorAll('.concept-list-button').forEach((element) => element.setAttribute('aria-pressed', String(element.dataset.concept === state.concept)));
  }
  function appendPageLinks(root, pages) { const links = node('div', 'detail-page-links'); pages.forEach((number) => links.append(pageLink(number))); root.append(links); }
  function emptyGraphDetail() {
    const detail = $('graph-detail'); detail.replaceChildren();
    detail.append(node('p', 'eyebrow', '知识之间的联系'), node('div', 'detail-empty-number', String(lesson.concepts.length).padStart(2, '0')), node('h2', '', '从一个概念出发'));
    detail.append(prose('点击图中的知识点，查看定义、相关页码及它与其他知识的联系。也可以使用下方列表。\n\n关系线说明概念如何相互支持；每条关系都能回到具体页面核对。'));
  }
  function selectConcept(id, updateHash = true) {
    const concept = conceptById.get(id); if (!concept) return; state.concept = id; state.relation = null;
    const detail = $('graph-detail'); detail.replaceChildren();
    detail.append(node('p', 'eyebrow', concept.group), node('h2', '', concept.label), provenance(concept.kind), prose(concept.description));
    detail.append(node('h3', '', '回到课件中的讲解')); appendPageLinks(detail, concept.pages);
    const relations = lesson.relations.filter((relation) => relation.from === id || relation.to === id); detail.append(node('h3', '', `相关联的知识 · ${relations.length}`));
    relations.forEach((relation) => {
      const other = conceptById.get(relation.from === id ? relation.to : relation.from); const item = button(other.label, 'relation-button', () => selectRelation(relation.id)); item.dataset.relation = relation.id;
      item.append(node('span', '', `${RELATION_LABELS[relation.type]} · ${relation.label}`)); detail.append(item);
    });
    if (!relations.length) detail.append(node('p', 'small muted', '目前没有足够依据建立跨概念关系。'));
    detail.append(button('清除选择', 'text-button', () => { state.concept = null; state.relation = null; $('neighbors-only').checked = false; emptyGraphDetail(); updateGraphStyles(); fitGraph(); setHash('#graph'); }));
    mathWithin(detail); updateGraphStyles(); focusGraphOn(id); if (updateHash) setHash(`#concept-${encodeURIComponent(id)}`); announce(`已选择知识点：${concept.label}`);
  }
  function selectRelation(id, updateHash = true) {
    const relation = relationById.get(id); if (!relation) return; state.relation = id;
    const detail = $('graph-detail'); detail.replaceChildren(); detail.append(node('p', 'eyebrow', RELATION_LABELS[relation.type]), node('h2', '', relation.label), provenance(relation.kind));
    const from = conceptById.get(relation.from); const to = conceptById.get(relation.to); const endpoints = node('div', 'concept-chips'); endpoints.style.margin = '15px 0';
    endpoints.append(button(from.label, 'concept-chip', () => selectConcept(from.id)), node('span', 'muted', relation.type === 'comparison' ? '↔' : '→'), button(to.label, 'concept-chip', () => selectConcept(to.id)));
    detail.append(endpoints, prose(relation.explanation), node('h3', '', '关联依据所在页')); appendPageLinks(detail, relation.pages);
    detail.append(button('返回知识点', 'text-button', () => selectConcept(state.concept || from.id)));
    mathWithin(detail); updateGraphStyles(); focusGraphOn(state.concept === to.id ? to.id : from.id); if (updateHash) setHash(`#relation-${encodeURIComponent(id)}`); announce(`已选择关联：${from.label}，${relation.label}，${to.label}`);
  }
  function showGraph(conceptId = null, updateHash = true) {
    showView('graph'); if (!state.graphReady) buildGraph();
    if (conceptId) { state.search = ''; $('concept-search').value = ''; buildConceptList(); selectConcept(conceptId, updateHash); }
    else { if (!state.concept && !state.relation) emptyGraphDetail(); if (updateHash) setHash('#graph'); }
    window.scrollTo({ top: 0 });
  }
  function readHash() {
    const hash = window.location.hash;
    if (/^#page-\d+$/.test(hash)) showPage(Number(hash.slice(6)), false);
    else if (hash.startsWith('#concept-')) { let id; try { id = decodeURIComponent(hash.slice(9)); } catch { showGraph(null, false); return; } showGraph(id, false); }
    else if (hash.startsWith('#relation-')) { let id; try { id = decodeURIComponent(hash.slice(10)); } catch { showGraph(null, false); return; } showGraph(null, false); selectRelation(id, false); }
    else if (hash === '#graph') showGraph(null, false);
    else showOverview(false);
  }

  $('course-name').textContent = lesson.title; $('source-name').textContent = source.source.filename; $('graph-count').textContent = `${lesson.concepts.length} 个知识点 · ${lesson.relations.length} 条关联`;
  $('home-btn').addEventListener('click', () => showOverview()); $('overview-btn').addEventListener('click', () => showOverview());
  $('reading-tab').addEventListener('click', () => showPage(state.page)); $('graph-tab').addEventListener('click', () => showGraph());
  $('page-search').addEventListener('input', (event) => buildPageList(event.target.value));
  $('sidebar-toggle').addEventListener('click', () => { const expanded = document.querySelector('.sidebar').classList.toggle('expanded'); $('sidebar-toggle').setAttribute('aria-expanded', String(expanded)); $('sidebar-toggle').textContent = expanded ? '收起目录' : '展开目录'; });
  ['prev-page', 'bottom-prev'].forEach((id) => $(id).addEventListener('click', () => advancePage(-1))); ['next-page', 'bottom-next'].forEach((id) => $(id).addEventListener('click', () => advancePage(1)));
  $('page-jump-form').addEventListener('submit', (event) => { event.preventDefault(); if ($('page-jump').reportValidity()) showPage(Number($('page-jump').value)); });
  $('zoom-slide').addEventListener('click', () => {
    const page = pageByNumber.get(state.page); const original = sourceByPage.get(state.page); $('dialog-title').textContent = `第 ${state.page} 页 · ${page.title}`;
    $('dialog-image').src = original.image; $('dialog-image').alt = `原课件第 ${state.page} 页：${page.title}`; $('dialog-image-area').classList.remove('original-size'); $('image-size-toggle').textContent = '原始比例'; $('slide-dialog').showModal();
  });
  $('close-dialog').addEventListener('click', () => $('slide-dialog').close());
  $('image-size-toggle').addEventListener('click', () => { const original = $('dialog-image-area').classList.toggle('original-size'); $('image-size-toggle').textContent = original ? '适应窗口' : '原始比例'; });
  $('slide-dialog').addEventListener('click', (event) => { if (event.target === $('slide-dialog')) $('slide-dialog').close(); });
  $('concept-search').addEventListener('input', (event) => { state.search = event.target.value; buildConceptList(); updateGraphStyles(); });
  $('neighbors-only').addEventListener('change', () => { if ($('neighbors-only').checked && !state.concept && lesson.concepts.length) selectConcept(lesson.concepts[0].id); updateGraphStyles(); fitGraph(); });
  $('graph-zoom-in').addEventListener('click', () => zoomGraph(1.25)); $('graph-zoom-out').addEventListener('click', () => zoomGraph(.8)); $('graph-fit').addEventListener('click', fitGraph); $('graph-overview').addEventListener('click', showWholeGraph);
  const svg = $('knowledge-graph'); let drag = null;
  svg.addEventListener('wheel', (event) => { event.preventDefault(); const rect = svg.getBoundingClientRect(); zoomGraph(event.deltaY < 0 ? 1.1 : 1 / 1.1, event.clientX - rect.left, event.clientY - rect.top); }, { passive: false });
  svg.addEventListener('pointerdown', (event) => { if (event.target.closest('.graph-node, .graph-edge') || (event.button !== undefined && event.button !== 0)) return; drag = { x: event.clientX, y: event.clientY, tx: state.tx, ty: state.ty }; svg.setPointerCapture(event.pointerId); svg.classList.add('dragging'); });
  svg.addEventListener('pointermove', (event) => { if (drag) { state.tx = drag.tx + event.clientX - drag.x; state.ty = drag.ty + event.clientY - drag.y; applyTransform(); } });
  const stopDrag = () => { drag = null; svg.classList.remove('dragging'); }; svg.addEventListener('pointerup', stopDrag); svg.addEventListener('pointercancel', stopDrag); svg.addEventListener('lostpointercapture', stopDrag);
  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => resizeGraph()).observe(svg); else window.addEventListener('resize', () => resizeGraph());
  window.addEventListener('hashchange', () => { if (ignoreHash) { ignoreHash = false; return; } readHash(); });
  document.addEventListener('keydown', (event) => {
    if (state.view !== 'reading' || $('slide-dialog').open || /INPUT|TEXTAREA|SELECT|BUTTON/.test(event.target.tagName) || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === 'ArrowRight') { event.preventDefault(); advancePage(1); } if (event.key === 'ArrowLeft') { event.preventDefault(); advancePage(-1); }
  });
  buildOverview(); buildPageList(); emptyGraphDetail(); readHash();
})();
