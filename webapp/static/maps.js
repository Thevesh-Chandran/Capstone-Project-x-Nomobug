(async () => {
  const response = await fetch('/api/spatial', { credentials: 'same-origin' });
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? 'Sign in to the staff workspace to view maps.'
        : 'Map sources are temporarily unavailable.',
    );
  const DATA = await response.json();
  let layer = 'sales',
    zoom = 1,
    selected = null,
    centre = [101.65, 3.12],
    groups = [],
    rows = [],
    drag = null;
  const $ = id => document.getElementById(id),
    money = n => (n == null ? 'Unknown' : 'RM ' + Math.round(n).toLocaleString()),
    pct = n => (n * 100).toFixed(1) + '%',
    titles = {
      sales: 'Sales hotspots',
      visits: 'Recorded warranty visits',
      model: 'Historical model by area',
    };
  // Default to the full dated range in the loaded sales and visit snapshot.
  const dates = [...DATA.sales, ...DATA.visits].map(row => row.date)
    .filter(date => typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)).sort();
  $('from').value = dates[0] || '';
  $('to').value = dates.at(-1) || '';
  // Only the attribution the map data's licences require.
  document.querySelector('footer').textContent = 'Map data © OpenStreetMap contributors, locations by Geoapify';
  function safe(t) {
    return String(t ?? '').replace(
      /[&<>"']/g,
      c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
    );
  }
  function position(lon, lat) {
    return [450 + (lon - centre[0]) * 720 * zoom, 280 - (lat - centre[1]) * 720 * zoom];
  }
  // Fallback name from the public district boundaries when no record in the group carries a district.
  function inRing(lon, lat, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  function districtAt(lon, lat) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || !DATA.boundaries) return '';
    for (const f of DATA.boundaries.features) {
      const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
      if (polys.some(p => inRing(lon, lat, p[0]) && !p.slice(1).some(h => inRing(lon, lat, h)))) {
        const { state, district } = f.properties;
        return state === district || !state ? district : state + ' / ' + district;
      }
    }
    return '';
  }
  function groupLabel(g) {
    let counts = {};
    for (let r of g.rs) {
      let name = r.district;
      if (name && name !== 'Unassigned') counts[name] = (counts[name] || 0) + 1;
    }
    let label = Object.keys(counts).sort((a, b) => counts[b] - counts[a])[0];
    if (!label) label = districtAt(g.lon, g.lat);
    if (!label) return 'Outside mapped districts';
    let parts = label.split(' / ');
    return parts.length === 2 && parts[0] === parts[1] ? parts[0] : label;
  }
  function pathFor(coords) {
    return coords
      .map(
        r =>
          r
            .map((p, i) => {
              let q = position(p[0], p[1]);
              return (i ? 'L' : 'M') + q.join(',');
            })
            .join(' ') + ' Z',
      )
      .join(' ');
  }
  function stats(rs) {
    let n = rs.length,
      positive = rs.filter(r => Number(r.outcome) === 1).length,
      tp = 0,
      fp = 0,
      fn = 0,
      correct = 0;
    for (let r of rs) {
      let y = Number(r.outcome) === 1,
        p = Number(r.score) >= Number(r.threshold);
      if (p === y) correct++;
      if (p && y) tp++;
      if (p && !y) fp++;
      if (!p && y) fn++;
    }
    return {
      n,
      positive,
      tp,
      fp,
      fn,
      accuracy: n ? correct / n : 0,
      baseline: n ? (n - positive) / n : 0,
      supported: n >= 20 && positive >= 5,
    };
  }
  function currentRows() {
    if (layer === 'model')
      return DATA.model.filter(r => Number.isFinite(r.latitude) && Number.isFinite(r.longitude));
    return DATA[layer].filter(r => r.date && (!$('from').value || r.date >= $('from').value) && (!$('to').value || r.date <= $('to').value));
  }
  function groupRows() {
    let k = Number($('size').value),
      step = k / 111;
    const bins = new Map();
    for (let r of rows) {
      let lonStep = step / Math.cos((3.12 * Math.PI) / 180),
        gx = Math.floor(r.longitude / lonStep),
        gy = Math.floor(r.latitude / step),
        id = gx + ':' + gy;
      let edge = Math.min(
        (r.latitude - gy * step) * 111,
        ((gy + 1) * step - r.latitude) * 111,
        (r.longitude - gx * lonStep) * 111 * Math.cos((3.12 * Math.PI) / 180),
        ((gx + 1) * lonStep - r.longitude) * 111 * Math.cos((3.12 * Math.PI) / 180),
      );
      if (edge <= Number(r.uncertainty_km || 0) + 0.1) continue;
      if (!bins.has(id))
        bins.set(id, {
          id,
          rs: [],
          lon: ((gx + 0.5) * step) / Math.cos((3.12 * Math.PI) / 180),
          lat: (gy + 0.5) * step,
        });
      bins.get(id).rs.push(r);
    }
    return [...bins.values()].map(g => ({
      ...g,
      value:
        layer === 'sales'
          ? g.rs.reduce((s, r) => s + (typeof r.amount === 'number' ? r.amount : 0), 0)
          : g.rs.length,
      metrics: stats(g.rs),
    }));
  }
  function densityField() {
    const step = 15,
      cols = 60,
      grid = new Float64Array(cols * 38);
    for (const r of rows) {
      const [x, y] = position(r.longitude, r.latitude),
        radius = Math.max(12, (Math.max(1.5, Number(r.uncertainty_km || 0)) / 111) * 720 * zoom),
        weight = layer === 'sales' ? Math.max(0, Number(r.amount) || 0) : 1;
      if (!weight) continue;
      const left = Math.max(0, Math.floor((x - 3 * radius) / step)),
        right = Math.min(cols - 1, Math.ceil((x + 3 * radius) / step)),
        top = Math.max(0, Math.floor((y - 3 * radius) / step)),
        bottom = Math.min(37, Math.ceil((y + 3 * radius) / step));
      for (let iy = top; iy <= bottom; iy++)
        for (let ix = left; ix <= right; ix++) {
          const d = ((ix + 0.5) * step - x) ** 2 + ((iy + 0.5) * step - y) ** 2;
          grid[iy * cols + ix] += (weight * Math.exp(-d / (2 * radius * radius))) / (radius * radius);
        }
    }
    const max = Math.max(0, ...grid);
    if (!max) return '';
    const stops = [
      [55, 102, 188],
      [47, 170, 208],
      [114, 211, 180],
      [244, 220, 99],
      [239, 154, 70],
      [206, 64, 88],
    ];
    return Array.from(grid, (v, i) => {
      let ratio = v / max;
      if (ratio < 0.015) return '';
      let t = Math.sqrt(ratio),
        k = t * (stops.length - 1),
        a = Math.min(stops.length - 2, Math.floor(k)),
        f = k - a,
        c = stops[a].map((v, j) => Math.round(v + (stops[a + 1][j] - v) * f));
      return `<rect x="${(i % cols) * step}" y="${Math.floor(i / cols) * step}" width="${step + 1}" height="${step + 1}" fill="rgb(${c.join(',')})" opacity="${0.2 + 0.7 * t}" pointer-events="none"/>`;
    }).join('');
  }
  function paint() {
    rows = currentRows();
    groups = groupRows();
    let max = Math.max(1, ...groups.map(g => g.value));
    $('map-title').textContent = titles[layer];
    $('display').disabled = layer === 'model';
    $('from').disabled = layer === 'model';
    $('to').disabled = layer === 'model';
    let total =
      layer === 'sales'
        ? rows.reduce((s, r) => s + (typeof r.amount === 'number' ? r.amount : 0), 0)
        : rows.length;
    let global = stats(rows);
    let overall = DATA.model_summary;
    let cards =
      layer === 'model'
        ? [
            ['Historical test services', overall.services],
            ['Actual returns', overall.positive_cases],
            ['Historical accuracy', pct(overall.accuracy)],
            ['No-return baseline', pct(overall.always_no_return_accuracy)],
          ]
        : layer === 'sales'
          ? [
              ['Customers on map', new Set(rows.map(r => r.customer)).size],
              ['Sales on map', money(total)],
              ['Purchases on map', rows.length],
              [
                'Purchases without a location',
                DATA.unlocated_sales_dates.filter(d => d && d >= $('from').value && d <= $('to').value)
                  .length,
              ],
            ]
          : [
              ['Located warranty signals', rows.length],
              ['Proximity groups', groups.length],
              ['Visit completion', 'Not verified'],
              ['Biological recurrence', 'Not measured'],
            ];
    $('metrics').innerHTML = cards
      .map(([k, v]) => `<div class="metric"><span>${k}</span><strong>${safe(v)}</strong></div>`)
      .join('');
    let land = DATA.boundaries.features
      .map(f => {
        let polys = f.geometry.type === 'MultiPolygon' ? f.geometry.coordinates : [f.geometry.coordinates];
        return polys
          .map(
            c => `<path class="land" d="${pathFor(c)}"><title>${safe(f.properties.district)}</title></path>`,
          )
          .join('');
      })
      .join('');
    let cells = groups
      .map(g => {
        let [x, y] = position(g.lon, g.lat),
          w = (Number($('size').value) / 111) * 720 * zoom,
          fill =
            layer === 'model'
              ? g.metrics.supported
                ? g.metrics.accuracy > g.metrics.baseline
                  ? '#4277bd'
                  : '#d98b5b'
                : '#ccd3df'
              : `hsl(${layer === 'sales' ? 216 : 12} 68% ${90 - (48 * g.value) / max}%)`;
        return `<rect tabindex="0" role="button" aria-label="Proximity group with ${g.rs.length} records" class="cell" data-id="${g.id}" x="${x - w / 2}" y="${y - w / 2}" width="${w}" height="${w}" rx="4" fill="${fill}" opacity=".82"><title>${g.rs.length} records${layer === 'sales' ? ', ' + money(g.value) : ''}</title></rect>`;
      })
      .join('');
    let labels = DATA.boundaries.features
      .map(f => {
        let coords = f.geometry.coordinates.flat(Infinity),
          xs = [],
          ys = [];
        for (let i = 0; i < coords.length; i += 2) {
          xs.push(coords[i]);
          ys.push(coords[i + 1]);
        }
        let west = Math.min(...xs),
          east = Math.max(...xs),
          south = Math.min(...ys),
          north = Math.max(...ys),
          p = position((west + east) / 2, (south + north) / 2);
        if (
          (east - west) * 720 * zoom < 75 ||
          (north - south) * 720 * zoom < 40 ||
          p[0] < 35 ||
          p[0] > 865 ||
          p[1] < 25 ||
          p[1] > 535
        )
          return '';
        return `<text x="${p[0]}" y="${p[1]}" text-anchor="middle" fill="#475e76" font-size="11" pointer-events="none">${safe(f.properties.district)}</text>`;
      })
      .join('');
    let points =
      zoom >= 3
        ? rows
            .map((r, i) => {
              let [x, y] = position(r.longitude, r.latitude);
              return `<circle tabindex="0" role="button" aria-label="Inspect recorded location" class="point" data-point="${i}" cx="${x}" cy="${y}" r="5" fill="${layer === 'visits' ? '#d66143' : '#285d9f'}"><title>${safe(layer === 'sales' ? r.id : 'Recorded location')}, approximate mapped location</title></circle>`;
            })
            .join('')
        : '';
    let heatMode = $('display').value === 'heat' && layer !== 'model';
    const hitAreas = heatMode ? cells.replaceAll('class="cell"', 'class="cell heat-hit"') : cells;
    $('map').innerHTML =
      '<defs><filter id="heat-smooth" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="6"/></filter></defs>' +
      land +
      (heatMode ? '<g filter="url(#heat-smooth)">' + densityField() + '</g>' : '') +
      hitAreas +
      labels +
      points +
      `<text x="20" y="30" fill="#737373" font-size="12">${zoom.toFixed(zoom < 0.1 ? 2 : 1)}×, ${zoom >= 3 ? 'individual locations' : heatMode ? 'heatmap' : 'area groups'}</text>`;
    $('legend').innerHTML =
      layer === 'model'
        ? '● Grey: insufficient evidence, Blue: above no-return baseline, Orange: at/below baseline'
        : '<span>Lower</span><i></i><span>Higher ' +
          (layer === 'sales' ? 'sales density' : 'visit density') +
          '</span>';
    $('coverage').textContent =
      layer === 'model'
        ? `${rows.length} mapped services of ${DATA.model_total} evaluated historical services. The date filters do not change this fixed historical sample. Grey cells need at least 20 services and 5 return cases before performance colouring.`
        : `${layer === 'sales' ? DATA.sales_total : DATA.visit_total} total source records before date filters; ${DATA[layer].length} have saved reliable coordinates. Unlocated records stay in overall reporting totals. Drag to pan; zoom to reveal individual records. Points are geocoded estimates, not verified building locations. Heat intensity is a visual density estimate; use proximity cells for exact saved counts. Uncertain cell-boundary memberships are excluded from proximity totals.`;
    $('definition').textContent =
      layer === 'sales'
        ? 'Sales are recorded package prices, not cash received or profit. Points represent purchase locations; repeated purchases can overlap.'
        : layer === 'visits'
          ? 'These are Calendar warranty signals, not verified pest recurrence, completed treatments or formal claims. Counts can be high where more customers are served; a comparable return rate requires linked eligible services with complete follow-up.'
          : 'The frozen model is unchanged. Area accuracy can differ because different evaluated records are selected. Choosing regions after seeing their scores is exploratory and cannot establish superior future accuracy. Sample size, return detection, false alerts and the no-return baseline must accompany accuracy.';
    $('rank-title').textContent =
      layer === 'sales'
        ? 'Highest sales areas'
        : layer === 'visits'
          ? 'Most warranty visits'
          : 'Historical test areas';
    $('map-guide').textContent =
      layer === 'model'
        ? 'Grey areas have too little evidence to compare model performance.'
        : 'Select an area on the map or from the list. Zoom in for individual records.';
    $('ranking').innerHTML = groups
      .sort((a, b) => b.value - a.value)
      .slice(0, 5)
      .map(
        (g, i) =>
          `<div class="row"><span>Area ${i + 1}, ${safe(groupLabel(g))}</span><button data-id="${g.id}">${layer === 'sales' ? money(g.value) : g.rs.length + ' services'}</button></div>`,
      )
      .join('');
    $('coverage').textContent +=
      ' ' +
      (rows.length - groups.reduce((n, g) => n + g.rs.length, 0)) +
      ' records excluded from area-group totals by location uncertainty.' +
      (layer === 'model'
        ? ''
        : ' Heatmap uses all mapped records, weighted by ' +
          (layer === 'sales' ? 'sales amount' : 'visit count') +
          ' and spread by location uncertainty; colours are relative, not a recurrence rate.');
    if (selected) showGroup(selected);
    else {
      $('selection-title').textContent = 'Explore an area';
      $('selection').replaceChildren();
      const hint = document.createElement('p');
      hint.textContent =
        'Select a coloured area or one of the areas below. Zoom in to inspect individual locations.';
      $('selection').append(hint);
    }
  }
  function showGroup(id) {
    selected = id;
    let g = groups.find(g => g.id === id);
    if (!g) {
      selected = null;
      return;
    }
    let s = g.metrics;
    $('selection-title').textContent = groupLabel(g) + ', proximity group';
    $('selection').innerHTML =
      `<div class="row"><span>Centre</span><strong>${safe(groupLabel(g))}</strong></div><div class="row"><span>Group width</span><strong>${$('size').value} km</strong></div><div class="row"><span>Records</span><strong>${g.rs.length}</strong></div>` +
      (layer === 'sales'
        ? `<div class="row"><span>Customers on map</span><strong>${new Set(g.rs.map(r => r.customer)).size}</strong></div><div class="row"><span>Recorded sales</span><strong>${money(g.value)}</strong></div>`
        : layer === 'model'
          ? `<p class="badge">${s.supported ? 'Exploratory historical result' : 'Too few evaluated outcomes'}</p><div class="row"><span>Actual returns</span><strong>${s.positive}</strong></div><div class="row"><span>Accuracy / baseline</span><strong>${pct(s.accuracy)} / ${pct(s.baseline)}</strong></div><div class="row"><span>Returns detected</span><strong>${s.tp} / ${s.positive}</strong></div><div class="row"><span>False alerts / missed returns</span><strong>${s.fp} / ${s.fn}</strong></div>`
          : '<p class="note">Calendar warranty signals only. A visit count is not a recurrence rate.</p>') +
      `<button id="focus">Zoom into this group</button><p class="note">${zoom >= 3 ? 'Click a point to inspect its source record.' : 'Use Zoom into this group to inspect its recorded locations.'}</p>`;
  }
  document.addEventListener('click', e => {
    const customerLink = e.target.closest('.customer-map-link');
    if (customerLink) sessionStorage.setItem('cp2_map_sale', customerLink.dataset.sale);
    let b = e.target.closest('button');
    if (b?.dataset.layer) {
      layer = b.dataset.layer;
      selected = null;
      document.querySelectorAll('[data-layer]').forEach(x => x.classList.toggle('active', x === b));
      paint();
    }
    let id = e.target.closest('[data-id]')?.dataset.id;
    if (id) showGroup(id);
    let point = e.target.closest('[data-point]')?.dataset.point;
    if (point !== undefined) {
      let r = rows[Number(point)];
      $('selection-title').textContent = 'Individual record';
      $('selection').innerHTML =
        `<div class="row"><span>Source</span><strong>${safe(layer === 'model' ? 'Historical evaluated service' : r.id || 'Calendar warranty signal')}</strong></div><div class="row"><span>Date</span><strong>${safe(r.date || 'Fixed historical evaluation')}</strong></div>${layer === 'sales' ? `<p><a href="/#customers" class="customer-map-link" data-sale="${safe(r.id)}">Open customer history</a></p><div class="row"><span>Recorded sales</span><strong>${money(r.amount)}</strong></div><div class="row"><span>Package</span><strong>${safe(r.package)}</strong></div>` : ''}<div class="row"><span>Location uncertainty</span><strong>${Number(r.uncertainty_km || 0).toFixed(2)} km</strong></div><div class="row"><span>Overlapping records</span><strong>${rows.filter(x => Math.abs(x.latitude - r.latitude) < 0.00001 && Math.abs(x.longitude - r.longitude) < 0.00001).length}</strong></div><p class="note">Private staff records. Open a purchase in Customers to inspect its programme and history.</p><h3>Records at this location</h3>${rows
          .filter(
            x => Math.abs(x.latitude - r.latitude) < 0.00001 && Math.abs(x.longitude - r.longitude) < 0.00001,
          )
          .slice(0, 20)
          .map(
            x =>
              `<div class="row"><span>${layer === 'sales' ? `<a href="/#customers" class="customer-map-link" data-sale="${safe(x.id)}">${safe(x.id)}</a>` : safe(x.id || 'Evaluated service')}<br>${safe(x.date || 'Historical test')}</span><strong>${layer === 'sales' ? money(x.amount) : safe(x.pest || '')}</strong></div>`,
          )
          .join(
            '',
          )}<p class="note">Up to 20 overlapping records shown. Precise contacts are not included.</p>`;
    }
    if (b?.id === 'focus' && selected) {
      let g = groups.find(g => g.id === selected);
      centre = [g.lon, g.lat];
      zoom = 5;
      paint();
    }
    if (b?.id === 'zoomin') {
      zoom = Math.min(12, zoom * 1.6);
      paint();
    }
    if (b?.id === 'zoomout') {
      zoom = Math.max(0.03, zoom / 1.6);
      paint();
    }
    if (b?.id === 'fit') {
      fitAll();
      paint();
    }
    if (b?.id === 'reset') {
      zoom = 1;
      centre = [101.65, 3.12];
      selected = null;
      paint();
    }
    if (b?.id === 'apply') {
      if (!$('from').value || !$('to').value || $('from').value > $('to').value) {
        alert('Choose a From date before the To date.');
        return;
      }
      selected = null;
      paint();
    }
  });
  $('map').addEventListener(
    'wheel',
    e => {
      e.preventDefault();
      zoom = Math.max(0.03, Math.min(12, zoom * (e.deltaY < 0 ? 1.2 : 0.83)));
      paint();
    },
    { passive: false },
  );
  function fitAll() {
    let rs = currentRows();
    if (!rs.length) return;
    let west = Math.min(...rs.map(r => r.longitude)),
      east = Math.max(...rs.map(r => r.longitude)),
      south = Math.min(...rs.map(r => r.latitude)),
      north = Math.max(...rs.map(r => r.latitude));
    centre = [(west + east) / 2, (south + north) / 2];
    zoom = Math.max(
      0.03,
      Math.min(
        12,
        Math.min(780 / (720 * Math.max(0.02, east - west)), 440 / (720 * Math.max(0.02, north - south))),
      ),
    );
    selected = null;
  }
  $('display').addEventListener('change', () => paint());
  $('map').addEventListener('pointerdown', e => {
    if (e.target.closest('[data-id],[data-point]')) return;
    drag = { x: e.clientX, y: e.clientY, c: [...centre] };
    $('map').setPointerCapture(e.pointerId);
  });
  $('map').addEventListener('pointermove', e => {
    if (!drag) return;
    let rect = $('map').getBoundingClientRect();
    centre = [
      drag.c[0] - ((e.clientX - drag.x) * 900) / rect.width / (720 * zoom),
      drag.c[1] + ((e.clientY - drag.y) * 560) / rect.height / (720 * zoom),
    ];
    paint();
  });
  $('map').addEventListener('keydown', e => {
    if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[data-id],[data-point]')) {
      e.preventDefault();
      e.target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      return;
    }
    let delta = 0.08 / zoom;
    if (e.key === 'ArrowLeft') centre[0] -= delta;
    else if (e.key === 'ArrowRight') centre[0] += delta;
    else if (e.key === 'ArrowUp') centre[1] += delta;
    else if (e.key === 'ArrowDown') centre[1] -= delta;
    else if (e.key === '+' || e.key === '=') zoom = Math.min(12, zoom * 1.6);
    else if (e.key === '-') zoom = Math.max(0.03, zoom / 1.6);
    else return;
    e.preventDefault();
    paint();
  });
  $('map').addEventListener('pointerup', () => {
    drag = null;
  });
  $('map').addEventListener('pointercancel', () => {
    drag = null;
  });
  paint();
})().catch(error => {
  document.querySelector('.map-workbench').replaceChildren();
  const p = document.createElement('p');
  p.textContent = error.message;
  const a = document.createElement('a');
  a.href = '/';
  a.textContent = 'Back to staff sign-in';
  document.querySelector('.map-workbench').append(p, a);
});
