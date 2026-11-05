'use strict';
// Readable page addresses. Internal view names stay as they were, so older links
// (#home, #today, #returns, #plan) keep working.
window.CP2_ALIAS = { workspace: 'today', 'follow-up': 'returns', reminders: 'home', bookings: 'plan' };
window.cp2Page = () => {
  const h = location.hash.slice(1);
  return window.CP2_ALIAS[h] || h;
};
let state, boundaries;
const $ = id => document.getElementById(id);
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
const number = v =>
  v === null || v === undefined
    ? '-'
    : new Intl.NumberFormat('en-MY', { maximumFractionDigits: 0 }).format(v);
const money = v =>
  v === null || v === undefined
    ? '-'
    : new Intl.NumberFormat('en-MY', {
        style: 'currency',
        currency: 'MYR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(v);
const percent = v => (v === null || v === undefined ? '-' : (v * 100).toFixed(1) + '%');
let helpSequence = 0;
function help(label, message) {
  const wrap = el('span', undefined, 'help-wrap'),
    button = el('button', 'i', 'help'),
    tip = el('span', message, 'tooltip');
  tip.id = 'dynamic-help-' + ++helpSequence;
  tip.setAttribute('role', 'tooltip');
  button.type = 'button';
  button.setAttribute('aria-label', label);
  button.setAttribute('aria-describedby', tip.id);
  button.setAttribute('aria-expanded', 'false');
  wrap.append(button, tip);
  return wrap;
}
function statusMessage(label, detail) {
  const box = $('global-status');
  box.replaceChildren(el('span', label));
  if (detail) box.append(help('About data freshness', detail));
}
const date = v =>
  v
    ? new Date(v).toLocaleDateString('en-MY', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'Unknown';
function empty(target, message) {
  target.replaceChildren(el('p', message, 'empty'));
}
async function api(url, opts = {}) {
  const r = await fetch(url, opts);
  let value;
  try {
    value = await r.json();
  } catch {
    const e = new Error(
      r.status === 429
        ? 'The workspace is busy. Please try again shortly.'
        : r.status === 401 || r.status === 403
          ? 'Your session has expired. Reload and sign in again.'
          : 'This tool is temporarily unavailable. Please try again.',
    );
    e.status = r.status;
    throw e;
  }
  if (!r.ok) {
    const e = new Error(value.error || 'Request failed');
    e.status = r.status;
    throw e;
  }
  return value;
}
function jsonPost(url, body) {
  return api(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
function kpis(target, values) {
  $(target).replaceChildren(
    ...values.map(([label, value, sub]) => {
      const n = el('article', undefined, 'kpi');
      n.append(el('small', label), el('strong', value));
      if (sub) n.append(el('div', sub, 'sub'));
      return n;
    }),
  );
}
function lines(target, values) {
  $(target).replaceChildren(
    ...values.map(([name, value, detail]) => {
      const n = el('div', undefined, 'metric-line'),
        label = el('span', name);
      if (detail) label.append(help('About ' + name, detail));
      n.append(label, el('strong', value));
      return n;
    }),
  );
}
function table(target, rows, columns) {
  const box = $(target);
  if (!rows?.length) return empty(box, 'No records available for this view.');
  const t = el('table'),
    head = el('thead'),
    hr = el('tr'),
    body = el('tbody');
  columns.forEach(c => hr.append(el('th', c[0])));
  head.append(hr);
  rows.forEach(row => {
    const tr = el('tr');
    columns.forEach(([label, key, format, numeric]) => {
      const value = row[key];
      tr.append(el('td', format ? format(value) : (value ?? '-'), numeric ? 'numeric' : ''));
    });
    body.append(tr);
  });
  t.append(head, body);
  box.replaceChildren(t);
}
function svgNode(tag, attrs = {}, text) {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, String(v)));
  if (text !== undefined) n.textContent = text;
  return n;
}
function showArea(d) {
  $('area-title').textContent = d.district || 'All evaluated services';
  if (d.status === 'insufficient_services' || !d.services) {
    empty(
      $('area-metrics'),
      `${number(d.services)} services. Too few evaluated services to show outcome metrics.`,
    );
    return;
  }
  const interval = d.accuracy_interval
    ? `Approximate 95% service-level interval: ${percent(d.accuracy_interval[0])}–${percent(d.accuracy_interval[1])}. Repeated customer visits may be correlated.`
    : '';
  lines('area-metrics', [
    ['Services evaluated', number(d.services)],
    [
      'Return visits',
      number(d.positive_cases),
      'Recorded corrective return visits within 30 days; not all are formal warranty claims.',
    ],
    ['Model accuracy', percent(d.accuracy), 'The original decision threshold remains fixed. ' + interval],
    [
      'Baseline accuracy',
      percent(d.always_no_return_accuracy),
      'Accuracy from predicting no return for every service in this same group.',
    ],
    ['False alerts / missed visits', `${number(d.false_alerts)} / ${number(d.missed_cases)}`],
    [
      'Return cases in review list',
      number(d.cases_found_in_global_top20),
      'Cases captured by the original global top-20 review list. This list is not reranked when selecting a district.',
    ],
  ]);
  if (d.positive_cases === 0)
    $('area-metrics').append(
      el('p', 'No return cases in this group. Detection performance cannot be measured.', 'notice'),
    );
}

function chooseDistrict(name) {
  $('district').value = name;
  const d = name === 'all' ? state.areas.overall : state.areas.districts.find(d => d.district === name);
  showArea(d || { services: 0 });
  document
    .querySelectorAll('.district-shape')
    .forEach(n => n.classList.toggle('chosen', n.dataset.district === name));
}
function drawMap() {
  if (!boundaries) return;
  const features = boundaries.features || [];
  const all = [];
  features.forEach(f => {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    polys.forEach(p => p.forEach(r => all.push(...r)));
  });
  if (!all.length) return;
  let minX = Math.min(...all.map(p => p[0])),
    maxX = Math.max(...all.map(p => p[0])),
    minY = Math.min(...all.map(p => p[1])),
    maxY = Math.max(...all.map(p => p[1]));
  const sx = 590 / (maxX - minX),
    sy = 280 / (maxY - minY),
    scale = Math.min(sx, sy),
    x = v => 20 + (v - minX) * scale,
    y = v => 290 - (v - minY) * scale;
  const svg = svgNode('svg', {
    viewBox: '0 0 640 310',
    role: 'img',
    'aria-label': 'District boundaries for locations represented in the historical evaluation',
  });
  features.forEach(f => {
    const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
    const path = svgNode('path', {
      d: polys
        .map(p => p.map(r => 'M' + r.map(v => `${x(v[0])},${y(v[1])}`).join('L') + 'Z').join(''))
        .join(''),
      class: 'district-shape',
      'fill-rule': 'evenodd',
      tabindex: 0,
    });
    const name = f.properties.state + ' / ' + f.properties.district;
    path.dataset.district = name;
    path.append(svgNode('title', {}, name));
    path.addEventListener('click', () => chooseDistrict(name));
    path.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        chooseDistrict(name);
      }
    });
    svg.append(path);
  });
  svg.append(svgNode('text', { x: 580, y: 25, fill: getComputedStyle(document.documentElement).getPropertyValue('--color-muted').trim(), 'font-size': 11 }, 'N ↑'));
  $('district-map').replaceChildren(svg);
}
function render() {
  const t = state.totals,
    s = state.snapshot,
    rows = s.tables || {};
  $('snapshot-date').textContent = s.fetched_at_utc
    ? 'Fetched ' + date(s.fetched_at_utc)
    : 'Data not connected';
  $('global-status').textContent =
    s.status === 'connected'
      ? ''
      : 'Business data is not connected yet. Model evidence and policy remain available.';
  $('dashboard-link').href = state.dashboard_url.replace('/embed/', '/');
  $('dashboard-frame').closest('.embed-panel').hidden = !state.dashboard_embed;
  $('dashboard-note').hidden = !!state.dashboard_embed;
  const opts = [el('option', 'All evaluated services')];
  opts[0].value = 'all';
  (state.areas.districts || []).forEach(d => {
    const o = el('option', d.district + ', ' + d.services + ' services');
    o.value = d.district;
    opts.push(o);
  });
  $('district').replaceChildren(...opts);
  chooseDistrict('all');
  const unassigned = state.areas.districts?.find(d => d.district === 'Unassigned')?.services ?? 0;
  const total = state.areas.overall?.services ?? 0;
  $('location-coverage').textContent =
    `${total - unassigned} of ${total} services reliably assigned to districts; ${unassigned} remain unassigned.`;
  table('district-table', state.areas.districts, [
    ['District', 'district'],
    ['Services', 'services', number, true],
    ['Return cases', 'positive_cases', number, true],
    ['Accuracy', 'accuracy', percent, true],
    ['Baseline', 'always_no_return_accuracy', percent, true],
    [
      'Evidence',
      'status',
      v => (v === 'insufficient_services' ? 'Too few services' : 'Small historical sample'),
    ],
  ]);
  kpis('system-cards', [
    ['Website', 'Running'],
    ['Business data', s.status === 'connected' ? 'Connected' : 'Not connected'],
    ['Last data fetch', s.fetched_at_utc ? date(s.fetched_at_utc) : 'Unknown'],
  ]);
  const sourceDates = (rows.freshness || [])
    .filter(r => ['sales', 'calendar', 'recurring_payments'].includes(r.source_name))
    .map(r => (r.extracted_at_utc ? Date.parse(r.extracted_at_utc) : NaN));
  if (sourceDates.length === 3 && sourceDates.every(Number.isFinite)) {
    const oldest = Math.min(...sourceDates);
    $('snapshot-date').textContent = 'Source snapshot ' + date(oldest);
    if (Date.now() - oldest > 36 * 3600000)
      statusMessage(
        'Business reporting needs refreshing.',
        'Source snapshot: ' +
          date(oldest) +
          '. Figures reflect the last published release and are older than 36 hours. Verify current source records before acting.',
      );
  } else if (s.status === 'connected') {
    $('global-status').textContent =
      'Source freshness is incomplete. Verify the original records before acting.';
  }
  if (state.system.last_refresh_error)
    $('global-status').textContent =
      'The last refresh failed. The previous successful snapshot is retained; check source freshness.';
}
function navigate() {
  const pages = [
    'overview',
    'today',
    'returns',
    'models',
    'performance',
    'risk',
    'home',
    'plan',
    'dashboard',
    'customers',
    'payments',
    'business',
    'areas',
    'status',
  ];
  let page = window.cp2Page() || 'overview';
  if (!pages.includes(page)) page = 'overview';
  document.querySelectorAll('[data-view]').forEach(n => (n.hidden = n.dataset.view !== page));
  document
    .querySelectorAll('[data-page]')
    .forEach(n => n.classList.toggle('active', n.dataset.page === page));
  $('breadcrumb').textContent =
    'Nomobug / ' +
    {
      overview: 'Management overview',
      today: 'Workspace',
      returns: 'Service follow-up',
      models: 'Prediction models',
      risk: 'Warranty risk',
      performance: 'Performance',
      home: 'Follow-up queue',
      plan: 'Plan',
      dashboard: 'Dashboard',
      areas: 'Model test by area',
      business: 'Area explorer',
      customers: 'Customers & areas',
      payments: 'Payment follow-up',
      status: 'Technical evidence',
    }[page];
  if (page === 'business' && state && !businessLoaded) loadBusiness();
  if (window.onRoute) window.onRoute(page, !!state);
  if (state && window.loadWorkspaceTools) window.loadWorkspaceTools(page);
  if (page === 'dashboard' && state && state.dashboard_embed && !$('dashboard-frame').src)
    $('dashboard-frame').src = state.dashboard_url;
}
async function load() {
  try {
    state = await api('/api/state');
    $('login').hidden = true;
    $('workspace').hidden = false;
    $('logout').textContent = state.system?.auth_mode === 'iap' ? 'Switch Google account' : 'Sign out';
    render();
    navigate();
    try {
      boundaries = await api('/api/area/boundaries');
      drawMap();
      populatePlaces();
    } catch (e) {
      empty($('district-map'), 'Prepare the district-boundary data to display this map.');
    }
  } catch (e) {
    if (e.status === 401) {
      $('login').hidden = false;
      $('workspace').hidden = true;
    } else $('global-status').textContent = e.message;
  }
}
$('district').addEventListener('change', e => chooseDistrict(e.target.value));
$('radius-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (!e.target.elements.lat.value) {
    $('radius-result').textContent = 'Area list is still loading. Please try again.';
    return;
  }
  const query = new URLSearchParams(new FormData(e.target));
  query.delete('place');
  $('radius-result').textContent = 'Evaluating the saved historical sample…';
  try {
    const r = await api('/api/area/radius?' + query);
    $('radius-result').replaceChildren(
      el(
        'p',
        `${r.services} services in this area; ${r.ambiguous_boundary_services ?? 0} uncertain boundary matches excluded.`,
      ),
    );
    if (r.status === 'insufficient_services') $('radius-result').append(el('p', r.note, 'notice'));
    else
      $('radius-result').append(
        el(
          'p',
          `Accuracy ${percent(r.accuracy)}, baseline ${percent(r.always_no_return_accuracy)}, ${r.positive_cases} return cases, ${r.false_alerts} false alerts, ${r.missed_cases} missed. ${r.positive_cases === 0 ? 'No return cases: detection performance cannot be measured.' : 'Small historical sample; exploratory.'}`,
          'notice',
        ),
      );
  } catch (err) {
    $('radius-result').textContent = err.message;
  }
});
$('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    await jsonPost('/api/login', { username: $('login-username').value, password: $('access-code').value });
    $('access-code').value = '';
    $('login-message').textContent = '';
    await load();
  } catch (err) {
    $('login-message').textContent = err.message;
  }
});
$('logout').addEventListener('click', async () => {
  await jsonPost('/api/logout', {});
  if (state?.system?.auth_mode === 'iap') location.assign('/?gcp-iap-mode=CLEAR_LOGIN_COOKIE');
  else location.reload();
});
window.addEventListener('hashchange', navigate);
navigate();
load();

