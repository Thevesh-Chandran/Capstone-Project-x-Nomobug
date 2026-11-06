'use strict';
/* Sidebar navigation and page title, shared by the main portal and the heatmap page. */
(function () {
  const I = {
    overview: '<path d="M3 13h4v7H3zM10 9h4v11h-4zM17 4h4v16h-4z"/>',
    today: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    home: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3.5 6 1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2"/>',
    payments: '<rect x="3" y="6" width="18" height="13" rx="2"/><path d="M3 10h18M7 15h3"/>',
    plan: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    customers:
      '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5"/><path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c1.8.8 3 2.6 3.5 5.2"/>',
    risk: '<path d="M12 3l8 3.5v5.5c0 4.6-3.3 7.8-8 9-4.7-1.2-8-4.4-8-9V6.5z"/><path d="M12 8v5M12 16.2v.1"/>',
    performance: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    dashboard:
      '<rect x="3" y="3" width="7" height="8" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="15" width="7" height="6" rx="1.5"/>',
    business: '<path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z"/><path d="M9 4v13.5M15 6.5V20"/>',
    maps: '<path d="M19 10c0 5-7 11-7 11s-7-6-7-11a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    status: '<path d="M4 19l5-6 4 3 7-9"/><path d="M15 7h5v5"/>',
    models: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/>',
    returns: '<path d="M3 17l5-5 4 3 8-8"/><path d="M14 7h6v6"/><circle cx="5" cy="20" r=".6"/>',
    areas:
      '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".8"/>',
  };
  // Report pages are dashboard pages shown inside the website (route -> dashboard page).
  // Only the overview is a report on its own; every other page shows its dashboard section
  // on top and the website's actions or predictions underneath (see CP2_PAGE_REPORT).
  window.CP2_REPORTS = { 'r-overview': '' };
  window.CP2_PAGE_REPORT = {
    returns: 'follow-up',
    home: 'payments',
    plan: 'bookings',
    customers: 'sales-and-areas',
    models: 'services-and-warranty',
    '/maps': 'maps-and-patterns',
  };
  // Operational tools stay prominent; source browsing and research are secondary.
  const NAV = [
    { label: '', views: [['r-overview', 'Overview', 'overview']] },
    {
      label: 'Daily work',
      views: [
        ['returns', 'Service follow-up'],
        ['home', 'Payments'],
        ['plan', 'Bookings & workload'],
        ['customers', 'Sales & customers'],
      ],
    },
    { label: 'Areas', views: [['/maps', 'Maps & patterns', 'maps']] },
    {
      label: 'Predictions',
      views: [
        ['models', 'Return visits & models'],
        ['status', 'Technical evidence'],
      ],
    },
    // Shown only to the owner account (app.js unhides it when /api/access answers).
    { label: 'Admin', views: [['access', 'Who has access', 'customers']], ownerOnly: true },
  ];
  const TITLES = {};
  NAV.forEach(gp => gp.views.forEach(([r, t]) => (TITLES[r] = t)));
  // Pages reached from inside other pages rather than the menu.
  Object.assign(
    TITLES,
    {
      overview: 'Management overview',
      today: 'Workspace',
      plan: 'Bookings & workload',
      performance: 'Performance',
      payments: 'Payments',
      business: 'Areas',
      areas: 'Accuracy by district',
      risk: 'Warranty-risk research',
    },
    { ...TITLES },
  );
  window.CP2_TITLES = TITLES;
  const $ = id => document.getElementById(id);
  const isMaps = location.pathname === '/maps';
  function build() {
    const nav = document.querySelector('.side-nav');
    if (!nav || nav.dataset.built) return;
    nav.dataset.built = '1';
    nav.replaceChildren();
    NAV.forEach(gp => {
      const box = document.createElement('div');
      box.className = 'side-group';
      if (gp.ownerOnly) {
        box.hidden = true;
        box.dataset.ownerOnly = '1';
      }
      if (gp.label) {
        const l = document.createElement('div');
        l.className = 'side-label';
        l.textContent = gp.label;
        box.append(l);
      }
      gp.views.forEach(([route, text, icon]) => {
        const a = document.createElement('a');
        a.className = 'side-link';
        a.dataset.route = route;
        const alias = Object.keys(window.CP2_ALIAS || {}).find(k => window.CP2_ALIAS[k] === route);
        a.href = route.startsWith('/') ? route : (isMaps ? '/#' : '#') + (alias || route);
        a.innerHTML = `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${I[icon || route]}</svg>`;
        const sp = document.createElement('span');
        sp.textContent = text;
        a.append(sp);
        box.append(a);
      });
      nav.append(box);
    });
  }
  function render(route) {
    if (route === 'decisions') route = 'returns';
    const t = TITLES[route] || TITLES.today;
    document.querySelectorAll('.side-link').forEach(a => {
      const on = a.dataset.route === route;
      a.classList.toggle('active', on);
      if (on) {
        a.setAttribute('aria-current', 'page');
        const dd = a.closest('details');
        if (dd) dd.open = true;
      } else a.removeAttribute('aria-current');
    });
    document.title = `${t}, Nomobug`;
    document.body.dataset.route = route.replace('/', '');
    const head = $('page-header');
    if (head) {
      head.replaceChildren();
      const h = document.createElement('h1');
      h.textContent = t;
      head.append(h);
    }
  }
  build();
  // Dashboard sections grow with their content so the page scrolls as one.
  setInterval(() => {
    document.querySelectorAll('.report-frame').forEach(f => {
      try {
        const d = f.contentDocument;
        const h = d && d.body && Math.max(d.documentElement.scrollHeight, d.body.scrollHeight);
        if (h && f.offsetParent && Math.abs(f.offsetHeight - h) > 4) f.style.height = h + 'px';
      } catch (e) {}
    });
  }, 400);
  window.onRoute = (route, ready) => {
    render(route);
    window.scrollTo({ top: 0, behavior: 'instant' });
    if (ready && window.loadStage) window.loadStage(route === 'decisions' ? 'returns' : route);
  };
  render(isMaps ? '/maps' : (window.cp2Page ? window.cp2Page() : location.hash.slice(1)) || 'returns');
  if (isMaps) {
    const lo = $('logout');
    if (lo)
      lo.addEventListener('click', async () => {
        try {
          await fetch('/api/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
          });
        } catch (e) {}
        location.assign('/');
      });
    const d = $('snapshot-date');
    if (d) d.textContent = 'Heatmap view';
  }
})();

// Deferred scripts may attach after the fast local state request completes.
if (location.pathname !== '/maps' && typeof navigate === 'function') navigate();
