'use strict';
// Colours come from the stylesheet's tokens, so charts follow the theme.
const tok = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
let planningData, planningPending, paymentData;
let queueView = 'all';
const customerForm = $('customer-search');
if (customerForm) {
  const article = customerForm.closest('article');
  $('customer-history-slot').append(article);
}
const businessFirst = $('business-filter')?.closest('.panel');
if (businessFirst) businessFirst.hidden = true;
const systemDetails = el('details', undefined, 'panel research-details');
systemDetails.append(el('summary', 'System status'), $('system-cards'));
document.querySelector('[data-view="status"]').append(systemDetails);
// Keep the custom-area date controls visible without duplicating Looker charts.
const areaForm = $('business-radius');
if (areaForm) areaForm.before($('business-filter'));
function paymentAction(value) {
  return value === 'USE_SOURCE_REMINDER_DATES_AND_SALES_CUMULATIVE_PAID; DELIVERY_STATUS_UNKNOWN'
    ? 'Check Sales updates before sending a reminder'
    : 'Review the source record';
}
function knownTotal(rows, key) {
  const values = rows.map(r => r[key]).filter(v => v !== null && v !== undefined);
  return values.length ? values.reduce((a, v) => a + Number(v), 0) : null;
}
function tooltipText(target, label, text) {
  target.replaceChildren(el('span', label), help('About ' + label, text));
}
async function planning() {
  if (planningData) return planningData;
  if (!planningPending)
    planningPending = api('/api/planning')
      .then(r => {
        planningData = r;
        return r;
      })
      .finally(() => (planningPending = null));
  return planningPending;
}
async function paymentFollowup() {
  if (!paymentData) paymentData = await api('/api/payment-followup');
  const todayMY = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kuala_Lumpur' }),
    end = new Date(todayMY + 'T12:00:00Z');
  end.setUTCDate(end.getUTCDate() + 6);
  const endDay = end.toISOString().slice(0, 10);
  let rows = paymentData.contracts;
  const view = $('payment-queue').value;
  if (view === 'upcoming')
    rows = rows.filter(
      r =>
        r.next_scheduled_reminder_date &&
        r.next_scheduled_reminder_date >= todayMY &&
        r.next_scheduled_reminder_date <= endDay &&
        Number(r.sales_remaining_balance_rm) > 0,
    );
  if (view === 'missing')
    rows = rows.filter(r => !r.next_scheduled_reminder_date && Number(r.sales_remaining_balance_rm) > 0);
  if (view === 'balance') rows = rows.filter(r => Number(r.sales_remaining_balance_rm) > 0);
  if (view === 'unknown')
    rows = rows.filter(
      r => r.sales_remaining_balance_rm == null || !Number.isFinite(Number(r.sales_remaining_balance_rm)),
    );
  const unknownPaid = rows.filter(
    r => r.sales_total_recorded_paid_rm === null || r.sales_total_recorded_paid_rm === undefined,
  ).length;
  const unknownBalance = rows.filter(
    r => r.sales_remaining_balance_rm === null || r.sales_remaining_balance_rm === undefined,
  ).length;
  kpis('payment-totals', [
    ['Matching contracts', number(rows.length)],
    [
      'Recorded paid',
      money(knownTotal(rows, 'sales_total_recorded_paid_rm')),
      unknownPaid ? number(unknownPaid) + ' amounts unknown' : undefined,
    ],
    [
      'Remaining balance',
      money(
        knownTotal(
          rows.map(r => ({
            ...r,
            sales_remaining_balance_rm:
              r.sales_remaining_balance_rm == null ? null : Math.max(0, Number(r.sales_remaining_balance_rm)),
          })),
          'sales_remaining_balance_rm',
        ),
      ),
      unknownBalance ? number(unknownBalance) + ' balances unknown' : undefined,
    ],
  ]);
  table('payment-contracts', rows, [
    ['Customer', 'name'],
    ['Sale', 'sales_record_id'],
    ['Next reminder', 'next_scheduled_reminder_date', v => (v ? date(v) : 'No source date')],
    ['Recorded paid', 'sales_total_recorded_paid_rm', money, true],
    ['Remaining', 'sales_remaining_balance_rm', money, true],
    ['Follow-up', 'next_action', paymentAction],
  ]);
  addCustomerActions('payment-contracts', rows);
  tooltipText(
    $('payment-notice'),
    'Staff reminder schedule, ' + paymentData.receipt.published_release.replace('cp2r_', ''),
    paymentData.notice + ' Actual instalment payment dates and sent-message status are not available.',
  );
}
window.loadWorkspaceTools = async page => {
  try {
    if (page === 'home') await renderWorkQueue();
    if (page === 'customers') {
      const mappedSale = sessionStorage.getItem('cp2_map_sale');
      if (mappedSale) {
        $('customer-search').elements.q.value = mappedSale;
        sessionStorage.removeItem('cp2_map_sale');
      }
      loadCustomers();
    }
    if (page === 'payments') await paymentFollowup();
  } catch (e) {
    const target =
      page === 'home'
        ? 'work-queue'
        : page === 'payments'
          ? 'payment-notice'
          : page === 'customers'
            ? 'customer-summary'
            : 'forecast-notice';
    $(target).textContent = e.message;
  }
};
$('payment-queue').addEventListener('change', () =>
  paymentFollowup().catch(e => ($('payment-notice').textContent = e.message)),
);
function openReviewCustomer(row) {
  sessionStorage.setItem('cp2_map_sale', row.sales_record_id || row.name);
  location.hash = 'customers';
}
function addCustomerActions(id, rows) {
  const t = $(id).querySelector('table');
  if (!t) return;
  t.querySelector('thead tr').append(el('th', 'Action'));
  t.querySelectorAll('tbody tr').forEach((tr, i) => {
    const cell = el('td'),
      button = el('button', 'Open customer', 'secondary');
    button.type = 'button';
    button.addEventListener('click', () => openReviewCustomer(rows[i]));
    cell.append(button);
    tr.append(cell);
  });
}
async function renderWorkQueue() {
  if (!paymentData) paymentData = await api('/api/payment-followup');
  const q = paymentData.review_queue;
  if (!q) throw new Error('Review queue unavailable. Open Payment follow-up to inspect source records.');
  kpis('work-queue-counts', [
    ['Reminders, next 7 days', number(q.counts.upcoming)],
    ['Missing reminder dates', number(q.counts.missing)],
    ['Unknown balances', number(q.counts.unknown)],
  ]);
  const matching = q.tasks.filter(r => queueView === 'all' || r.review_kind === queueView),
    rows = matching.slice(0, 15);
  document.querySelectorAll('[data-review]').forEach(b => {
    b.classList.toggle('active', b.dataset.review === queueView);
    b.setAttribute('aria-pressed', String(b.dataset.review === queueView));
  });
  if (rows.length) {
    table('work-queue', rows, [
      ['Customer', 'name'],
      ['Why review', 'review_reason'],
      ['Reminder', 'next_scheduled_reminder_date', v => (v ? date(v) : 'Confirm date')],
      ['Recorded balance', 'sales_remaining_balance_rm', money, true],
      ['Next step', 'review_action'],
    ]);
    addCustomerActions('work-queue', rows);
  } else empty($('work-queue'), 'No matching review items in the published records.');
  $('work-queue-notice').replaceChildren(
    el('span', number(matching.length) + ' matching items, first 15 shown, as of ' + date(q.as_of)),
    help('About this review queue', q.notice + ' Source release: ' + paymentData.receipt.published_release),
  );
}
document.querySelectorAll('[data-review]').forEach(button =>
  button.addEventListener('click', () => {
    queueView = button.dataset.review;
    renderWorkQueue().catch(e => ($('work-queue').textContent = e.message));
  }),
);