function closeHelp(except) {
  document.querySelectorAll('.help-wrap').forEach(w => {
    if (w !== except) {
      w.classList.remove('open');
      w.querySelector('.help').setAttribute('aria-expanded', 'false');
    }
  });
}
document.addEventListener('click', e => {
  const button = e.target.closest('.help');
  if (!button) {
    if (!e.target.closest('.help-wrap')) closeHelp();
    return;
  }
  const wrap = button.closest('.help-wrap'),
    opening = !wrap.classList.contains('open');
  closeHelp(wrap);
  wrap.classList.remove('dismissed');
  wrap.classList.toggle('open', opening);
  button.setAttribute('aria-expanded', String(opening));
  if (!opening) wrap.classList.add('dismissed');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    closeHelp();
    document.querySelectorAll('.help-wrap').forEach(w => w.classList.add('dismissed'));
  }
});
document.addEventListener('focusin', e => {
  if (e.target.matches('.help')) e.target.closest('.help-wrap').classList.remove('dismissed');
});
document.addEventListener('pointerover', e => {
  const wrap = e.target.closest('.help-wrap');
  if (wrap && !wrap.contains(e.relatedTarget)) wrap.classList.remove('dismissed');
});

let businessLoaded = false;
async function loadBusiness() {
  const form = $('business-filter');
  if (!form.elements.end.value)
    form.elements.end.value = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kuala_Lumpur' });
  try {
    const r = await api('/api/business?' + new URLSearchParams(new FormData(form)));
    businessLoaded = true;
    $('business-release').textContent = 'Source release ' + r.receipt.published_release.replace('cp2r_', '');
    const sales = r.districts.reduce((a, d) => a + d.sales_rm, 0),
      purchases = r.districts.reduce((a, d) => a + d.sale_rows, 0),
      visits = r.districts.reduce((a, d) => a + d.appointments, 0);
    kpis('business-kpis', [
      ['Sales', money(sales)],
      ['Purchases', number(purchases)],
      ['Appointments', number(visits)],
    ]);
    table('business-areas', r.districts, [
      ['District', 'district'],
      ['Sales', 'sales_rm', money, true],
      ['Purchases', 'sale_rows', number, true],
      ['Appointments', 'appointments', number, true],
    ]);
    const top = r.districts.filter(d => d.district !== 'Unassigned').slice(0, 8),
      max = Math.max(...top.map(d => d.sales_rm), 1);
    $('business-bars').replaceChildren(
      ...top.map(d => {
        const row = el('div', undefined, 'business-bar');
        row.append(el('span', d.district), el('strong', money(d.sales_rm)));
        const track = el('div', undefined, 'bar-track'),
          fill = el('div', undefined, 'bar-fill');
        fill.style.width = (d.sales_rm / max) * 100 + '%';
        track.append(fill);
        row.append(track);
        return row;
      }),
    );
    const unknown = r.districts.find(d => d.district === 'Unassigned');
    $('business-coverage').textContent =
      `${number(unknown?.sale_rows || 0)} purchases and ${number(unknown?.appointments || 0)} appointments have no reliable district. ${number(r.unknown_date_sales)} purchases have no usable date and are excluded from date filters. Sales are package prices; appointments are bookings.`;
    $('business-radius').requestSubmit();
  } catch (e) {
    $('business-coverage').textContent = e.message;
  }
}
async function loadCustomers() {
  try {
    const r = await jsonPost('/api/customers', Object.fromEntries(new FormData($('customer-search'))));
    $('customer-summary').textContent =
      `Showing the first ${Math.min(50, r.matching_groups)} of ${number(r.matching_groups)} customer groups. Exact customer matching; unresolved identities remain separate.`;
    // Summary row: one tile per figure, describing every matching customer group.
    const sm = r.summary || {};
    $('customer-stats').replaceChildren(
      ...[
        [number(sm.groups), 'customer groups'],
        [money(sm.sales_rm), 'recorded sales'],
        [number(sm.repeat), 'repeat customers'],
        [number(sm.needs_review), 'need an identity check'],
      ].map(([v, l]) => {
        const t = el('div', undefined, 'customer-stat');
        t.append(el('strong', v), el('span', l));
        return t;
      }),
    );
    $('customer-results').replaceChildren(
      ...r.customers.map(c => {
        const d = el('details', undefined, 'customer-row'),
          summary = el('summary');
        summary.append(
          el('strong', c.name),
          el('span', money(c.sales_rm)),
          el('span', c.purchase_count + (c.purchase_count === 1 ? ' programme' : ' programmes')),
          el(
            'span',
            c.repeat_customer
              ? 'Repeat customer'
              : c.identity_status === 'needs_review'
                ? 'Identity needs review'
                : 'Single programme',
          ),
        );
        d.append(summary);
        const programmeLabels = new Map();
        c.sales.forEach(s => {
          if (s.programme_id && !programmeLabels.has(s.programme_id))
            programmeLabels.set(s.programme_id, 'Programme ' + (programmeLabels.size + 1));
        });
        const t = el('table');
        const h = el('tr');
        ['Sale', 'Date', 'Programme', 'Sales'].forEach(x => h.append(el('th', x)));
        t.append(h);
        c.sales.forEach(s => {
          const row = el('tr');
          [
            s.sale_id,
            s.date || 'Unknown',
            programmeLabels.get(s.programme_id) || 'Unlinked',
            money(s.sales_rm),
          ].forEach(x => row.append(el('td', x)));
          t.append(row);
        });
        d.append(t);
        if (c.appointment_count !== undefined)
          d.append(el('p', number(c.appointment_count) + ' linked appointments', 'sub'));
        for (const contract of c.contracts || []) {
          const line = el(
            'p',
            `Contract ${contract.sales_record_id}, Recorded paid ${money(contract.sales_total_recorded_paid_rm)}, Remaining ${money(contract.sales_remaining_balance_rm)}, Next reminder ${contract.next_scheduled_reminder_date || 'No source date'}`,
          );
          d.append(line, el('p', paymentAction(contract.next_action), 'sub'));
        }
        return d;
      }),
    );
    const customerHeading = el('div', undefined, 'customer-list-head');
    ['Customer', 'Sales', 'Programmes', 'Relationship'].forEach(label =>
      customerHeading.append(el('span', label)),
    );
    $('customer-results').prepend(customerHeading);
  } catch (e) {
    $('customer-summary').textContent = e.message;
  }
}
$('business-filter').addEventListener('submit', e => {
  e.preventDefault();
  loadBusiness();
});
// Changing a filter or the order updates the list straight away.
$('customer-search')
  .querySelectorAll('select')
  .forEach(sel => sel.addEventListener('change', () => $('customer-search').requestSubmit()));
