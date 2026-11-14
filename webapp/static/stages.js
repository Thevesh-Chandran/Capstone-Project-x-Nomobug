'use strict';
/* Today, Performance and Warranty risk pages. Plain SVG charts and DOM only:
   no inline style attributes (strict CSP), values set through CSSOM. */
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  // Chart colours: one distinct colour per series, read from the stylesheet's tokens.
  const tok = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const C = {
    get blue() { return tok('--chart-model'); }, // the model / main series
    get amber() { return tok('--chart-rule'); }, // the simple rule or comparison
    get teal() { return tok('--chart-actual'); }, // recorded actuals
    get coral() { return tok('--chart-miss'); }, // misses, things that raise risk
    get grey() { return tok('--chart-neutral'); }, // random order or neutral baseline
    get ink() { return tok('--color-ink'); },
  };
  const g = id => document.getElementById(id);
  const mk = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined && text !== null) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const s = (tag, attrs = {}, text) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, String(attrs[k]));
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const link = (text, href, cls) => {
    const a = mk('a', text, cls);
    a.href = href;
    return a;
  };
  const nf = new Intl.NumberFormat('en-MY', { maximumFractionDigits: 0 });
  const rm = v => (v == null ? '-' : 'RM ' + nf.format(Math.round(v)));
  const rmShort = v => {
    if (v == null) return '-';
    const a = Math.abs(v);
    return (
      (v < 0 ? '-' : '') +
      'RM ' +
      (a >= 1e6
        ? (a / 1e6).toFixed(2) + 'M'
        : a >= 1e4
          ? Math.round(a / 1e3) + 'k'
          : a >= 1e3
            ? (a / 1e3).toFixed(1) + 'k'
            : nf.format(a))
    );
  };
  const pct = (v, d = 0) => (v == null || !isFinite(v) ? '-' : (v * 100).toFixed(d) + '%');
  const toDate = d => {
    const raw = String(d);
    const local = raw.includes('T')
      ? new Date(raw).toLocaleDateString('en-CA', { timeZone: 'Asia/Kuala_Lumpur' })
      : raw.slice(0, 10);
    return new Date(local + 'T00:00:00');
  };
  const day = d => toDate(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const weekday = d =>
    toDate(d).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
  const longDay = d =>
    toDate(d).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
  const addDays = (d, n) => {
    const x = toDate(d);
    x.setDate(x.getDate() + n);
    return x.toISOString().slice(0, 10);
  };
  const month = m => toDate(m + '-01').toLocaleDateString('en-GB', { month: 'short' });
  const monthYear = m => toDate(m + '-01').toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
  const title = t => {
    let v = String(t || '')
      .trim()
      .replace(/\s+/g, ' ')
      .replace(/\(\s+/g, '(')
      .replace(/\s+\)/g, ')');
    if (v === v.toUpperCase() || v === v.toLowerCase())
      v = v.toLowerCase().replace(/(^|[\s(])([a-z])/g, (m, p, c) => p + c.toUpperCase());
    return v;
  };
  let data = null,
    work = null,
    loading = null,
    current = null;

  /* ---------- tooltip ---------- */
  const tip = mk('div', undefined, 'chart-tip');
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  document.body.append(tip);
  function showTip(evt, head, rows) {
    tip.replaceChildren(mk('strong', head));
    rows.forEach(([label, value, color]) => {
      const r = mk('div', undefined, 'chart-tip-row');
      const sw = mk('i');
      if (color) sw.style.setProperty('--sw', color);
      r.append(sw, mk('span', label), mk('b', value));
      tip.append(r);
    });
    tip.hidden = false;
    const pad = 12,
      w = tip.offsetWidth,
      h = tip.offsetHeight;
    let x = evt.clientX + pad,
      y = evt.clientY + pad;
    if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }
  const hideTip = () => {
    tip.hidden = true;
  };
  function niceMax(v) {
    if (v <= 0) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    const n = v / p;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p;
  }
  const width = host => Math.max(280, Math.round(host.clientWidth || 600));
  const later = fn => requestAnimationFrame(() => requestAnimationFrame(fn));

  /* ---------- line chart: soft area under the main series ---------- */
  function lineChart(
    host,
    { labels, series, height = 240, format = nf.format, xLabel = l => l, tipTitle = l => l, max: fixedMax },
  ) {
    host.replaceChildren();
    const w = width(host),
      h = height;
    const m = { t: 12, r: 12, b: 26, l: 52 };
    const iw = w - m.l - m.r,
      ih = h - m.t - m.b;
    const max =
      fixedMax || niceMax(Math.max(...series.flatMap(se => se.values).filter(v => v != null), 1) * 1.05);
    const x = i => m.l + (labels.length < 2 ? iw / 2 : (i * iw) / (labels.length - 1)),
      y = v => m.t + ih - (v / max) * ih;
    const svg = s('svg', {
      viewBox: `0 0 ${w} ${h}`,
      width: w,
      height: h,
      class: 'chart',
      role: 'img',
      'aria-label': series.map(se => se.label).join(', '),
    });
    const defs = s('defs');
    svg.append(defs);
    for (let i = 0; i <= 4; i++) {
      const v = (max * i) / 4,
        yy = y(v);
      svg.append(
        s('line', { x1: m.l, x2: m.l + iw, y1: yy, y2: yy, class: i ? 'c-grid' : 'c-base' }),
        s('text', { x: m.l - 8, y: yy + 4, class: 'c-axis', 'text-anchor': 'end' }, format(v)),
      );
    }
    const every = Math.max(1, Math.ceil(labels.length / Math.max(2, Math.floor(iw / 56))));
    labels.forEach((l, i) => {
      if (i % every === 0 || i === labels.length - 1)
        svg.append(
          s(
            'text',
            {
              x: x(i),
              y: h - 6,
              class: 'c-axis',
              'text-anchor': i === 0 ? 'start' : i === labels.length - 1 ? 'end' : 'middle',
            },
            xLabel(l),
          ),
        );
    });
    series.forEach(se => {
      const pts = se.values.map((v, i) => (v == null ? null : [x(i), y(v)])).filter(Boolean);
      if (!pts.length) return;
      const d = 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('L');
      if (se.area) {
        const id = 'ga' + Math.random().toString(36).slice(2);
        const lg = s('linearGradient', { id, x1: 0, y1: 0, x2: 0, y2: 1 });
        lg.append(
          s('stop', { offset: '0%', 'stop-color': se.color, 'stop-opacity': 0.28 }),
          s('stop', { offset: '100%', 'stop-color': se.color, 'stop-opacity': 0 }),
        );
        defs.append(lg);
        svg.append(
          s('path', {
            d: d + `L${pts[pts.length - 1][0]},${m.t + ih}L${pts[0][0]},${m.t + ih}Z`,
            fill: `url(#${id})`,
          }),
        );
      }
      const path = s('path', {
        d,
        fill: 'none',
        stroke: se.color,
        'stroke-width': se.dashed ? 2 : 2.5,
        'stroke-linejoin': 'round',
        'stroke-linecap': 'round',
      });
      if (se.dashed) path.setAttribute('stroke-dasharray', '4 4');
      svg.append(path);
      const last = pts[pts.length - 1];
      if (!se.dashed)
        svg.append(
          s('circle', {
            cx: last[0],
            cy: last[1],
            r: 4,
            fill: tok('--color-paper-3'),
            stroke: se.color,
            'stroke-width': 2.5,
          }),
        );
    });
    const cross = s('line', { y1: m.t, y2: m.t + ih, class: 'c-cross', visibility: 'hidden' });
    svg.append(cross);
    const hit = s('rect', { x: m.l, y: m.t, width: iw, height: ih, fill: 'transparent' });
    svg.append(hit);
    hit.addEventListener('pointermove', e => {
      const r = svg.getBoundingClientRect();
      const px = (e.clientX - r.left) * (w / r.width);
      const i = Math.max(
        0,
        Math.min(labels.length - 1, Math.round((px - m.l) / (iw / Math.max(1, labels.length - 1)))),
      );
      cross.setAttribute('x1', x(i));
      cross.setAttribute('x2', x(i));
      cross.setAttribute('visibility', 'visible');
      showTip(
        e,
        tipTitle(labels[i]),
        series.filter(se => se.values[i] != null).map(se => [se.label, format(se.values[i]), se.color]),
      );
    });
    hit.addEventListener('pointerleave', () => {
      cross.setAttribute('visibility', 'hidden');
      hideTip();
    });
    host.append(svg);
  }

  /* ---------- paired columns ---------- */
  function columns(
    host,
    { labels, series, height = 220, xLabel = l => l, tipTitle = l => l, format = nf.format },
  ) {
    host.replaceChildren();
    const w = width(host),
      h = height;
    const m = { t: 10, r: 6, b: 26, l: 40 };
    const iw = w - m.l - m.r,
      ih = h - m.t - m.b;
    const max = niceMax(Math.max(...series.flatMap(se => se.values), 1) * 1.05);
    const svg = s('svg', {
      viewBox: `0 0 ${w} ${h}`,
      width: w,
      height: h,
      class: 'chart',
      role: 'img',
      'aria-label': series.map(x => x.label).join(', '),
    });
    for (let i = 0; i <= 3; i++) {
      const v = (max * i) / 3,
        yy = m.t + ih - (v / max) * ih;
      svg.append(
        s('line', { x1: m.l, x2: w - m.r, y1: yy, y2: yy, class: i ? 'c-grid' : 'c-base' }),
        s('text', { x: m.l - 8, y: yy + 4, class: 'c-axis', 'text-anchor': 'end' }, format(v)),
      );
    }
    const band = iw / labels.length,
      k = series.length,
      gw = Math.min(band * 0.62, k * 14),
      bw = (gw - (k - 1) * 2) / k;
    const every = band < 40 ? 2 : 1;
    labels.forEach((l, i) => {
      const g0 = m.l + band * i + (band - gw) / 2;
      series.forEach((se, j) => {
        const v = se.values[i] || 0,
          bh = (v / max) * ih;
        if (bh > 0)
          svg.append(
            s('rect', {
              x: g0 + j * (bw + 2),
              y: m.t + ih - bh,
              width: bw,
              height: bh,
              fill: se.color,
              rx: Math.min(3, bw / 2),
            }),
          );
      });
      const hr = s('rect', { x: m.l + band * i, y: m.t, width: band, height: ih, fill: 'transparent' });
      svg.append(hr);
      hr.addEventListener('pointermove', e =>
        showTip(
          e,
          tipTitle(l),
          series.map(se => [se.label, format(se.values[i]), se.color]),
        ),
      );
      hr.addEventListener('pointerleave', hideTip);
      if (i % every === 0)
        svg.append(
          s(
            'text',
            { x: m.l + band * i + band / 2, y: h - 6, class: 'c-axis', 'text-anchor': 'middle' },
            xLabel(l),
          ),
        );
    });
    host.append(svg);
  }

  /* ---------- small marks ---------- */
  function spark(values, { w = 120, h = 34 } = {}) {
    const v = values.filter(x => x != null);
    const svg = s('svg', {
      viewBox: `0 0 ${w} ${h}`,
      width: w,
      height: h,
      class: 'spark',
      'aria-hidden': 'true',
    });
    if (v.length < 2) return svg;
    const lo = Math.min(...v),
      hi = Math.max(...v),
      r = hi - lo || 1;
    const pts = v.map((x, i) => [(i * (w - 4)) / (v.length - 1) + 2, h - 3 - ((x - lo) / r) * (h - 8)]);
    const d = 'M' + pts.map(p => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('L');
    svg.append(
      s('path', { d: d + `L${pts[pts.length - 1][0]},${h}L2,${h}Z`, class: 'spark-area' }),
      s('path', { d, class: 'spark-line' }),
      s('circle', { cx: pts[pts.length - 1][0], cy: pts[pts.length - 1][1], r: 2.6, class: 'spark-dot' }),
    );
    return svg;
  }
  function ring(share, label, { size = 44, stroke = 5 } = {}) {
    const r = (size - stroke) / 2,
      c = 2 * Math.PI * r;
    const svg = s('svg', {
      viewBox: `0 0 ${size} ${size}`,
      width: size,
      height: size,
      class: 'ring',
      role: 'img',
      'aria-label': label,
    });
    svg.append(
      s('circle', { cx: size / 2, cy: size / 2, r, class: 'ring-track', 'stroke-width': stroke }),
      s('circle', {
        cx: size / 2,
        cy: size / 2,
        r,
        class: 'ring-fill',
        'stroke-width': stroke,
        'stroke-dasharray': `${(Math.max(0, Math.min(1, share)) * c).toFixed(1)} ${c.toFixed(1)}`,
        transform: `rotate(-90 ${size / 2} ${size / 2})`,
      }),
      s('text', { x: size / 2, y: size / 2 + 4, 'text-anchor': 'middle', class: 'ring-text' }, label),
    );
    return svg;
  }
  const initials = n =>
    title(n)
      .replace(/\(.*?\)/g, '')
      .split(/\s+/)
      .filter(w => /^[A-Za-z]/.test(w))
      .slice(0, 2)
      .map(w => w[0].toUpperCase())
      .join('') || '?';

  /* ---------- building blocks ---------- */
  function block(heading, { more, note, cls = '' } = {}) {
    const b = mk('section', undefined, 'block ' + cls);
    const h = mk('header', undefined, 'block-head');
    const t = mk('div');
    t.append(mk('h2', heading));
    if (note) t.append(mk('p', note, 'block-note'));
    h.append(t);
    if (more) h.append(link(more[0], more[1], 'block-more'));
    b.append(h);
    return b;
  }
  function hero(titleText, lead, stats) {
    const h = mk('section', undefined, 'hero');
    const top = mk('div', undefined, 'hero-top');
    const t = mk('div');
    t.append(mk('h1', titleText), mk('p', lead, 'hero-lead'));
    top.append(t);
    h.append(top);
    const row = mk('div', undefined, 'hero-stats');
    stats.forEach(st => {
      const c = mk('div', undefined, 'hstat');
      const txt = mk('div', undefined, 'hstat-text');
      txt.append(mk('span', st.label, 'hstat-label'), mk('strong', st.value, 'hstat-value'));
      if (st.note) {
        const n = mk('span', undefined, 'hstat-note');
        if (st.tone) {
          n.append(mk('b', st.tone[0], 'delta ' + st.tone[1]), document.createTextNode(' ' + st.note));
        } else n.textContent = st.note;
        txt.append(n);
      }
      c.append(txt);
      if (st.mark) c.append(st.mark);
      row.append(c);
    });
    h.append(row);
    return h;
  }
  function rowList(items, empty) {
    if (!items.length) return mk('p', empty, 'block-empty');
    const ul = mk('ul', undefined, 'rows');
    items.forEach(it => {
      const li = mk('li', undefined, 'lrow');
      const a = mk('a', undefined, 'lrow-link');
      a.href = it.href || '#';
      const av = mk(
        'span',
        it.avatar || initials(it.name),
        'avatar' + (it.avatarCls ? ' ' + it.avatarCls : ''),
      );
      const main = mk('div', undefined, 'row-main');
      main.append(mk('span', it.name, 'row-name'));
      if (it.sub) main.append(mk('span', it.sub, 'row-sub'));
      const side = mk('div', undefined, 'row-side');
      if (it.value) side.append(mk('span', it.value, 'row-value'));
      if (it.chip) side.append(mk('span', it.chip[0], 'chip ' + (it.chip[1] || '')));
      a.append(av, main);
      if (it.mark) a.append(it.mark);
      a.append(side);
      li.append(a);
      ul.append(li);
    });
    return ul;
  }
  const bar = (share, cls = '') => {
    const b = mk('span', undefined, 'mbar ' + cls);
    const f = mk('i');
    f.style.setProperty('--w', Math.max(0, Math.min(100, share * 100)).toFixed(1) + '%');
    b.append(f);
    return b;
  };
  const greet = () => {
    const hr = Number(
      new Date().toLocaleString('en-GB', { timeZone: 'Asia/Kuala_Lumpur', hour: 'numeric', hour12: false }),
    );
    return hr < 12 ? 'Good morning' : hr < 18 ? 'Good afternoon' : 'Good evening';
  };
  const daysUntil = d =>
    Math.round(
      (toDate(d) - toDate(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kuala_Lumpur' }))) / 864e5,
    );

  /* ---------- live check-in plan (prescriptive step) ---------- */
  let rplan = null,
    rcalls = 'all';
  async function loadPlan(calls) {
    const r = await fetch('/api/return-risk?calls=' + calls);
    const v = await r.json();
    if (!r.ok) throw new Error(v.error || 'Unavailable');
    rplan = v;
    rcalls = calls;
    return v;
  }
  function checkInRows(list) {
    return rowList(
      list.map(c => {
        const due = daysUntil(c.call_on);
        return {
          name: title(c.name),
          sub: `${c.sale_id}, service ${c.service}, serviced ${day(c.serviced)}${c.why.length ? ', ' + c.why.join(', ') : ''}`,
          value: pct(c.chance) + ' chance',
          href: '#customers',
          mark: ring(Math.min(1, c.chance / 0.4), pct(c.chance), { size: 38, stroke: 4 }),
          chip: [due <= 0 ? 'Call today' : 'Call ' + weekday(c.call_on), due <= 0 ? 'dark' : ''],
        };
      }),
      'No open service windows to check this week.',
    );
  }
  function checkInManage(p, after) {
    if (!p.check_ins.length && !(p.done || []).length)
      return mk('p', 'No open service windows to check this week.', 'block-empty');
    const ul = mk('ul', undefined, 'rows checkins');
    const choices = p.choices || {};
    const row = (c, done) => {
      const li = mk('li', undefined, 'lrow crow' + (done ? ' is-done' : ''));
      const due = daysUntil(c.call_on);
      const top = mk('div', undefined, 'crow-top');
      const av = mk('span', initials(title(c.name)), 'avatar');
      const main = mk('div', undefined, 'row-main');
      main.append(
        mk(
          'span',
          title(c.name) + (c.pilot_arm === 'call' && p.pilot && p.pilot.active ? '  ·  pilot' : ''),
          'row-name',
        ),
        mk(
          'span',
          `${c.sale_id}, service ${c.service}, serviced ${day(c.serviced)}${c.why.length ? ', ' + c.why.join(', ') : ''}`,
          'row-sub',
        ),
      );
      const history = link('Open customer history', '#customers', 'block-more');
      history.addEventListener('click', () => sessionStorage.setItem('cp2_map_sale', c.sale_id));
      main.append(history);
      const side = mk('div', undefined, 'row-side');
      side.append(mk('span', pct(c.chance) + ' estimated return risk', 'row-value'));
      if (c.outcome)
        side.append(mk('span', c.outcome.label, 'chip ' + (c.outcome.status === 'no_answer' ? '' : 'dark')));
      else
        side.append(
          mk(
            'span',
            due <= 0 ? 'Call today' : 'Call ' + weekday(c.call_on),
            'chip ' + (due <= 0 ? 'dark' : ''),
          ),
        );
      top.append(av, main, ring(Math.min(1, c.chance / 0.4), pct(c.chance), { size: 38, stroke: 4 }), side);
      li.append(top);
      if (!p.log_available) {
        ul.append(li);
        return;
      }
      const f = mk('form', undefined, 'crow-form');
      const sel = mk('select');
      sel.setAttribute('aria-label', 'Check-in result for ' + title(c.name));
      sel.append(new Option('Record result', ''));
      Object.entries(choices).forEach(([k, l]) => sel.append(new Option(l, k)));
      if (c.outcome) sel.value = c.outcome.status;
      const nt = mk('input');
      nt.type = 'text';
      nt.maxLength = 400;
      nt.placeholder = 'Note (optional)';
      nt.setAttribute('aria-label', 'Note');
      if (c.outcome) nt.value = c.outcome.note || '';
      const mn = mk('input');
      mn.type = 'number';
      mn.min = 0;
      mn.max = 120;
      mn.step = 1;
      mn.placeholder = 'Min';
      mn.className = 'crow-min';
      mn.setAttribute('aria-label', 'Call minutes');
      if (c.outcome && c.outcome.minutes != null) mn.value = c.outcome.minutes;
      const bt = mk('button', 'Save', 'btn btn-dark btn-sm');
      bt.type = 'submit';
      const msg = mk('span', '', 'crow-msg');
      f.append(sel, nt, mn, bt, msg);
      f.addEventListener('submit', async e => {
        e.preventDefault();
        if (!sel.value) {
          msg.textContent = 'Choose a result first';
          return;
        }
        bt.disabled = true;
        msg.textContent = 'Saving';
        try {
          const r = await fetch('/api/return-risk/outcome', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sale_id: c.sale_id,
              serviced: c.serviced,
              status: sel.value,
              note: nt.value,
              minutes: mn.value,
              revision: p.revision,
            }),
          });
          const v = await r.json();
          if (!r.ok) throw new Error(v.error || 'Could not save');
          msg.textContent = 'Saved';
          after && after();
        } catch (err) {
          msg.textContent = err.message;
          bt.disabled = false;
        }
      });
      li.append(f);
      ul.append(li);
    };
    let shown = 0;
    const more = mk('button', 'Show 20 more services', 'btn');
    const showMore = () => {
      const end = Math.min(shown + 20, p.check_ins.length);
      p.check_ins.slice(shown, end).forEach(c => row(c, false));
      shown = end;
      more.textContent = `Show more (${shown} of ${p.check_ins.length} shown)`;
      more.hidden = shown >= p.check_ins.length;
      ul.append(more);
    };
    more.addEventListener('click', showMore);
    showMore();
    if ((p.done || []).length) {
      ul.append(mk('li', `Already reached (${p.done.length}), not called again`, 'crow-divider'));
      p.done.forEach(c => row(c, true));
    }
    return ul;
  }
  function outcomeStats(o) {
    const d = mk('div', undefined, 'plan-stats outcome-stats');
    if (!o || !o.recorded) {
      d.append(
        mk(
          'p',
          'No check-ins recorded yet. This log records staff activity and customer-reported issues; a separate approved study is needed to measure any effect on returns.',
          'block-note',
        ),
      );
      return d;
    }
    [
      [nf.format(o.recorded), 'check-ins recorded'],
      [nf.format(o.reached), 'customers reached'],
      [o.issue_share == null ? '-' : pct(o.issue_share), 'of reached had an issue'],
      [nf.format(o.counts.visit_booked), 'return visits booked early'],
      [o.mean_minutes == null ? '-' : nf.format(o.mean_minutes) + ' min', 'average call'],
    ].forEach(([v, l]) => {
      const x = mk('div');
      x.append(mk('strong', v), mk('span', l));
      d.append(x);
    });
    return d;
  }
  function planNote(p) {
    if (!p || p.status !== 'live')
      return p && p.status === 'stale'
        ? 'The service feed needs refreshing before a customer list can be used.'
        : 'The current service feed is not available yet. Historical model results remain available below.';
    const pl =
      p.pilot && p.pilot.active
        ? ` Check-in pilot until ${day(p.pilot.calls_to)}: ${p.pilot.held_back} higher-risk customers are held back as the comparison group; please do not call them.`
        : '';
    return (
      pl.trim() +
      (pl ? ' ' : '') +
      `${p.check_ins.length} eligible services are listed for review. Open a customer history, contact the customer, then save the result below. Risk estimates use service records through ${day(p.predictors_through)}; they are not confirmed return visits.`
    );
  }

  /* =========================== Today =========================== */
  // Experimental model scores are kept in research; Today lists only source-backed work.
  function tile(title, text, href) {
    const a = mk('a', undefined, 'tile');
    a.href = href;
    a.append(mk('strong', title), mk('span', text));
    return a;
  }
  function renderToday(root) {
    root.replaceChildren();
    const R = data.return_risk || {},
      E = R.evaluation,
      live = rplan && rplan.status === 'live',
      o = live ? rplan.outcomes : null;
    const intro = mk('section', undefined, 'solution-intro');
    intro.append(
      mk('h1', 'Workspace'),
      mk(
        'p',
        'Recent services, customer follow-up and booking plans.',
        'solution-lead',
      ),
    );
    const actions = mk('div', undefined, 'solution-actions');
    actions.append(link('Open service follow-up', '#returns', 'btn btn-dark'));
    intro.append(actions);
    root.append(intro);
    const layout = mk('div', undefined, 'solution-grid');
    const main = mk('div'),
      side = mk('aside');
    layout.append(main, side);
    root.append(layout);
    const queue = block('Service follow-up', {
      more: ['Open workspace', '#returns'],
      note: 'The working list and recorded customer outcomes.',
    });
    const status = mk('div', undefined, 'connection-state ' + (live ? 'connected' : ''));
    status.append(
      mk('strong', live ? 'Recent service list available' : 'Live service list not connected'),
      mk(
        'p',
        live
          ? `Services recorded through ${day(rplan.predictors_through)}. Review the latest Calendar before contacting a customer.`
          : planNote(rplan),
      ),
    );
    queue.append(status);
    if (live) {
      const stats = mk('div', undefined, 'plan-stats');
      [
        [rplan.eligible, 'services eligible'],
        [o ? o.reached : 0, 'customers reached'],
        [o ? o.counts.issue_found + o.counts.visit_booked : 0, 'issues recorded'],
      ].forEach(([v, l]) => {
        const x = mk('div');
        x.append(mk('strong', nf.format(v)), mk('span', l));
        stats.append(x);
      });
      queue.append(stats, checkInRows(rplan.check_ins.slice(0, 4)));
    } else
      queue.append(
        mk(
          'p',
          'Historical model evidence is available now. A current predictor feed is still needed before a real customer list can be used.',
          'side-text',
        ),
        link('Explore the model evidence', '#returns', 'block-more'),
      );
    main.append(queue);
    const tools = block('When a customer needs help');
    const tiles = mk('div', undefined, 'tiles');
    tiles.append(
      tile('Customer history', 'Check the programme and earlier visits', '#customers'),
      tile('Bookings & workload', 'Team calendars and next week\'s workload', '#plan'),
      tile('Return-visit map', 'Inspect the recorded local pattern', '/maps'),
    );
    tools.append(tiles);
    main.append(tools);
    const payments = block('Payment reminders', { more: ['Open reminders', '#home'] });
    const due = ((work && work.tasks) || []).filter(t => t.review_kind === 'upcoming');
    payments.append(
      mk(
        'p',
        `${due.length} recorded reminders fall in the next seven days. Confirm the latest Sales balance before contacting a client.`,
        'side-text',
      ),
    );
    main.append(payments);
    const ev = block('What the model contributes', { more: ['See the assessment', '#returns'] });
    if (E) {
      const me = E.compare['Return-risk score (chosen)'];
      const stats = mk('dl', undefined, 'evidence-summary');
      [
        [nf.format(E.services), 'historically assessed services'],
        [nf.format(E.returns), 'recorded returns'],
        [me.auc.toFixed(2), 'ranking AUC (0.5 random; 1 perfect)'],
      ].forEach(([v, l]) => {
        stats.append(mk('dt', v), mk('dd', l));
      });
      ev.append(
        stats,
        mk(
          'p',
          'Historical estimates support a review. They do not confirm a warranty claim or show that follow-up calls reduce returns.',
          'side-text',
        ),
      );
    }
    side.append(ev);
    // Weekly capacity suggestion: the hours forecast plus a buffer, and how much of a week goes to return visits.
    const hrs = (data.predictive.forecasts || []).find(f => f.id === 'booked_hours_h1');
    const pb = (data.return_risk || {}).problem || {};
    if (hrs && !data.source_stale) {
      const plan = hrs.prediction + hrs.mae;
      const returnHours = null; // No verified duration per return visit is available.
      const cap = block('Next week: staffing scenario', { cls: 'block-sky', more: ['Bookings & workload', '#plan'] });
      const big = mk('p', undefined, 'meter-big');
      big.append(mk('strong', nf.format(plan) + ' h'), document.createTextNode(' of appointments to staff for'));
      cap.append(
        big,
        mk(
          'p',
          `Forecast ${nf.format(hrs.prediction)} h plus ${nf.format(hrs.mae)} h illustrative allowance, equal to the historical average absolute error; this is not a guaranteed upper bound.` +
            (returnHours != null
              ? ` About ${nf.format(returnHours)} h of a typical week goes to return visits; calling the customers on the check-in list aims to bring this down.`
              : ''),
          'side-text',
        ),
      );
      const saved = work && work.settings && work.settings.capacity_hours;
      if (saved != null && Number.isFinite(Number(saved)))
        cap.append(
          mk(
            'p',
            saved >= plan
              ? `Saved team capacity ${nf.format(saved)} h covers it.`
              : `Saved team capacity ${nf.format(saved)} h is about ${nf.format(plan - saved)} h short: consider backup cover.`,
            'side-text ' + (saved >= plan ? 'good' : 'warn'),
          ),
        );
      if (saved == null)
        cap.append(mk('p', 'Enter available team hours in Bookings & workload to calculate the staffing gap.', 'side-text'));
      side.append(cap);
    }
    const readiness = block('Source status');
    readiness.append(
      mk(
        'p',
        `Sales and reporting: ${day(data.source_updated)}${data.source_stale ? ', refresh needed' : ''}.`,
        'side-text',
      ),
      mk(
        'p',
        'The live predictor connection and the saved historical assessment have separate update cycles.',
        'side-text',
      ),
    );
    side.append(readiness);
  }

  /* =========================== Performance =========================== */
  const fmtVal = (v, f) =>
    v == null ? '-' : f === 'rm' ? rmShort(v) : f === 'pct' ? pct(v, 1) : nf.format(v);
  const STATUS = { good: 'On track', warn: 'Watch', bad: 'Behind', unknown: 'No data' };
  const confirmedRow = r => r.target_status === 'confirmed';
  function renderPerformance(root) {
    const F = data.performance;
    root.replaceChildren();
    const scored = F.scorecard.filter(confirmedRow);
    const counts = { good: 0, warn: 0, bad: 0, unknown: 0 };
    scored.forEach(r => counts[r.status]++);
    root.append(
      hero('Performance', 'Historical comparisons. Owner targets are not scored until they are confirmed.', [
        {
          label: 'On track',
          value: String(counts.good),
          note: `of ${scored.length} scored measures`,
          mark: ring(scored.length ? counts.good / scored.length : 0, `${counts.good}/${scored.length}`),
        },
        { label: 'Watch or behind', value: String(counts.warn + counts.bad), note: 'scored measures' },
        {
          label: 'Awaiting a target',
          value: String(F.scorecard.length - scored.length),
          note: 'owner to confirm',
        },
      ]),
    );
    const b1 = block('Measures');
    const t = mk('table', undefined, 'table score-table');
    const th = mk('thead');
    const hr = mk('tr');
    ['Measure', 'Recorded', 'Owner target', 'Reference', 'Status'].forEach((x, i) =>
      hr.append(mk('th', x, i === 1 || i === 2 ? 'num' : '')),
    );
    th.append(hr);
    const tb = mk('tbody');
    F.scorecard.forEach(r => {
      const ok = confirmedRow(r);
      const tr = mk('tr');
      tr.append(mk('td', r.metric, 'strong'));
      const now = mk('td', undefined, 'num');
      now.append(mk('span', fmtVal(r.value, r.format)));
      if (r.change != null)
        now.append(
          mk(
            'small',
            (r.change >= 0 ? ' +' : ' -') + pct(Math.abs(r.change), 1),
            r.change >= 0 ? 'up' : 'down',
          ),
        );
      tr.append(now);
      tr.append(mk('td', ok ? fmtVal(r.benchmark, r.format) : 'Not set', 'num' + (ok ? '' : ' muted')));
      const lab = mk('td', undefined, 'muted');
      if (r.target_status && r.target_status !== 'confirmed') {
        lab.textContent = 'Owner target not confirmed';
      } else
        lab.textContent =
          r.benchmark_label + (r.benchmark == null ? '' : ' (' + fmtVal(r.benchmark, r.format) + ')');
      tr.append(lab);
      const st = mk('td');
      st.append(
        mk('span', ok ? STATUS[r.status] : 'Target not set', 'status s-' + (ok ? r.status : 'unknown')),
      );
      tr.append(st);
      tb.append(tr);
    });
    t.append(th, tb);
    const tw = mk('div', undefined, 'table-wrap');
    tw.append(t);
    b1.append(tw);
    root.append(b1);
    const better = F.forecast_errors.filter(r => r.model < r.baseline).length;
    const b3 = block('Booking forecast error', {
      note: `Closer than a simple average in ${better} of the last ${F.forecast_errors.length} weeks. Lower is better.`,
    });
    b3.append(
      legend([
        ['Model', C.blue],
        ['Simple average', C.amber],
      ]),
    );
    const h3 = mk('div', undefined, 'chart-host');
    b3.append(h3);
    root.append(b3);
    // Sales and collection trends are descriptive, so they live in the business dashboard.
    const b4 = block('Sales and collection trends', {
      more: ['Open the business dashboard', '#dashboard'],
      note: 'Monthly sales, contract collection and other descriptive charts are in the business dashboard, where they can be filtered by date and area.',
    });
    root.append(b4);
    later(() => {
      columns(h3, {
        labels: F.forecast_errors.map(r => r.origin),
        series: [
          { label: 'Model', values: F.forecast_errors.map(r => r.model), color: C.blue },
          { label: 'Simple average', values: F.forecast_errors.map(r => r.baseline), color: C.amber },
        ],
        xLabel: day,
        tipTitle: l => 'Week of ' + day(l),
      });
    });
  }
  function legend(items) {
    const d = mk('div', undefined, 'clegend');
    items.forEach(([l, c, dashed]) => {
      const it = mk('span');
      const sw = mk('i', undefined, dashed ? 'dashed' : '');
      sw.style.setProperty('--sw', c);
      it.append(sw, document.createTextNode(l));
      d.append(it);
    });
    return d;
  }

  /* =========================== Warranty-risk research =========================== */
  function renderRisk(root) {
    const W = data.warranty_risk || {};
    root.replaceChildren();
    if (!W.properties) {
      root.append(mk('p', 'The warranty-risk model is not available for this release.', 'block-empty'));
      return;
    }
    const ev = W.evaluation;
    root.append(
      hero(
        'Warranty-risk research',
        `As of ${day(W.as_of)}, ${nf.format(W.open_windows)} mapped locations had a recorded Calendar visit in the preceding 30 days and no warranty visit since. These are experimental historical scores, not verified warranty eligibility or instructions to contact a customer.`,
        [
          {
            label: 'Open service windows',
            value: nf.format(W.open_windows),
            note: 'recorded visits, last 30 days',
          },
          {
            label: 'Model estimate',
            value: nf.format(W.expected_calls),
            note: 'experimental, remaining windows',
          },
          {
            label: 'High risk',
            value: nf.format(W.high_risk),
            note: '20% chance or more',
            mark: ring(
              W.high_risk / Math.max(1, W.open_windows),
              pct(W.high_risk / Math.max(1, W.open_windows)),
            ),
          },
          { label: 'Records up to', value: day(W.as_of), note: 'Calendar' },
        ],
      ),
    );
    const b = block('Experimental location scores', {
      cls: 'block-research',
      note: 'Research view. Not a contact list.',
    });
    const t = mk('table', undefined, 'table');
    const th = mk('thead');
    const hr = mk('tr');
    [
      ['Property'],
      ['Area'],
      ['Serviced'],
      ['Window ends'],
      ['Earlier visits', 'num'],
      ['Chance', 'num'],
    ].forEach(([x, c]) => hr.append(mk('th', x, c)));
    th.append(hr);
    const tb = mk('tbody');
    W.properties.forEach(r => {
      const tr = mk('tr');
      const nm = mk('td', undefined, 'strong');
      const idc = mk('span', undefined, 'cell-id');
      idc.append(mk('span', initials(r.property), 'avatar sm'), mk('span', title(r.property)));
      nm.append(idc);
      tr.append(
        nm,
        mk(
          'td',
          r.district === 'Unassigned' ? 'Not recorded' : r.district,
          r.district === 'Unassigned' ? 'muted' : '',
        ),
        mk('td', day(r.last_service)),
      );
      const we = mk('td');
      we.append(mk('span', day(addDays(r.last_service, 30)), 'chip'));
      tr.append(we);
      tr.append(
        mk(
          'td',
          r.prior_warranty ? `${r.prior_visits} (${r.prior_warranty} warranty)` : String(r.prior_visits),
          'num',
        ),
      );
      const td = mk('td', undefined, 'num');
      const w = mk('span', undefined, 'chance');
      w.append(bar(r.risk / 0.5), mk('b', pct(r.risk)));
      td.append(w);
      tr.append(td);
      tb.append(tr);
    });
    t.append(th, tb);
    const tw = mk('div', undefined, 'table-wrap');
    tw.append(t);
    b.append(tw);
    root.append(b);
    const d = mk('details', undefined, 'explain');
    d.append(mk('summary', 'How reliable is this list?'));
    const dl = mk('dl', undefined, 'facts');
    [
      [
        pct(ev.top20_recall),
        'of warranty calls in the test months came from the 20% of visits the model ranked highest.',
      ],
      [ev.top20_lift.toFixed(1) + ' times', 'the usual warranty rate among those visits.'],
      [
        `${nf.format(ev.expected_vs_actual_calls[0])} expected, ${nf.format(ev.expected_vs_actual_calls[1])} recorded`,
        'recorded return labels in the historical assessment. Matching totals alone does not prove calibration.',
      ],
    ].forEach(([a, b2]) => {
      dl.append(mk('dt', a), mk('dd', b2));
    });
    d.append(
      dl,
      mk(
        'p',
        `Historically assessed on ${nf.format(ev.test_visits)} Calendar visit anchors between ${day(ev.test_period.split(' to ')[0])} and ${day(ev.test_period.split(' to ')[1])} 2026 that were not used to build it. It only looks at each property's own visit history. Three in four flagged properties will not call back. Independent review found location matching and timing limitations. The saved 2 November record does not establish a valid prospective test; it must not be reported as one.`,
        'block-note',
      ),
    );
    root.append(d);
  }

  /* =========================== Return-visit risk =========================== */
  const FACTORS = [
    ['final_residential', 'Final service of a residential programme'],
    ['residential', 'Residential customer'],
    ['three_service_programme', '3-service programme'],
    ['property_claims_90d', 'Each return at this address in the last 90 days'],
    ['programme_past_claims', 'Each earlier return in the same programme'],
    ['final_service', 'Final service of any programme'],
    ['cockroach_only', 'Cockroach-only treatment'],
    ['log_sale_rm', 'Higher package price (per step up)'],
    ['includes_rodent', 'Programme includes rodents'],
    ['gap_missing', 'No earlier service recorded'],
    ['first_service', 'First service of a programme'],
  ];
  function renderReturns(root) {
    root.replaceChildren();
    const pl = block("Service check-in plan", {
      note: 'All eligible services are shown by default. Use the score as context while staff continue their normal customer follow-up.',
    });
    const ctl = mk('div', undefined, 'plan-ctl');
    const lab = mk('label', undefined, 'plan-calls');
    lab.append(mk('span', 'Show services'));
    const inp = mk('select');
    [
      ['all', 'All eligible services'],
      ['10', 'First 10 by score'],
      ['20', 'First 20 by score'],
      ['40', 'First 40 by score'],
      ['60', 'First 60 by score'],
    ].forEach(([v, t]) => inp.append(new Option(t, v)));
    inp.value = String(rcalls);
    lab.append(inp);
    ctl.append(lab);
    const stats = mk('div', undefined, 'plan-stats');
    ctl.append(stats);
    pl.append(ctl);
    const note = mk('p', '', 'block-note');
    const listHost = mk('div');
    const logHost = mk('div', undefined, 'checkin-log');
    pl.append(note, listHost, logHost);
    root.append(pl);
    const paint = p => {
      stats.replaceChildren();
      if (p && p.status === 'live') {
        [
          [nf.format(p.check_ins.length), 'services ready to review'],
          [nf.format((p.done || []).length), 'contacts already completed'],
        ].forEach(([v, l]) => {
          const d = mk('div');
          d.append(mk('strong', v), mk('span', l));
          stats.append(d);
        });
      }
      note.textContent = planNote(p);
      listHost.replaceChildren(
        p && p.status === 'live'
          ? checkInManage(p, async () => {
              try {
                paint(await loadPlan(rcalls));
              } catch (e) {}
            })
          : mk('p', '', 'block-empty'),
      );
      logHost.replaceChildren();
      if (p && p.status === 'live') {
        logHost.append(mk('h3', 'Check-in log', 'sub-head'), outcomeStats(p.outcomes));
        if (!p.log_available)
          logHost.append(
            mk('p', 'Progress storage is unavailable, so results cannot be saved right now.', 'side-text'),
          );
      }
    };
    paint(rplan);
    let t;
    inp.addEventListener('change', () => {
      clearTimeout(t);
      t = setTimeout(async () => {
        try {
          paint(await loadPlan(inp.value));
        } catch (e) {
          note.textContent = e.message;
        }
      }, 250);
    });
  }

  function renderRankingDetails(root, R) {
    const E = R.evaluation;
    const cmp = E.compare;
    const rule = cmp['Rule: final residential service'];
    const rnd = cmp['Random order'];
    const b1 = block('How many returns each approach finds', {
      note: `Tested on ${nf.format(E.services)} services from ${E.period} (${E.returns} recorded returns). This assesses ranking, not a requirement to contact only some clients. Read across: if staff check this share of services, this share of returns is caught.`,
    });
    b1.append(
      legend([
        ['Return-risk score', C.blue],
        ['Rule: final residential service', C.amber, true],
        ['Random order', C.grey],
      ]),
    );
    const h1 = mk('div', undefined, 'chart-host');
    b1.append(h1);
    root.append(b1);
    const two = mk('div', undefined, 'cols');
    root.append(two);
    const b2 = block('What raises or lowers the risk', {
      note: 'How much each factor multiplies the odds of a return, other things equal',
    });
    const fl = mk('ul', undefined, 'factors');
    const u = R.per_unit_log_odds || {};
    FACTORS.filter(([k]) => u[k] != null)
      .map(([k, l]) => [l, Math.exp(u[k])])
      .sort((a, b) => b[1] - a[1])
      .forEach(([l, x]) => {
        const li = mk('li', undefined, x >= 1 ? 'up' : 'down');
        li.append(mk('span', l), mk('b', (x >= 1 ? '×' : '×') + x.toFixed(1)));
        fl.append(li);
      });
    b2.append(fl);
    two.append(b2);
    const exp = E.monthly.reduce((a, r) => a + r.expected, 0),
      act = E.monthly.reduce((a, r) => a + r.actual, 0);
    const b4 = block('Expected and actual returns by month of service', {
      note: `The score expected ${nf.format(exp)} returns and ${nf.format(act)} were recorded, so it runs about ${pct(1 - exp / act)} low. Future calibration and any operational benefit still need verification.`,
    });
    b4.append(
      legend([
        ['Expected by the score', C.blue],
        ['Recorded', C.teal],
      ]),
    );
    const h4 = mk('div', undefined, 'chart-host');
    b4.append(h4);
    root.append(b4);
    const d = mk('details', undefined, 'explain');
    d.append(mk('summary', 'How it was built and tested'));
    const dl = mk('dl', undefined, 'facts');
    [
      [
        'Data',
        `${nf.format(R.model.fit_rows)} sale-linked paid services from March 2024 to March 2026 (${R.model.fit_positives} returns). The label is a recorded corrective Calendar visit for the same sale within 30 days.`,
      ],
      [
        'Model',
        `Logistic regression on ${R.model.features.length} inputs known before the visit: programme position, premise, package price, earlier returns, gap since the last service and pest group. Weather and area inputs were tried and did not improve validation results.`,
      ],
      [
        'Choices',
        `Inputs and settings were chosen on November 2025 to March 2026 only. The final model was frozen before the test months were scored, with 30-day gaps and no sale appearing in two partitions.`,
      ],
      [
        'Compared with',
        `A random forest on all 90+ inputs: ranking score ${cmp['Complex model (random forest, all inputs)'].auc.toFixed(2)}. The simple rule: ${rule.auc.toFixed(2)}. Random order: ${rnd.auc.toFixed(2)}.`,
      ],
      [
        'Limits',
        'A recorded return visit is not proof the pests came back. Some of the test months were looked at in earlier studies of other models. The score ranks risk; whether early check-ins reduce returns still needs a trial.',
      ],
    ].forEach(([a, b]) => dl.append(mk('dt', a), mk('dd', b)));
    d.append(dl);
    root.append(d);
    later(() => {
      const cc = E.capture_curve;
      const lab = cc.review_share_pct.map(v => v + '%');
      lineChart(h1, {
        labels: lab,
        series: [
          {
            label: 'Return-risk score',
            values: cc['Return-risk score (chosen)'].map(v => v * 100),
            color: C.blue,
            area: true,
          },
          {
            label: 'Rule',
            values: cc['Rule: final residential service'].map(v => v * 100),
            color: C.amber,
            dashed: true,
          },
          {
            label: 'Random order',
            values: cc['Random order'].map(v => v * 100),
            color: C.grey,
            dashed: true,
          },
        ],
        format: v => Math.round(v) + '%',
        tipTitle: l => 'Checking ' + l + ' of services',
        height: 260,
        max: 100,
      });
      const ms = E.monthly.filter(r => r.services > 50);
      columns(h4, {
        labels: ms.map(r => r.m),
        series: [
          { label: 'Expected', values: ms.map(r => r.expected), color: C.blue },
          { label: 'Recorded', values: ms.map(r => r.actual), color: C.teal },
        ],
        xLabel: month,
        tipTitle: monthYear,
        format: v => nf.format(v),
      });
    });
  }

  /* =========================== loader =========================== */

  /* =========================== prediction models (management view) =========================== */
  // Horizontal bars comparing a model with simpler alternatives. rows: [label, value 0..1 or number, colour, text]
  function compareBars(rows, max) {
    const ul = mk('ul', undefined, 'cmp');
    const top = max || Math.max(...rows.map(r => r[1]), 1e-9);
    rows.forEach(([label, value, colour, text]) => {
      const li = mk('li');
      const track = mk('span', undefined, 'cmp-track');
      const fill = mk('i');
      fill.style.setProperty('--w', Math.max(2, Math.min(100, (value / top) * 100)).toFixed(1) + '%');
      fill.style.setProperty('--c', colour);
      track.append(fill);
      li.append(mk('span', label, 'cmp-label'), track, mk('b', text, 'cmp-value'));
      ul.append(li);
    });
    return ul;
  }
  function performancePanel(label, description) {
    const details = mk('details', undefined, 'model-evidence performance-panel');
    details.append(mk('summary', label), mk('p', description));
    return details;
  }

  function performanceFigure(name, caption, alt) {
    const figure = mk('figure', undefined, 'performance-figure');
    const img = mk('img');
    img.src = '/model-' + name + '.png';
    img.alt = alt;
    img.loading = 'lazy';
    figure.append(mk('figcaption', caption), img);
    return figure;
  }

  function performanceTable(headers, rows) {
    const wrapper = mk('div', undefined, 'table-wrap performance-table');
    wrapper.tabIndex = 0;
    wrapper.setAttribute('role', 'region');
    wrapper.setAttribute('aria-label', 'Model performance table');
    const table = mk('table'), head = table.createTHead().insertRow(), body = table.createTBody();
    headers.forEach(label => {
      const cell = mk('th', label);
      cell.scope = 'col';
      head.append(cell);
    });
    rows.forEach(values => {
      const row = body.insertRow();
      values.forEach(value => row.append(mk('td', value)));
    });
    wrapper.append(table);
    return wrapper;
  }

  function returnPerformance(evaluation) {
    const panel = performancePanel('Historical ranking comparison', 'ROC AUC compares ranking quality on the same services.');
    if (evaluation?.compare) {
      const methods = Object.entries(evaluation.compare).filter(([, result]) => Number.isFinite(result.auc));
      panel.append(mk('p', nf.format(evaluation.services) + ' services · ' + nf.format(evaluation.returns) + ' recorded returns'));
      panel.append(compareBars(methods.map(([name, result], index) => [
        name, result.auc, [C.blue, C.amber, C.grey][index % 3], result.auc.toFixed(2),
      ]), 1));
      panel.append(performanceTable(['Method', 'ROC AUC', 'Average precision', 'Returns in top 20%'],
        methods.map(([name, result]) => [
          name, result.auc.toFixed(2), Number.isFinite(result.ap) ? result.ap.toFixed(3) : '—',
          Number.isFinite(result.capture_20) ? pct(result.capture_20) : '—',
        ])));
    }
    return panel;
  }

  function forecastPerformance(forecast, image, unit) {
    const panel = performancePanel('Historical forecast comparison', 'Recorded outcomes, selected forecast and simple-average baseline.');
    panel.append(performanceFigure(image, 'Forecast versus recorded outcomes',
      'Historical ' + unit + ' by forecast date for the model, baseline and recorded outcomes.'));
    panel.append(performanceTable(['Method', 'Mean absolute error'], [
      ['Selected forecast', Number(forecast.mae).toFixed(2) + ' ' + unit],
      ['Simple average', Number(forecast.baseline_mae).toFixed(2) + ' ' + unit],
    ]));
    return panel;
  }

  function originalModelPerformance() {
    const panel = performancePanel('Original ExtraTrees holdout charts', 'Historical assessment on 100 services with five recorded returns. The classification threshold was 19%.');
    const figures = mk('div', undefined, 'performance-grid');
    figures.append(
      performanceFigure('roc', 'ROC curve · AUC 0.891', 'True positive rate versus false positive rate across score thresholds.'),
      performanceFigure('precision-recall', 'Precision–recall curve · AP 0.305', 'Precision versus recall across score thresholds, with a 5% prevalence baseline.'),
      performanceFigure('threshold', 'Classification metrics at the saved threshold', 'Accuracy 94%, precision 40%, recall 40%, F1 40%. Always predicting no return gives 95% accuracy.'),
      performanceFigure('input-removal', 'Input-removal study · development folds', 'The eight largest changes in average precision after removing one input. Positive values mean the score improved after removal. These are validation effects.'),
    );
    panel.append(figures, performanceTable(['Measure', 'Result'], [
      ['Accuracy', '94%'], ['Always predict no return', '95% accuracy'],
      ['Precision / recall / F1', '40% / 40% / 40%'],
      ['True / false positives', '2 / 3'], ['True / false negatives', '92 / 3'],
    ]));
    return panel;
  }

  const MODEL_OPTIONS = [
    ['ranking', '30-day return risk — Logistic regression', 'Used in service follow-up'],
    ['booking_entries_h2', 'Two-week bookings — Extra Trees', 'Planning forecast'],
    ['booked_hours_h1', 'Next-week appointment hours — Ridge regression', 'Planning forecast'],
    ['frozen', '30-day return classification — Extra Trees', 'Frozen experiment'],
    ['return60', '60-day residential return — Logistic regression', 'Earlier research'],
    ['repeat90', '90-day repeat purchase — Ranking model', 'Earlier research'],
  ];
  let selectedModel = MODEL_OPTIONS[0][0];

  function renderModels(root) {
    root.replaceChildren();
    const header = block('Model performance');
    const label = mk('label', undefined, 'model-selector');
    label.append(mk('span', 'Choose a model'));
    const select = mk('select');
    MODEL_OPTIONS.forEach(([id, name]) => select.append(new Option(name, id)));
    select.value = selectedModel;
    label.append(select);
    header.append(label);
    const evidence = mk('div');
    root.append(header, evidence);

    const show = () => {
      selectedModel = select.value;
      g('model-area-evidence').hidden = selectedModel !== 'frozen';
      const [id, name, status] = MODEL_OPTIONS.find(([key]) => key === selectedModel);
      const card = block(name);
      card.append(mk('p', status, 'block-note'));
      evidence.replaceChildren(card);
      const R = data.return_risk || {};
      let panel;
      if (id === 'ranking' && R.evaluation) {
        panel = returnPerformance(R.evaluation);
        card.append(panel);
        renderRankingDetails(evidence, R);
      } else if (id === 'frozen') {
        panel = originalModelPerformance();
        card.append(panel);
      } else if (id === 'return60' || id === 'repeat90') {
        const research = mk('div');
        card.append(research);
        window.renderResearchModel(research, id);
      } else {
        const forecast = (data.predictive?.forecasts || []).find(f => f.id === id);
        if (forecast) {
          const booking = id === 'booking_entries_h2';
          panel = forecastPerformance(forecast, booking ? 'booking' : 'hours', booking ? 'bookings' : 'hours');
          card.append(panel);
        } else {
          card.append(mk('p', 'Assessment unavailable for this release.'));
        }
      }
      if (panel) panel.open = true;
    };
    select.addEventListener('change', show);
    show();
  }

  /* =========================== Management overview =========================== */
  // One page for the owner: where the business stands, what to do this week and why,
  // then the areas and packages behind it. Every action links to its detail.
  const RENDER = {
    today: renderToday,
    performance: renderPerformance,
    risk: renderRisk,
    returns: renderReturns,
    models: renderModels,
  };
  function draw(route) {
    const root = g('view-' + route);
    if (!root || !data) return;
    try {
      RENDER[route](root);
    } catch (e) {
      console.error(e);
      root.replaceChildren(mk('p', 'This page could not be drawn from the current data.', 'block-empty'));
    }
  }
  async function getJSON(url) {
    const r = await fetch(url);
    const v = await r.json();
    if (r.status === 401 && typeof load === 'function') load();
    if (!r.ok) throw new Error(v.error || 'Unavailable');
    return v;
  }
  window.loadStage = async function (route) {
    if (!RENDER[route]) return;
    current = route;
    if (data && (route !== 'today' || work)) {
      draw(route);
      return;
    }
    if (loading) return loading;
    const waiting = g('view-' + route);
    if (waiting && !waiting.childElementCount) waiting.replaceChildren(mk('p', 'Loading the latest records…', 'block-empty'));
    loading = (async () => {
      try {
        const [a, w] = await Promise.all([
          data ? data : getJSON('/api/analytics'),
          getJSON('/api/workspace').catch(() => null),
          rplan ? rplan : loadPlan(rcalls).catch(() => null),
        ]);
        data = a;
        work = w;
        draw(current);
      } catch (e) {
        const root = g('view-' + current);
        const box = mk('div', undefined, 'block-empty');
        box.append(mk('p', 'The figures could not be loaded: ' + e.message));
        const b = mk('button', 'Try again', 'btn btn-ghost btn-sm');
        b.type = 'button';
        b.addEventListener('click', () => {
          loading = null;
          window.loadStage(current);
        });
        box.append(b);
        root.replaceChildren(box);
      } finally {
        loading = null;
      }
    })();
    return loading;
  };
  let rt;
  window.addEventListener('resize', () => {
    clearTimeout(rt);
    rt = setTimeout(() => {
      if (data && (current === 'performance' || current === 'returns') && !g('view-' + current).hidden)
        draw(current);
    }, 200);
  });
})();