const spatialLink = document.createElement('a');
spatialLink.href = '/maps';
spatialLink.className = 'btn btn-ghost btn-sm';
spatialLink.textContent = 'Open heatmaps';
$('business-radius').closest('article')?.querySelector('.panel-head')?.append(spatialLink);

// Source-backed aggregate visuals; no customer-level scores or synthetic forecasts.
function modelBars(target, rows, description) {
  target.replaceChildren(el('p', description));
  const svg = svgNode('svg', {
    viewBox: '0 0 860 ' + (rows.length * 40 + 20),
    role: 'img',
    'aria-label': description,
    class: 'model-bars',
  });
  const max = Math.max(1, ...rows.map(r => r.value));
  rows.forEach((r, i) => {
    const y = 6 + i * 40;
    svg.append(svgNode('text', { x: 0, y: y + 17, fill: tok('--color-ink-2'), 'font-size': 16 }, r.label));
    svg.append(
      svgNode('rect', { x: 275, y: y + 4, width: (500 * r.value) / max, height: 16, rx: 4, fill: r.color }),
    );
    svg.append(
      svgNode(
        'text',
        { x: 285 + (500 * r.value) / max, y: y + 16, fill: tok('--color-ink'), 'font-size': 16, 'font-weight': 600 },
        number(r.value),
      ),
    );
  });
  target.append(svg);
}
window.renderResearchModel = async (target, id) => {
  target.replaceChildren(el('p', 'Loading historical evidence…'));
  try {
    const r = await planning();
    if (id === 'return60') {
      const research = target,
        b = r.research_best?.candidate;
      if (b) {
        modelBars(
          research,
          [
            { label: 'Returns detected', value: b.TP, color: tok('--chart-actual') },
            { label: 'Returns missed', value: b.FN, color: tok('--chart-miss') },
            { label: 'False alerts', value: b.FP, color: tok('--chart-rule') },
          ],
          'Will a residential programme have a recorded pest return within 60 days after its final paid service?',
        );
        modelFacts(research, 'Research candidate, logistic regression', [
          ['Tested', number(b.services) + ' programmes'],
          ['Actual returns', number(b.positive_windows)],
          ['Accuracy', percent(b.pooled_accuracy)],
          ['No-return baseline', percent(b.always_no_return_accuracy)],
          ['Returns detected', percent(b.pooled_recall)],
          ['Alerts correct', percent(b.pooled_precision)],
          ['F1 score', b.pooled_f1.toFixed(3)],
          ['Time folds', number(b.folds)],
        ]);
        research.append(
          el(
            'p',
            'Highest F1 in the inspected historical search; selected after comparing results. Different target and population from the 30-day test. Research only: not running live predictions and not a replacement for the frozen future test.',
            'notice',
          ),
        );
      } else research.replaceChildren(el('p', 'Research evidence unavailable.'));
    } else {
      const repeat = target;
      const p = r.repeat_purchase.evaluation;
      if (p) {
        modelBars(
          repeat,
          [
            { label: 'Actual repeat buyers, found', value: p.cases_in_review_list, color: tok('--chart-actual') },
            {
              label: 'Actual repeat buyers, missed',
              value: p.positive_customers - p.cases_in_review_list,
              color: tok('--chart-miss'),
            },
            { label: 'Listed customers, did not repeat', value: p.false_alerts_in_review_list, color: tok('--chart-rule') },
          ],
          'Who might buy again within 90 days? Historical test: ' +
            p.customers +
            ' customers; ' +
            p.review_budget +
            ' on the ranked review list.',
        );
        repeat.append(
          el(
            'p',
            'This is a ranking, not a reliable purchase probability. Finding 13 of 19 repeat buyers is not 68% classification accuracy.',
          ),
        );
        modelFacts(repeat, 'Experimental ranking, 90-day repeat purchase', [
          ['Tested', number(p.customers) + ' customers'],
          ['Actual repeat buyers', number(p.positive_customers)],
          ['Buyers found', percent(p.capture_fraction)],
          ['Listed customers', number(p.review_budget)],
          ['List precision', percent(p.cases_in_review_list / p.review_budget)],
          ['Accuracy', 'Not a yes/no test'],
        ]);
      } else repeat.replaceChildren(el('p', 'Repeat-purchase evaluation is unavailable.'));
    }
  } catch (error) {
    target.replaceChildren(el('p', 'Historical evidence unavailable: ' + error.message));
  }
};
function modelFacts(target, label, values) {
  const head = el('div', label, 'model-label'),
    grid = el('div', undefined, 'model-facts');
  values.forEach(([name, value]) => {
    const box = el('div');
    box.append(el('span', name), el('strong', value));
    grid.append(box);
  });
  target.prepend(head, grid);

}