$('customer-search').addEventListener('submit', e => {
  e.preventDefault();
  loadCustomers();
});

$('business-radius').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    if (!e.target.elements.lat.value) {
      $('business-radius-coverage').textContent = 'Area list is still loading. Please try again.';
      return;
    }
    const payload = {
      ...Object.fromEntries(new FormData(e.target)),
      ...Object.fromEntries(new FormData($('business-filter'))),
    };
    const r = await jsonPost('/api/business/radius', payload);
    kpis('business-radius-result', [
      ['Sales', money(r.sales_rm)],
      ['Purchases', number(r.sale_rows)],
      ['Appointments', number(r.appointments)],
    ]);
    $('business-radius-coverage').textContent =
      `${number(r.ambiguous_sales)} purchases and ${number(r.ambiguous_appointments)} appointments cross the radius uncertainty boundary and are excluded. ${number(r.unlocated_sales)} purchases and ${number(r.unlocated_appointments)} appointments lack reliable coordinates. ${number(r.unknown_sale_values)} included purchases have unknown sales amounts; sales sum known amounts. Uses the selected date range.`;
  } catch (err) {
    $('business-radius-coverage').textContent = err.message;
  }
});

function populatePlaces() {
  const places = (boundaries?.features || [])
    .map(f => {
      const points = [];
      const walk = a => {
        if (typeof a[0] === 'number') points.push(a);
        else a.forEach(walk);
      };
      walk(f.geometry.coordinates);
      if (!points.length) return null;
      const xs = points.map(p => p[0]),
        ys = points.map(p => p[1]);
      return {
        name: f.properties.state + ' / ' + f.properties.district,
        lat: (Math.min(...ys) + Math.max(...ys)) / 2,
        lon: (Math.min(...xs) + Math.max(...xs)) / 2,
      };
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
  document.querySelectorAll('.place-select').forEach(select => {
    select.replaceChildren(
      ...places.map(place => {
        const o = el('option', place.name);
        o.value = place.name;
        o.dataset.lat = place.lat;
        o.dataset.lon = place.lon;
        return o;
      }),
    );
    select.value = places.find(p => p.name === 'Selangor / Petaling')?.name || places[0]?.name || '';
    const sync = () => {
      const o = select.selectedOptions[0];
      if (!o) return;
      select.form.elements.lat.value = o.dataset.lat;
      select.form.elements.lon.value = o.dataset.lon;
    };
    select.addEventListener('change', sync);
    sync();
  });
  if (location.hash === '#business' && businessLoaded) $('business-radius').requestSubmit();
}
