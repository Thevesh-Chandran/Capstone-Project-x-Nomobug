/* Local interface guidance: no customer data or AI requests on hover. */
(() => {
  'use strict';
  const pages = {
    plan: [
      'Plan',
      'Review the upcoming bookings, compare the full-week appointment-hours forecast with staff-entered available hours, then save the scenario. Booking counts do not establish team capacity.',
    ],
    home: [
      'Work',
      'Start with records to review, or find a customer. Verify the latest source balance and schedule before contacting the customer. This system does not send reminders.',
    ],
    dashboard: [
      'Business dashboard',
      'Use the report filters to change the period and groups. Open in Looker if the embedded report does not load.',
    ],
    customers: [
      'Customers',
      'Search a customer name or sale ID to inspect purchases and service programmes. Repeat-purchase suggestions are experimental.',
    ],
    payments: [
      'Payment follow-up',
      'Check recorded paid amounts, remaining balances and reminder dates. A passed reminder date does not prove payment or that a reminder was sent.',
    ],
    business: [
      'Area explorer',
      'Choose Sales, Warranty visits or Historical model. Select a hotspot, then zoom in to inspect individual recorded locations.',
    ],
    areas: [
      'Model test by area',
      'Compare historical predictions for a selected district or radius. Small groups are uncertain; changing the area does not retrain the model.',
    ],
    status: [
      'Evidence',
      'Inspect model evidence, booking forecasts and source freshness. Model scores are experimental.',
    ],
  };
  const hints = {
    district: 'Choose a district to inspect its saved historical model results.',
    'payment-queue': 'Choose upcoming reminder dates, missing dates or contracts with a recorded balance.',
    'customer-search': 'Find a customer by name or sale ID. Results show recorded programmes and purchases.',
    'business-radius': 'Choose a named area and radius to compare the records safely located inside it.',
    'radius-form': 'Compare the historical test sample within a named area and radius.',
    from: 'Start date for the map records.',
    to: 'End date for the map records.',
    display: 'Density heatmap shows concentrations. Proximity groups let you compare nearby records.',
    size: 'Choose the size of nearby location groups. Changing it changes the grouping, not the model.',
    apply: 'Apply the selected dates and map settings.',
    zoomin: 'Zoom in to separate hotspots and reveal individual records.',
    zoomout: 'Zoom out to see the wider area.',
    fit: 'Fit all available locations into the map.',
    reset: 'Restore the map view.',
    'ask-button':
      'Send your question. Answers use approved project evidence; broader explanations can take longer.',
    'dashboard-link': 'Open the original report in Looker Studio.',
    logout: 'Sign out of this workspace.',
  };
  const root = document.createElement('div');
  root.className = 'workspace-guide';
  root.innerHTML = `<div class="guide-bubble" id="guide-bubble" hidden role="status"></div><section class="guide-panel" id="guide-panel" hidden aria-label="Workspace guide"><div class="guide-head"><div><strong>Workspace guide</strong><small>Help where you need it</small></div><button type="button" class="guide-close" aria-label="Close guide">×</button></div><p id="guide-page-help"></p><div class="guide-actions"><button type="button" id="guide-explain">Explain this page</button><a href="/#status" id="guide-ask">Model evidence <span aria-hidden="true"></span></a></div><label class="guide-preference"><input type="checkbox" id="guide-enabled">Explain controls on hover or keyboard focus</label><small class="guide-disclosure">Interface tips explain the controls. Model evidence is available separately.</small></section><button type="button" class="guide-launcher" aria-label="Open workspace guide" aria-controls="guide-panel" aria-expanded="false"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M20 11a8 8 0 0 1-8 8H5l-3 3v-10a9 9 0 0 1 18-1Z"/><path d="M8 9h8M8 13h5"/></svg><span>Guide</span></button>`;
  document.body.append(root);
  const bubble = root.querySelector('#guide-bubble'),
    panel = root.querySelector('#guide-panel'),
    launcher = root.querySelector('.guide-launcher'),
    enabled = root.querySelector('#guide-enabled');
  let awake = false,
    hideTimer;
  try {
    awake = localStorage.getItem('nomobug-guide-enabled') === 'true';
  } catch {}
  enabled.checked = awake;
  const current = () =>
    location.pathname.replace(/\/$/, '') === '/maps' ? 'business' : location.hash.slice(1) || 'home';
  function pageHelp() {
    const value = pages[current()] || pages.home;
    root.querySelector('.guide-head small').textContent = value[0];
    root.querySelector('#guide-page-help').textContent = value[1];
    return value[1];
  }
  function close() {
    clearTimeout(hideTimer);
    panel.hidden = true;
    bubble.hidden = true;
    launcher.setAttribute('aria-expanded', 'false');
  }
  launcher.addEventListener('click', () => {
    const open = panel.hidden;
    panel.hidden = !open;
    bubble.hidden = true;
    launcher.setAttribute('aria-expanded', String(open));
    pageHelp();
  });
  root.querySelector('.guide-close').addEventListener('click', () => {
    close();
    launcher.focus();
  });
  enabled.addEventListener('change', () => {
    awake = enabled.checked;
    bubble.hidden = true;
    try {
      localStorage.setItem('nomobug-guide-enabled', String(awake));
    } catch {}
  });
  root.querySelector('#guide-explain').addEventListener('click', pageHelp);
  root.querySelector('#guide-ask').addEventListener('click', () => {
    close();
  });
  function tipFor(target) {
    if (!(target instanceof Element) || root.contains(target)) return '';
    const tooltip = target.closest('.help-wrap')?.querySelector('.tooltip');
    if (tooltip) return tooltip.textContent.trim();
    const nav = target.closest('[data-page]');
    if (nav && pages[nav.dataset.page]) return pages[nav.dataset.page][1];
    for (let known = target; known && known !== document.body; known = known.parentElement) {
      if (known.id && hints[known.id]) return hints[known.id];
    }
    const layer = target.closest('[data-layer]');
    if (layer)
      return (
        {
          sales: 'Map recorded sales by customer location. These amounts are sales, not profit.',
          visits:
            'Map recorded warranty/return visits. A booking is not confirmation that treatment was completed.',
          model:
            'Explore saved historical model results. Small local samples cannot establish dependable accuracy.',
        }[layer.dataset.layer] || ''
      );
    return '';
  }
  function showTip(event) {
    if (!awake || !panel.hidden) return;
    const text = tipFor(event.target);
    clearTimeout(hideTimer);
    if (!text) {
      bubble.hidden = true;
      return;
    }
    bubble.textContent = text;
    bubble.hidden = false;
  }
  document.addEventListener('pointerover', showTip);
  document.addEventListener('focusin', showTip);
  document.addEventListener('pointerout', event => {
    if (
      event.relatedTarget instanceof Node &&
      event.target instanceof Node &&
      event.target.contains(event.relatedTarget)
    )
      return;
    hideTimer = setTimeout(() => {
      bubble.hidden = true;
    }, 180);
  });
  document.addEventListener('focusout', () => {
    bubble.hidden = true;
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      close();
      bubble.hidden = true;
    }
  });
  document.addEventListener('click', e => {
    if (!root.contains(e.target)) {
      close();
      bubble.hidden = true;
    }
  });
  window.addEventListener('hashchange', () => {
    close();
    pageHelp();
  });
  const workspace = document.getElementById('workspace');
  if (workspace) {
    const sync = () => {
      root.hidden = workspace.hidden;
    };
    new MutationObserver(sync).observe(workspace, { attributes: true, attributeFilter: ['hidden'] });
    sync();
  }
  pageHelp();
})();
