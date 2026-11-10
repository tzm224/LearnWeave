(() => {
  'use strict';

  const types = {
    problem: '问题', constraint: '约束', insight: '洞察', architecture: '架构',
    design_decision: '设计决策', component: '组件', mechanism: '机制', tradeoff: '权衡',
    evidence: '证据', concept: '概念', pattern: '可迁移模式', outcome: '结果'
  };
  const relations = {
    motivates: '促使', addresses: '应对', implements: '落实', depends_on: '依赖',
    enables: '使得', part_of: '属于', supports: '支持', contrasts_with: '对比',
    generalizes_to: '可归纳为', trades_off: '带来权衡'
  };
  const levelNames = {L1: '宏观', L2: '设计机制', L3: '细节'};
  const card = {width: 156, height: 74};

  function element(tag, className, text) {
    const result = document.createElement(tag);
    if (className) result.className = className;
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function svg(tag, properties, text) {
    const result = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(properties)) result.setAttribute(key, value);
    if (text !== undefined) result.textContent = text;
    return result;
  }

  function button(label, action, className) {
    const result = element('button', className, label);
    result.type = 'button';
    result.addEventListener('click', () => action(result));
    return result;
  }

  // Every actual edge connects vertices in the same or adjacent BFS columns.
  // Disconnected components are laid out separately, without artificial edges.
  function layout(ids, edges, vertical) {
    const adjacency = new Map(ids.map(id => [id, new Set()]));
    for (const edge of edges) {
      adjacency.get(edge.source_id).add(edge.target_id);
      adjacency.get(edge.target_id).add(edge.source_id);
    }
    const positions = new Map();
    const visited = new Set();
    const isolated = [];
    let bottom = 0;
    const columnGap = vertical ? card.height + 64 : card.width + 94;
    const rowGap = vertical ? card.width + 34 : card.height + 36;
    const position = (depth, offset) => vertical ? {x: offset, y: depth} : {x: depth, y: offset};
    for (const start of ids) {
      if (visited.has(start)) continue;
      if (!adjacency.get(start).size) {
        isolated.push(start);
        continue;
      }
      let front = [start];
      const columns = [];
      visited.add(start);
      while (front.length) {
        columns.push(front);
        const next = [];
        for (const id of front) {
          for (const other of adjacency.get(id)) {
            if (!visited.has(other)) {
              visited.add(other);
              next.push(other);
            }
          }
        }
        front = next;
      }
      const rows = columns.reduce((height, column) => Math.max(height, column.length), 0);
      columns.forEach((column, x) => column.forEach((id, y) => positions.set(id,
        position(x * columnGap, bottom + (y + (rows - column.length) / 2) * rowGap))));
      bottom += rows * rowGap + 12;
    }
    const count = Math.max(1, Math.ceil(Math.sqrt(isolated.length)));
    isolated.forEach((id, index) => positions.set(id,
      position(index % count * columnGap, bottom + Math.floor(index / count) * rowGap)));
    return positions;
  }

  // Offset coinciding edges, including relations whose endpoints are reversed.
  function edgeGeometry(start, end, lane, vertical) {
    // Compute along the layout's depth axis, then transpose back to screen space.
    const half = (vertical ? card.height : card.width) / 2;
    if (vertical) {
      start = {x: start.y, y: start.x};
      end = {x: end.y, y: end.x};
    }
    const direction = Math.sign(end.x - start.x);
    let ax, ay, bx, by, cx, cy, dx, dy;
    if (direction) {
      ax = start.x + direction * (half + 2);
      bx = end.x - direction * (half + 3);
      ay = start.y + lane;
      by = end.y + lane;
      cx = dx = (ax + bx) / 2;
      cy = ay; dy = by;
    } else {
      ax = bx = start.x + half + 2;
      ay = start.y + lane;
      by = end.y + lane;
      cx = dx = ax + 40 + Math.abs(end.y - start.y) * 0.07 + lane;
      cy = ay; dy = by;
    }
    if (vertical) {
      [ax, ay, bx, by, cx, cy, dx, dy] = [ay, ax, by, bx, cy, cx, dy, dx];
    }
    return {
      path: 'M ' + ax + ' ' + ay + ' C ' + cx + ' ' + cy + ', ' + dx + ' ' + dy + ', ' + bx + ' ' + by,
      x: (ax + 3 * cx + 3 * dx + bx) / 8,
      y: (ay + 3 * cy + 3 * dy + by) / 8
    };
  }

  function titleLines(title) {
    const lines = [''];
    let units = 0;
    for (const ch of title.replace(/\s+/g, ' ').trim()) {
      const width = ch.codePointAt(0) < 256 ? 0.56 : 1;
      if (units + width > 10.0) {
        if (lines.length === 2) {
          lines[1] = lines[1].trimEnd() + '…';
          break;
        }
        lines.push('');
        units = 0;
      }
      lines[lines.length - 1] += ch;
      units += width;
    }
    return lines;
  }

  window.initReaderGraph = function ({root, nodes, graph, openNode, openEdge, goToNarrative}) {
    const byId = new Map(nodes.nodes.map(node => [node.id, node]));
    let level = 'L1';
    let vertical = root.getBoundingClientRect().width < 560;
    let selected = null;
    let neighborsOnly = false;
    let box = {x: 0, y: 0, width: 1, height: 1};
    let view = {...box};
    let positions = new Map();
    const nodeShapes = new Map();

    const toolbar = element('div', 'rg-toolbar');
    const layers = element('div', 'rg-layers');
    layers.setAttribute('role', 'group');
    layers.setAttribute('aria-label', '图谱层级');
    const layerButtons = new Map();
    for (const [code, name] of Object.entries(levelNames)) {
      const control = button(code + ' ' + name, () => {
        if (level === code) return;
        level = code;
        if (!graph.views[level].includes(selected)) {
          selected = null;
          neighborsOnly = false;
        }
        render();
      });
      layerButtons.set(code, control);
      layers.append(control);
    }
    const searchBox = element('div', 'rg-search');
    const search = element('input');
    search.type = 'search';
    search.placeholder = '搜索全部节点';
    search.setAttribute('aria-label', '搜索全部层级的节点');
    const results = element('div', 'rg-results');
    results.hidden = true;
    searchBox.append(search, results);
    toolbar.append(layers, searchBox);

    const canvas = element('div', 'rg-canvas');
    const diagram = svg('svg', {class: 'rg-diagram', role: 'group', 'aria-label': '知识图谱，节点和关系可用键盘选择'});
    const defs = svg('defs', {});
    const marker = svg('marker', {id: 'reader-graph-arrow', viewBox: '0 0 8 8', markerWidth: 7,
      markerHeight: 7, refX: 7.5, refY: 4, orient: 'auto', markerUnits: 'userSpaceOnUse'});
    marker.append(svg('path', {d: 'M0 0 L8 4 L0 8 z', class: 'rg-arrow'}));
    defs.append(marker);
    const world = svg('g', {});
    diagram.append(defs, world);

    const tools = element('div', 'rg-tools');
    const zoomOut = button('−', () => zoom(1.3));
    const zoomIn = button('+', () => zoom(1 / 1.3));
    zoomOut.setAttribute('aria-label', '缩小图谱');
    zoomIn.setAttribute('aria-label', '放大图谱');
    tools.append(zoomOut, zoomIn, button('适应画布', fit));
    canvas.append(diagram, tools);

    const footer = element('div', 'rg-footer');
    const stats = element('span', 'rg-count');
    stats.setAttribute('aria-live', 'polite');
    const hint = element('span', 'rg-pan-hint', '拖动平移，点击节点阅读');
    footer.append(stats, hint, element('span', 'rg-legend', '虚线表示 AI 推断'));
    const inspector = element('div', 'rg-inspector');
    root.replaceChildren(toolbar, canvas, footer, inspector);

    function updateView() {
      diagram.setAttribute('viewBox', [view.x, view.y, view.width, view.height].join(' '));
    }

    function fit(readable = false) {
      const rect = diagram.getBoundingClientRect();
      const ratio = (rect.width || 800) / (rect.height || 420);
      const width = Math.max(box.width, box.height * ratio);
      const height = width / ratio;
      view = {x: box.x + (box.width - width) / 2, y: box.y + (box.height - height) / 2, width, height};
      if (readable === true && rect.width && width > rect.width * 1.22) {
        // Keep labels legible at first open. The Fit button still shows the full map.
        const near = positions.get(selected) || positions.values().next().value;
        view.width = rect.width * 1.22;
        view.height = rect.height * 1.22;
        view.x = near.x - view.width / 2;
        view.y = near.y - view.height / 2;
        if (vertical) view.y = near.y - card.height / 2 - 18;
      }
      updateView();
    }

    function svgPoint(clientX, clientY) {
      const matrix = diagram.getScreenCTM();
      if (!matrix) return {x: view.x + view.width / 2, y: view.y + view.height / 2};
      return new DOMPoint(clientX, clientY).matrixTransform(matrix.inverse());
    }

    function zoom(factor, anchor = {x: view.x + view.width / 2, y: view.y + view.height / 2}) {
      const current = view.width / (diagram.getBoundingClientRect().width || 800);
      const next = Math.max(0.2, Math.min(Math.max(12, box.width / 150), current * factor));
      factor = next / current;
      view = {x: anchor.x + (view.x - anchor.x) * factor, y: anchor.y + (view.y - anchor.y) * factor,
        width: view.width * factor, height: view.height * factor};
      updateView();
    }

    function relationLabel(edge) {
      return byId.get(edge.source_id).title + ' · ' + relations[edge.relation] + ' · ' + byId.get(edge.target_id).title;
    }

    function drawEdge(edge, lane, withLabel) {
      const {path, x, y} = edgeGeometry(positions.get(edge.source_id), positions.get(edge.target_id), lane, vertical);
      const inferred = edge.attribution === 'ai_inference';
      const label = relationLabel(edge) + (inferred ? '（AI 推断）' : '');
      const group = svg('g', {class: 'rg-edge', tabindex: 0, role: 'button', 'data-edge-id': edge.id,
        'aria-label': label + '，查看关系和依据'});
      const line = svg('path', {d: path, class: 'rg-line' + (inferred ? ' rg-inferred' : '')});
      if (edge.relation !== 'contrasts_with') line.setAttribute('marker-end', 'url(#reader-graph-arrow)');
      group.append(svg('title', {}, label), svg('path', {d: path, class: 'rg-hit'}), line);
      const text = svg('text', {x, y: y - 4, class: 'rg-edge-label' + (withLabel ? '' : ' rg-hover-label'),
        'text-anchor': 'middle'}, relations[edge.relation]);
      group.append(text);
      return group;
    }

    function drawNode(id) {
      const node = byId.get(id);
      const {x, y} = positions.get(id);
      const group = svg('g', {class: 'rg-node', transform: 'translate(' + x + ',' + y + ')', tabindex: 0,
        role: 'button', 'data-node-id': id, 'aria-label': node.title + '，' + types[node.type] + '，' + node.level,
        'aria-pressed': String(id === selected)});
      const inferred = node.attribution === 'ai_inference';
      group.append(svg('title', {}, node.title), svg('rect', {x: -card.width / 2, y: -card.height / 2,
        width: card.width, height: card.height, rx: 7, class: 'rg-card' + (inferred ? ' rg-inferred' : '')}));
      const left = -card.width / 2 + 12;
      const meta = types[node.type] + ' · ' + node.level + (inferred ? ' · 推断' : '');
      group.append(svg('text', {x: left, y: -16, class: 'rg-meta'}, meta));
      const lines = titleLines(node.title);
      lines.forEach((line, index) => group.append(svg('text', {x: left, y: 5 + index * 17, class: 'rg-title'}, line)));
      return group;
    }

    function showInspector() {
      inspector.replaceChildren();
      inspector.hidden = !selected;
      if (!selected) return;
      const node = byId.get(selected);
      const title = element('strong', 'rg-detail-title', node.title);
      const summary = element('p', 'rg-summary', node.summary);
      const actions = element('div', 'rg-actions');
      const neighborButton = button(neighborsOnly ? '退出相邻视图' : '只看相邻', () => {
        neighborsOnly = !neighborsOnly;
        render();
        inspector.querySelector('.rg-neighbors').focus({preventScroll: true});
      }, 'rg-neighbors');
      neighborButton.setAttribute('aria-pressed', String(neighborsOnly));
      actions.append(button('阅读讲解', trigger => goToNarrative(node.id, trigger)),
        button('查看依据', trigger => openNode(node.id, trigger)), neighborButton);
      inspector.append(title, summary, actions);
    }

    function select(id) {
      const previous = selected;
      selected = id;
      if (neighborsOnly) {
        render();
      } else {
        nodeShapes.get(previous)?.setAttribute('aria-pressed', 'false');
        nodeShapes.get(id)?.setAttribute('aria-pressed', 'true');
        showInspector();
      }
    }

    function render() {
      for (const [code, control] of layerButtons) control.setAttribute('aria-pressed', String(level === code));
      const inLevel = new Set(graph.views[level]);
      const levelEdges = graph.edges.filter(e => inLevel.has(e.source_id) && inLevel.has(e.target_id));
      let ids = graph.views[level];
      if (neighborsOnly && selected) {
        const near = new Set([selected]);
        for (const edge of levelEdges) {
          if (edge.source_id === selected) near.add(edge.target_id);
          if (edge.target_id === selected) near.add(edge.source_id);
        }
        ids = ids.filter(id => near.has(id));
      }
      const visible = new Set(ids);
      const edges = levelEdges.filter(e => visible.has(e.source_id) && visible.has(e.target_id));
      positions = layout(ids, edges, vertical);
      const pairs = new Map();
      for (const edge of edges) {
        const key = [edge.source_id, edge.target_id].sort().join(' ');
        if (!pairs.has(key)) pairs.set(key, []);
        pairs.get(key).push(edge);
      }
      world.replaceChildren();
      for (const siblings of pairs.values()) {
        const gap = Math.min(20, (card.height - 16) / siblings.length);
        siblings.forEach((edge, n) => world.append(drawEdge(edge, (n - (siblings.length - 1) / 2) * gap, edges.length < 14)));
      }
      nodeShapes.clear();
      for (const id of ids) {
        const shape = drawNode(id);
        nodeShapes.set(id, shape);
        world.append(shape);
      }
      stats.textContent = level + (neighborsOnly ? ' 相邻视图' : '') + ' · ' + ids.length + ' 个节点 · ' + edges.length + ' 条关系';
      showInspector();
      const bounds = world.getBBox();
      box = {x: bounds.x - 18, y: bounds.y - 18, width: Math.max(1, bounds.width) + 36, height: Math.max(1, bounds.height) + 36};
      fit(true);
    }

    function focusNode(id) {
      if (!byId.has(id)) return;
      if (!graph.views[level].includes(id)) level = byId.get(id).level;
      selected = id;
      neighborsOnly = false;
      render();
      const point = positions.get(id);
      const rect = diagram.getBoundingClientRect();
      const targetWidth = Math.min(view.width, (rect.width || 800) * 1.2);
      const targetHeight = view.height * targetWidth / view.width;
      view = {x: point.x - targetWidth / 2, y: point.y - targetHeight / 2, width: targetWidth, height: targetHeight};
      updateView();
      nodeShapes.get(id).focus({preventScroll: true});
    }

    function showResults() {
      const query = search.value.trim().toLocaleLowerCase();
      results.replaceChildren();
      results.hidden = !query;
      if (!query) return;
      const matches = nodes.nodes.filter(node => (node.title + ' ' + node.id + ' ' + types[node.type]).toLocaleLowerCase().includes(query));
      for (const node of matches) {
        results.append(button(node.title + ' · ' + node.level, () => {
          results.hidden = true;
          search.value = '';
          focusNode(node.id);
        }));
      }
      if (!matches.length) results.append(element('span', 'rg-no-results', '没有匹配的节点'));
    }

    search.addEventListener('input', showResults);
    search.addEventListener('focus', showResults);
    search.addEventListener('keydown', event => {
      if ((event.key === 'Enter' || event.key === 'ArrowDown') && !results.hidden) {
        event.preventDefault();
        const first = results.querySelector('button');
        if (event.key === 'Enter') first?.click();
        else first?.focus();
      }
    });
    searchBox.addEventListener('focusout', event => {
      if (!searchBox.contains(event.relatedTarget)) results.hidden = true;
    });
    searchBox.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        search.focus();
        results.hidden = true;
      }
    });

    function activate(target) {
      const shape = target.closest('[data-node-id],[data-edge-id]');
      if (!shape) return;
      if (shape.hasAttribute('data-node-id')) select(shape.dataset.nodeId);
      else openEdge(shape.dataset.edgeId, shape);
    }
    diagram.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        activate(event.target);
        if (event.target.closest('[data-node-id]')) inspector.querySelector('button')?.focus();
      }
    });

    let drag = null;
    let ignoreClick = false;
    diagram.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0) return;
      ignoreClick = false;
      drag = {id: event.pointerId, x: event.clientX, y: event.clientY, view: {...view}};
    });
    diagram.addEventListener('pointermove', event => {
      if (!drag || drag.id !== event.pointerId) return;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (!ignoreClick && Math.hypot(dx, dy) < 5) return;
      ignoreClick = true;
      diagram.setPointerCapture(event.pointerId);
      const scale = diagram.getScreenCTM()?.a || 1;
      view.x = drag.view.x - dx / scale;
      view.y = drag.view.y - dy / scale;
      updateView();
    });
    const endDrag = () => { drag = null; };
    diagram.addEventListener('pointerup', endDrag);
    diagram.addEventListener('pointercancel', endDrag);
    diagram.addEventListener('pointerleave', () => { if (!ignoreClick) endDrag(); });
    diagram.addEventListener('click', event => { if (!ignoreClick) activate(event.target); });
    diagram.addEventListener('wheel', event => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      zoom(event.deltaY < 0 ? 1 / 1.18 : 1.18, svgPoint(event.clientX, event.clientY));
    }, {passive: false});

    render();
    new ResizeObserver(entries => {
      const width = entries[0].contentRect.width;
      if (!width || drag) return;
      if (vertical !== (width < 560)) {
        vertical = width < 560;
        render();
      } else {
        fit(true);
      }
    }).observe(diagram);
    return {focusNode};
  };
})();
