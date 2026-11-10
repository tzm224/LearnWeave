(() => {
  'use strict';

  const byId = id => document.getElementById(id);
  const bundle = JSON.parse(byId('reader-data').textContent);
  const nodes = new Map(bundle.nodes.nodes.map(node => [node.id, node]));
  const sources = new Map(bundle.nodes.source_refs.map(source => [source.id, source]));
  const edges = new Map(bundle.graph.edges.map(edge => [edge.id, edge]));
  const origins = {
    author_claim: '作者主张', direct_evidence: '直接证据',
    ai_inference: 'AI 推断', external_background: '外部背景'
  };
  const confidence = {high: '高', medium: '中', low: '低'};
  const labels = {
    scope: '支持范围', result: '证据结论', limitations: '局限',
    assumptions: '前提', alternatives: '替代设计', interfaces: '接口',
    applicability: '适用条件', failure_modes: '失效条件', boundaries: '边界',
    evidence_kind: '证据类型'
  };
  const evidenceKinds = {empirical: '实验', theoretical: '理论论证', worked_example: '例题推演', observation: '观察'};
  const dialog = byId('inspector');
  const body = byId('inspector-body');
  let returnPoint = null;

  function element(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (className) el.className = className;
    return el;
  }

  function action(label, callback) {
    const button = element('button', label);
    button.type = 'button';
    button.addEventListener('click', callback);
    return button;
  }

  function present(kind, title, trigger) {
    if (!dialog.open) {
      returnPoint = {trigger: trigger || document.activeElement, x: window.scrollX, y: window.scrollY};
    }
    byId('inspector-kind').textContent = kind;
    byId('inspector-title').textContent = title;
    body.replaceChildren();
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
    byId('close-inspector').focus({preventScroll: true});
  }

  byId('close-inspector').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right ||
        event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    if (!returnPoint || dialog.open) return;
    returnPoint.trigger?.focus({preventScroll: true});
    window.scrollTo(returnPoint.x, returnPoint.y);
    returnPoint = null;
  });

  function navigate(id) {
    const target = byId(id);
    if (!target) return;
    if (dialog.open) {
      returnPoint = null;
      dialog.close();
    }
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    const hash = '#' + encodeURIComponent(id);
    if (location.hash !== hash) location.hash = hash;
    target.scrollIntoView();
    if (!target.hasAttribute('tabindex')) target.tabIndex = -1;
    target.focus({preventScroll: true});
  }

  function narrativeTarget(id) {
    const target = ['step-', 'analysis-node-', 'patterns-node-'].map(prefix => prefix + id).find(key => byId(key));
    if (target) return target;
    const mention = byId('reader-article').querySelector('[data-node="' + id + '"]');
    return mention?.closest('section[id]')?.id;
  }

  function goToNarrative(id, trigger) {
    const target = narrativeTarget(id);
    if (target) navigate(target);
    else openNode(id, trigger);
  }

  function trustedOriginal(id) {
    const href = document.querySelector('a[data-original-source="' + id + '"]')?.getAttribute('href') ||
      bundle.source_links?.[id];
    if (!href) return null;
    try {
      const url = new URL(href, location.href);
      if (['file:', 'http:', 'https:'].includes(url.protocol)) return url.href;
    } catch { /* A locator remains readable when its link cannot be opened. */ }
    return null;
  }

  function sourceCard(source, showLocator = true) {
    const card = element('section', undefined, 'source-card');
    if (showLocator) card.append(element('h4', source.locator));
    card.append(element('p', source.origin === 'primary' ? '主材料' : '外部材料', 'panel-meta'));
    if (source.note) card.append(element('p', source.note));
    const topic = byId('sources-source-' + source.id);
    // Authored source descriptions can explain evidence beyond the JSON note.
    if (topic) {
      for (const p of topic.querySelectorAll('p')) {
        const text = p.cloneNode(true);
        text.querySelectorAll('a[data-original-source]').forEach(link => link.remove());
        let description = text.textContent.trim().replace(/^[—–·\s]+/, '');
        if (description.startsWith(source.locator)) {
          description = description.slice(source.locator.length).replace(/^[。.,，：:;；—–\s]+/, '');
        }
        if (description && description !== source.note && !card.textContent.includes(description)) {
          card.append(element('p', description));
        }
      }
    }
    const original = trustedOriginal(source.id);
    if (original) {
      const link = element('a', '打开原件 ↗');
      link.href = original;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      card.append(link);
    } else {
      card.append(element('p', source.uri, 'panel-meta'));
    }
    return card;
  }

  function addSources(ids) {
    body.append(element('h3', '来源与定位'));
    for (const id of ids) body.append(sourceCard(sources.get(id)));
  }

  function provenance(record) {
    body.append(element('p', origins[record.attribution] + ' · 提取把握' + confidence[record.confidence.level], 'panel-meta'));
    body.append(element('p', record.confidence.rationale));
  }

  function valueContent(value) {
    if (Array.isArray(value)) {
      const list = element('ul');
      for (const item of value) {
        const li = element('li');
        li.append(valueContent(item));
        list.append(li);
      }
      return list;
    }
    if (value && typeof value === 'object') {
      const list = element('dl');
      for (const [key, detail] of Object.entries(value)) {
        const dd = element('dd');
        dd.append(valueContent(detail));
        list.append(element('dt', labels[key] || key), dd);
      }
      return list;
    }
    return document.createTextNode(String(value ?? ''));
  }

  function evidenceDetails(record) {
    for (const [key, value] of Object.entries(record.details || {})) {
      if (Array.isArray(value) && !value.length) continue;
      body.append(element('h3', labels[key] || key));
      body.append(valueContent(key === 'evidence_kind' ? (evidenceKinds[value] || value) : value));
    }
  }

  function openNode(id, trigger) {
    const node = nodes.get(id);
    if (!node) return;
    present('节点与依据', node.title, trigger);
    body.append(element('p', node.summary));
    provenance(node);
    evidenceDetails(node);
    const support = bundle.graph.edges.filter(edge => edge.relation === 'supports' && edge.target_id === id);
    if (support.length) {
      body.append(element('h3', '支持这个结论的证据'));
      for (const edge of support) {
        const card = element('div', undefined, 'source-card');
        card.append(element('p', edge.rationale), action(nodes.get(edge.source_id).title, () => openNode(edge.source_id)));
        body.append(card);
      }
    }
    addSources(node.source_refs);
    const actions = element('div', undefined, 'panel-actions');
    if (narrativeTarget(id)) actions.append(action('阅读讲解', () => goToNarrative(id)));
    actions.append(action('在图中定位', () => { navigate('graph'); graphUI.focusNode(id); }));
    body.append(actions);
  }

  function openEdge(id, trigger) {
    const edge = edges.get(id);
    if (!edge) return;
    const arrow = edge.relation === 'contrasts_with' ? ' ↔ ' : ' → ';
    present('关系与依据', nodes.get(edge.source_id).title + arrow + nodes.get(edge.target_id).title, trigger);
    body.append(element('h3', '为什么相连'), element('p', edge.rationale));
    provenance(edge);
    if (edge.relation === 'supports') {
      const evidence = nodes.get(edge.source_id);
      evidenceDetails(evidence);
    }
    addSources(edge.evidence_refs);
  }

  function openSource(id, trigger) {
    const source = sources.get(id);
    if (!source) return;
    present('来源与依据', source.locator, trigger);
    // A section or paragraph may reference more than one claim. Keep provenance attached to its claim.
    const local = trigger.closest('p, li, h2, h3, h4');
    const context = trigger.closest('[data-context-node]')?.dataset.contextNode;
    const candidates = new Set([context, ...Array.from(local?.querySelectorAll('[data-node]') || [], el => el.dataset.node)]);
    const claims = [...candidates].map(key => nodes.get(key)).filter(node => node?.source_refs.includes(id));
    for (const claim of claims) {
      body.append(element('h3', claim.title), element('p', claim.summary));
      provenance(claim);
      if (claim.type === 'evidence') evidenceDetails(claim);
    }
    body.append(sourceCard(source, false));
    if (!claims.length) {
      const related = [...nodes.values()].filter(node => node.source_refs.includes(id));
      if (related.length) {
        body.append(element('h3', '引用此处的节点'));
        const actions = element('div', undefined, 'panel-actions');
        for (const node of related) actions.append(action(node.title + ' · ' + origins[node.attribution], () => openNode(node.id)));
        body.append(actions);
      }
    }
  }

  const graphUI = window.initReaderGraph({root: byId('reader-graph'), nodes: bundle.nodes, graph: bundle.graph,
    openNode, openEdge, goToNarrative});

  byId('reader-article').addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (link.dataset.source && sources.has(link.dataset.source)) {
      event.preventDefault();
      openSource(link.dataset.source, link);
    } else if (link.dataset.node && nodes.has(link.dataset.node)) {
      event.preventDefault();
      openNode(link.dataset.node, link);
    }
  });

  for (const math of document.querySelectorAll('#reader-article .math')) {
    const raw = math.textContent.trim();
    const displayMode = math.dataset.display === 'true' || math.tagName === 'DIV';
    // The article renderer normalizes both inline and display delimiters to two characters per side.
    const tex = raw.slice(2, -2).trim();
    try {
      window.katex.render(tex, math, {output: 'mathml', displayMode, trust: false, throwOnError: true});
    } catch {
      math.textContent = raw;
      math.classList.add('math-error');
      math.title = '公式未能排版，显示原式';
    }
  }

  function revealHashTarget() {
    const target = byId(location.hash.slice(1));
    if (!target) return;
    let detail = target.closest('details');
    let opened = false;
    while (detail) {
      if (!detail.open) { detail.open = true; opened = true; }
      detail = detail.parentElement?.closest('details');
    }
    if (opened) target.scrollIntoView();
  }
  window.addEventListener('hashchange', revealHashTarget);
  byId('reader-article').addEventListener('click', event => {
    const hash = event.target.closest('a')?.hash;
    if (!event.defaultPrevented && hash && hash === location.hash) revealHashTarget();
  });
  revealHashTarget();

  const toc = document.querySelector('.toc');
  const mobile = window.matchMedia('(max-width: 760px)');
  function adjustToc() { toc.open = !mobile.matches; }
  adjustToc();
  mobile.addEventListener('change', adjustToc);
  toc.addEventListener('click', event => {
    if (mobile.matches && event.target.closest('a[href^="#"]')) toc.open = false;
  });

  const tocLinks = [...toc.querySelectorAll('a[href^="#"]')];
  const sections = tocLinks.map(link => byId(link.hash.slice(1)));
  const viewLinks = [...document.querySelectorAll('.view-nav a')];
  let scheduled = false;
  function markCurrent() {
    scheduled = false;
    let active = 0;
    sections.forEach((section, index) => {
      if (section && section.getBoundingClientRect().top <= Math.min(180, innerHeight * .22)) active = index;
    });
    tocLinks.forEach((link, index) => {
      if (index === active) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
    const graphActive = tocLinks[active].hash === '#graph';
    viewLinks.forEach(link => {
      if ((link.hash === '#graph') === graphActive) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  function onScroll() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(markCurrent); }
  }
  window.addEventListener('scroll', onScroll, {passive: true});
  window.addEventListener('resize', onScroll);
  markCurrent();
})();
