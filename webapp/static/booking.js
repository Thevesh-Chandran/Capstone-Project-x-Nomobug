'use strict';
// Staff already plan travel and slots with Google Maps and Google Calendar, so this page shows
// the weekly workload forecast and the team calendars. The slot finder below is kept in the code
// (renderBookingTools) but no longer shown on the page.
let bookingView = 'demand';
function attachBookingTools(root) {
  const demand = el('div'),
    children = Array.from(root.children);
  children.slice(1).forEach(n => demand.append(n));
  const bookingRoot = el('div', undefined, 'booking-workspace'),
    googleRoot = el('div', undefined, 'google-calendar-view'),
    tabs = el('div', undefined, 'context-tabs booking-tabs');
  const buttons = [];
  [
    ['demand', 'Weekly workload'],
    ['google', 'Google Calendar'],
  ].forEach(([key, label]) => {
    const b = deskButton(
      label,
      () => {
        bookingView = key;
        sync();
      },
      'quiet',
    );
    buttons.push([key, b]);
    tabs.append(b);
  });
  function sync() {
    bookingRoot.hidden = bookingView !== 'booking';
    googleRoot.hidden = bookingView !== 'google';
    demand.hidden = bookingView !== 'demand';
    if (bookingView === 'google') renderGoogleCalendar(googleRoot);
    buttons.forEach(([key, b]) => b.setAttribute('aria-pressed', String(key === bookingView)));
  }
  root.append(tabs, googleRoot, demand);
  sync();
}
// Plain explanation at the top of the page: what it does and what it does not do.
function bookingIntro() {
  const box = el('section', undefined, 'booking-intro');
  const text = el('div');
  text.append(
    el('h2', 'Find a good time for a customer visit'),
    el(
      'p',
      'This page reads all six team calendars and suggests times that fit. It does not book anything: once you choose a time, add it in Google Calendar as usual.',
    ),
  );
  const steps = el('ol', undefined, 'booking-steps');
  [
    ['See who is busy', 'The team calendar below shows every appointment, side by side.'],
    ['Describe the visit', 'Enter the customer area, visit type, date and how long it takes.'],
    ['Pick a suggested time', 'Compare gaps for suitable teams, with the travel-time allowance you entered.'],
  ].forEach(([title, detail], i) => {
    const li = el('li');
    li.append(el('b', String(i + 1)), el('div'));
    li.lastChild.append(el('strong', title), el('span', detail));
    steps.append(li);
  });
  box.append(text, steps);
  return box;
}
// The real Google Calendar, embedded. Staff see events only if their Google account has access.
function renderGoogleCalendar(root) {
  if (root.dataset.ready) return;
  root.dataset.ready = '1';
  const url = typeof state !== 'undefined' && state ? state.google_calendar_url : null;
  const head = el('div', undefined, 'google-calendar-head');
  head.append(
    el('p', 'View the team calendars here. Use Open Google Calendar to create or change bookings.', 'desk-muted'),
  );
  const open = el('a', 'Open Google Calendar', 'secondary');
  open.href = 'https://calendar.google.com/calendar/r/week';
  open.target = '_blank';
  open.rel = 'noopener';
  head.append(open);
  root.append(head);
  if (!url) {
    root.append(
      el(
        'p',
        'The team calendars have not been linked to this page yet. Use the button above to open Google Calendar in a new tab.',
        'notice',
      ),
    );
    return;
  }
  const frame = el('iframe');
  frame.className = 'google-calendar-frame';
  frame.title = 'Team Google Calendars';
  frame.src = url;
  frame.loading = 'lazy';
  root.append(
    frame,
    el(
      'p',
      'If the calendar shows as empty, sign in to Google in this browser with an account that can see the team calendars, or use the button above.',
      'desk-footnote',
    ),
  );
}
async function renderBookingTools(root) {
  root.replaceChildren(el('p', 'Loading the Calendar schedule…', 'desk-muted'));
  try {
    const data = await api('/api/booking');
    root.replaceChildren();
    const source = el('div', undefined, 'desk-source');
    source.append(
      el(
        'span',
        data.status === 'ready' ? 'Calendar schedule available' : 'Calendar schedule needs refreshing',
        'desk-dot ' + (data.status === 'ready' ? '' : 'amber'),
      ),
      el(
        'span',
        data.captured_at
          ? new Date(data.captured_at).toLocaleString('en-MY', { timeZone: 'Asia/Kuala_Lumpur' }) + ' MYT'
          : 'No verified extraction',
      ),
    );
    root.append(source);
    const calendarHost = el('section', undefined, 'booking-calendar-host');
    root.append(calendarHost);
    const layout = el('div', undefined, 'booking-layout'),
      panel = deskPanel('New or rescheduled appointment'),
      aside = deskPanel('How options are chosen');
    aside.append(
      el('p', 'Usual team first. If it cannot fit, check cross-area cover and Replacement.', 'desk-muted'),
    );
    const roster = el('dl', undefined, 'booking-roster');
    data.teams.forEach(t => {
      const area = !t.active
        ? 'Inactive'
        : t.visit_type === 'consultation'
          ? 'Consultations only'
          : t.role === 'backup'
            ? t.allowed_regions.join(' / ') + ' backup'
            : t.normal_region || t.normal_areas.join(', ');
      roster.append(el('dt', t.id[0].toUpperCase() + t.id.slice(1)), el('dd', area));
    });
    aside.append(roster);
    aside.append(
      el(
        'p',
        'These are schedule checks, not a trained prediction model. No appointment is booked, moved or reserved.',
        'desk-footnote',
      ),
    );
    const form = el('form', undefined, 'booking-form'),
      result = el('div', undefined, 'booking-results');
    result.setAttribute('aria-live', 'polite');
    function field(title, input) {
      const label = el('label', title, 'desk-field');
      label.append(input);
      return label;
    }
    function select(name, rows) {
      const input = el('select');
      input.name = name;
      rows.forEach(([value, title]) => {
        const o = el('option', title);
        o.value = value;
        input.append(o);
      });
      return input;
    }
    const operation = select('operation', [
      ['new', 'New booking'],
      ['move', 'Reschedule an appointment'],
    ]);
    form.append(field('What would you like to do?', operation));
    const moveGroup = el('div'),
      search = el('input'),
      move = select('reschedule_key', [['', 'Search for the customer first']]),
      matches = el('p', undefined, 'desk-footnote');
    search.type = 'search';
    moveGroup.hidden = true;
    move.disabled = true;
    moveGroup.append(
      field('Find the appointment by customer name', search),
      field('Appointment to move', move),
      matches,
    );
    form.append(moveGroup);
    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      move.replaceChildren();
      const first = el('option', q.length < 2 ? 'Enter at least two letters' : 'Choose the appointment');
      first.value = '';
      move.append(first);
      const found =
        q.length < 2
          ? []
          : data.events.filter(
              e =>
                e.reschedulable &&
                data.teams.some(t => t.id === e.team_id && t.active) &&
                e.label.toLowerCase().includes(q),
            );
      found.slice(0, 40).forEach(e => {
        const o = el(
          'option',
          e.label +
            ', ' +
            new Date(e.start).toLocaleString('en-MY', {
              timeZone: 'Asia/Kuala_Lumpur',
              dateStyle: 'short',
              timeStyle: 'short',
            }) +
            ', ' +
            e.team_id,
        );
        o.value = e.key;
        move.append(o);
      });
      matches.textContent =
        q.length < 2
          ? ''
          : found.length + ' matches' + (found.length > 40 ? ', first 40 shown; narrow the search' : '');
    });
    operation.addEventListener('change', () => {
      moveGroup.hidden = operation.value !== 'move';
      move.disabled = operation.value !== 'move';
      move.required = operation.value === 'move';
      if (move.disabled) move.value = '';
    });
    const pair = el('div', undefined, 'booking-pair'),
      area = select(
        'area',
        data.areas.map(a => [a.id, a.name]),
      ),
      kind = select('visit_type', [
        ['treatment', 'Treatment'],
        ['consultation', 'Consultation'],
      ]);
    pair.append(field('Customer area', area), field('Visit type', kind));
    form.append(pair);
    const dateInput = el('input');
    dateInput.type = 'date';
    dateInput.name = 'date';
    dateInput.required = true;
    const today = new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kuala_Lumpur' });
    dateInput.min = today > data.window_start ? today : data.window_start || today;
    dateInput.max = data.window_end || today;
    dateInput.value = dateInput.min;
    const duration = el('input');
    duration.type = 'number';
    duration.name = 'duration_minutes';
    duration.min = 15;
    duration.max = 480;
    duration.step = 1;
    duration.required = true;
    duration.value = '60';
    const row = el('div', undefined, 'booking-pair');
    row.append(field('Preferred date', dateInput), field('Appointment length (minutes)', duration));
    form.append(row);
    const start = el('input'),
      end = el('input');
    start.type = end.type = 'time';
    start.name = 'work_start';
    end.name = 'work_end';
    start.required = end.required = true;
    start.value = '09:00';
    end.value = '18:00';
    const hours = el('div', undefined, 'booking-pair');
    hours.append(field('Teams can start at', start), field('Teams finish by', end));
    form.append(hours);
    const buffer = el('input');
    buffer.type = 'number';
    buffer.name = 'travel_buffer_minutes';
    buffer.min = 0;
    buffer.max = 120;
    buffer.step = 1;
    buffer.required = true;
    buffer.value = '30';
    form.append(field('Travel time around each existing appointment (minutes)', buffer));
    const teams = el('fieldset', undefined, 'booking-teams');
    teams.append(el('legend', 'Teams checked as available for these hours'));
    function showTeams() {
      teams.querySelectorAll('label').forEach(n => n.remove());
      data.teams
        .filter(t => t.active && t.visit_type === kind.value)
        .forEach(t => {
          const box = el('input');
          box.type = 'checkbox';
          box.name = 'available_teams';
          box.value = t.id;
          const label = el('label');
          label.append(box, el('span', t.calendar_name.replace(/\s*\([^)]*\)/, '')));
          teams.append(label);
        });
    }
    kind.addEventListener('change', showTeams);
    showTeams();
    form.append(teams);
    const confirmation = el('label', undefined, 'booking-confirmation'),
      checked = el('input');
    checked.type = 'checkbox';
    checked.required = true;
    confirmation.append(
      checked,
      el('span', 'I checked working hours, breaks and the selected teams’ suitability for this service.'),
    );
    form.append(confirmation);
    const submit = el('button', 'Find Calendar-fit options', 'primary');
    submit.disabled = data.status !== 'ready';
    form.append(submit);
    if (data.status !== 'ready')
      panel.append(
        el(
          'p',
          'A fresh, complete six-team Calendar extraction is needed before checking slots.',
          'desk-error',
        ),
      );
    const calendar = createBookingCalendar(calendarHost, data, {
      date: dateInput.value,
      onDate: day => {
        dateInput.value = day;
        dateInput.dispatchEvent(new Event('input', { bubbles: true }));
      },
      onMove: event => {
        operation.value = 'move';
        operation.dispatchEvent(new Event('change', { bubbles: true }));
        search.value = event.label;
        search.dispatchEvent(new Event('input', { bubbles: true }));
        move.value = event.key;
        duration.value = String(
          Math.max(15, Math.round((new Date(event.end) - new Date(event.start)) / 60000)),
        );
        move.dispatchEvent(new Event('change', { bubbles: true }));
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
      },
    });
    let formRevision = 0;
    function invalidateOptions(event) {
      formRevision++;
      result.replaceChildren();
      calendar.update(dateInput.value, []);
      if (event.target !== checked) checked.checked = false;
    }
    form.addEventListener('input', invalidateOptions);
    form.addEventListener('change', invalidateOptions);
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const body = Object.fromEntries(new FormData(form));
      body.staff_confirmed = checked.checked;
      body.all_slots = true;
      body.available_teams = Array.from(form.querySelectorAll('[name=available_teams]:checked')).map(
        n => n.value,
      );
      if (!body.available_teams.length) {
        result.replaceChildren(el('p', 'Select the teams you have checked as available.', 'desk-error'));
        return;
      }
      const submittedRevision = formRevision;
      submit.disabled = true;
      result.replaceChildren(el('p', 'Checking appointment clashes…', 'desk-muted'));
      try {
        const response = await jsonPost('/api/booking/options', body);
        if (formRevision !== submittedRevision) return;
        calendar.update(body.date, response.options);
        result.replaceChildren(
          el('h2', response.options.length ? 'Calendar-fit options' : 'No option to show'),
          el('p', response.message, 'desk-muted'),
        );
        if (response.options.length) {
          result.append(
            el(
              'p',
              'All suitable starts are highlighted on the calendar. First 12 options are listed below.',
              'desk-footnote',
            ),
          );
          const table = el('table'),
            head = el('tr');
          ['Team', 'Time', 'Coverage', ''].forEach(v => head.append(el('th', v)));
          table.append(head);
          response.options.slice(0, 12).forEach(o => {
            const tr = el('tr'),
              when = v =>
                new Date(v).toLocaleTimeString('en-MY', {
                  timeZone: 'Asia/Kuala_Lumpur',
                  hour: 'numeric',
                  minute: '2-digit',
                }),
              cell = el('td'),
              copy = deskButton('Copy option', async () => {
                const text = [
                  o.team,
                  body.date + ', ' + when(o.start) + '–' + when(o.end),
                  o.reason,
                  'Travel allowance: ' +
                    o.travel_buffer_minutes +
                    ' minutes around existing appointments (staff assumption).',
                  'Confirm the route and current Calendar before booking. Nothing has been reserved.',
                ].join('\n');
                try {
                  await navigator.clipboard.writeText(text);
                  copy.textContent = 'Copied';
                } catch {
                  copy.textContent = 'Copy unavailable';
                }
              });
            cell.append(copy);
            tr.append(
              el('td', o.team.replace(/\s*\([^)]*\)/, '')),
              el('td', when(o.start) + '–' + when(o.end)),
              el('td', o.reason),
              cell,
            );
            table.append(tr);
          });
          const wrap = el('div', undefined, 'table-wrap');
          wrap.append(table);
          result.append(wrap);
          result.append(
            el(
              'p',
              'Travel has not been verified. Check the route and the current Calendar before confirming with the customer.',
              'desk-footnote',
            ),
          );
        }
      } catch (error) {
        if (formRevision === submittedRevision) deskError(result, error);
      } finally {
        submit.disabled = data.status !== 'ready';
      }
    });
    panel.append(form);
    layout.append(panel, aside);
    root.append(layout, result);
  } catch (error) {
    deskError(root, error);
  }
}

function createBookingCalendar(host, data, actions) {
  let selectedDate = actions.date,
    view = 'day',
    teamId = data.teams.find(t => t.active && t.visit_type === 'treatment').id,
    options = [];
  const addDays = (day, n) => {
    const d = new Date(day + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const dayOf = stamp =>
    new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Kuala_Lumpur',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date(stamp));
  const minute = stamp => {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kuala_Lumpur',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(new Date(stamp));
    return (
      Number(parts.find(p => p.type === 'hour').value) * 60 +
      Number(parts.find(p => p.type === 'minute').value)
    );
  };
  const clock = stamp =>
    new Date(stamp).toLocaleTimeString('en-MY', {
      timeZone: 'Asia/Kuala_Lumpur',
      hour: 'numeric',
      minute: '2-digit',
    });
  const shortTeam = t => t.calendar_name.replace(/\s*\([^)]*\)/, '');
  const toolbar = el('div', undefined, 'booking-calendar-toolbar'),
    heading = el('div'),
    title = el('h2', 'Team calendar'),
    period = el('p', undefined, 'desk-muted');
  heading.append(title, period);
  const nav = el('div', undefined, 'booking-calendar-nav'),
    team = el('select');
  team.setAttribute('aria-label', 'Team shown in week view');
  data.teams
    .filter(t => t.active)
    .forEach(t => {
      const opt = el('option', shortTeam(t));
      opt.value = t.id;
      team.append(opt);
    });
  team.value = teamId;
  const mode = el('div', undefined, 'context-tabs');
  [
    ['day', 'Day, all teams'],
    ['week', 'Week, one team'],
  ].forEach(([key, label]) => {
    const b = deskButton(
      label,
      () => {
        view = key;
        render();
      },
      'quiet',
    );
    b.dataset.mode = key;
    mode.append(b);
  });
  function go(delta) {
    const day = addDays(selectedDate, delta);
    if (day < data.window_start || day > data.window_end) return;
    actions.onDate(day);
  }
  nav.append(
    deskButton('←', () => go(view === 'week' ? -7 : -1), 'quiet'),
    deskButton('Today', () => actions.onDate(dayOf(new Date().toISOString())), 'quiet'),
    deskButton('→', () => go(view === 'week' ? 7 : 1), 'quiet'),
    team,
    mode,
  );
  toolbar.append(heading, nav);
  const legend = el('div', undefined, 'booking-calendar-legend');
  [
    ['busy', 'Existing appointment / blocked'],
    ['suggestion', 'Suitable start'],
    ['backup', 'Cross-area / backup'],
    ['selected', 'Selected appointment'],
  ].forEach(([key, label]) => legend.append(el('span', label, 'calendar-key ' + key)));
  const hint = el(
    'p',
    'Select an appointment to inspect it. Check your requirements below to highlight suitable starts.',
    'desk-footnote',
  );
  const gridHost = el('div', undefined, 'booking-calendar-scroll'),
    detail = el('div', undefined, 'booking-calendar-detail');
  detail.setAttribute('aria-live', 'polite');
  host.append(toolbar, legend, hint, gridHost, detail);
  team.addEventListener('change', () => {
    teamId = team.value;
    render();
  });
  function inspect(item, isOption) {
    detail.replaceChildren(
      el('h3', isOption ? 'Suggested booking' : 'Calendar appointment'),
      el('p', isOption ? item.team : item.label),
      el('strong', dayOf(item.start) + ', ' + clock(item.start) + '–' + clock(item.end)),
    );
    if (isOption) {
      detail.append(
        el('p', item.reason + ', Travel allowance ' + item.travel_buffer_minutes + ' min.', 'desk-muted'),
        el(
          'p',
          'Check the live Calendar and route before confirming. This slot is not reserved.',
          'desk-footnote',
        ),
      );
      const copy = deskButton(
        'Copy option',
        async () => {
          try {
            await navigator.clipboard.writeText(
              [
                item.team,
                dayOf(item.start) + ' ' + clock(item.start) + '–' + clock(item.end),
                item.reason,
                'Travel allowance ' + item.travel_buffer_minutes + ' min; route unverified. Not reserved.',
              ].join('\n'),
            );
            copy.textContent = 'Copied';
          } catch {
            copy.textContent = 'Copy unavailable';
          }
        },
        'primary',
      );
      detail.append(copy);
    } else if (item.reschedulable && new Date(item.start) > new Date())
      detail.append(deskButton('Find a replacement slot', () => actions.onMove(item), 'primary'));
    const link = el('a', 'Open this day in Google Calendar', 'secondary');
    link.href = 'https://calendar.google.com/calendar/u/0/r/day/' + dayOf(item.start).replaceAll('-', '/');
    link.target = '_blank';
    link.rel = 'noopener';
    detail.append(link);
  }
  function render() {
    gridHost.replaceChildren();
    detail.replaceChildren();
    team.hidden = view !== 'week';
    mode
      .querySelectorAll('button')
      .forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === view)));
    const active = data.teams.filter(t => t.active),
      weekday = new Date(selectedDate + 'T12:00:00Z').getUTCDay(),
      monday = addDays(selectedDate, -((weekday + 6) % 7));
    const columns =
      view === 'day'
        ? active.map(t => ({ day: selectedDate, team: t }))
        : Array.from({ length: 7 }, (_, n) => ({
            day: addDays(monday, n),
            team: data.teams.find(t => t.id === teamId),
          }));
    period.textContent =
      view === 'day'
        ? new Date(selectedDate + 'T12:00:00Z').toLocaleDateString('en-MY', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric',
            timeZone: 'UTC',
          })
        : monday + ' to ' + addDays(monday, 6) + ', ' + shortTeam(columns[0].team);
    const grid = el('div', undefined, 'booking-calendar-grid');
    grid.style.setProperty('--calendar-columns', columns.length);
    const corner = el('div', 'MYT', 'booking-calendar-corner');
    grid.append(corner);
    columns.forEach(col => {
      const label =
        view === 'day'
          ? shortTeam(col.team)
          : new Date(col.day + 'T12:00:00Z').toLocaleDateString('en-MY', {
              weekday: 'short',
              day: 'numeric',
              month: 'short',
              timeZone: 'UTC',
            });
      const h = el('button', label, 'booking-calendar-column-head');
      h.type = 'button';
      h.disabled = col.day < data.window_start || col.day > data.window_end;
      if (view === 'week') h.addEventListener('click', () => actions.onDate(col.day));
      else h.disabled = true;
      grid.append(h);
    });
    const startHour = 7,
      endHour = 24,
      hourHeight = 80,
      height = (endHour - startHour) * hourHeight,
      timeCol = el('div', undefined, 'booking-calendar-times');
    timeCol.style.height = height + 'px';
    for (let hour = startHour; hour < endHour; hour++) {
      const tick = el('span', String(hour).padStart(2, '0') + ':00');
      tick.style.top = (hour - startHour) * hourHeight + 'px';
      timeCol.append(tick);
    }
    grid.append(timeCol);
    columns.forEach(col => {
      const lane = el('div', undefined, 'booking-calendar-lane');
      lane.style.height = height + 'px';
      if (col.day === selectedDate) lane.classList.add('current-day');
      const begin = new Date(col.day + 'T00:00:00+08:00'),
        finish = new Date(addDays(col.day, 1) + 'T00:00:00+08:00');
      if (col.day < data.window_start || col.day > data.window_end) {
        lane.classList.add('outside-window');
        lane.append(el('p', 'Outside captured period', 'desk-footnote'));
        grid.append(lane);
        return;
      }
      options
        .filter(o => o.team_id === col.team.id && dayOf(o.start) === col.day)
        .forEach(o => {
          const top = ((minute(o.start) - startHour * 60) * hourHeight) / 60;
          if (top < 0) return;
          const b = el(
            'button',
            clock(o.start),
            'booking-calendar-slot ' +
              (o.coverage === 'usual_area' || o.coverage === 'consultation' ? 'usual' : 'cover'),
          );
          b.type = 'button';
          b.style.top = top + 'px';
          b.title = clock(o.start) + '–' + clock(o.end) + ', ' + o.reason;
          b.setAttribute(
            'aria-label',
            'Suitable start ' + shortTeam(col.team) + ' ' + col.day + ' ' + clock(o.start),
          );
          b.addEventListener('click', () => inspect(o, true));
          lane.append(b);
        });
      const events = data.events
        .filter(e => e.team_id === col.team.id && new Date(e.start) < finish && new Date(e.end) > begin)
        .sort((a, b) => new Date(a.start) - new Date(b.start));
      const positioned = [];
      events.forEach(e => {
        const from = Math.max(startHour * 60, (new Date(e.start) - begin) / 60000),
          to = Math.min(endHour * 60, (new Date(e.end) - begin) / 60000);
        if (to <= from) return;
        let track = 0;
        while (positioned.some(p => p.track === track && from < p.to && to > p.from)) track++;
        positioned.push({ e, from, to, track });
      });
      const tracks = Math.max(1, ...positioned.map(p => p.track + 1));
      positioned.forEach(({ e, from, to, track }) => {
        const b = el('button', undefined, 'booking-calendar-event');
        b.type = 'button';
        b.style.top = ((from - startHour * 60) * hourHeight) / 60 + 'px';
        b.style.height = Math.max(22, ((to - from) * hourHeight) / 60 - 2) + 'px';
        b.style.left = (track / tracks) * 100 + '%';
        b.style.width = 100 / tracks + '%';
        b.append(el('strong', clock(e.start) + '–' + clock(e.end)), el('span', e.label));
        b.title = e.label + ', ' + clock(e.start) + '–' + clock(e.end);
        b.addEventListener('click', () => inspect(e, false));
        lane.append(b);
      });
      grid.append(lane);
    });
    gridHost.append(grid);
    gridHost.scrollTop = 2 * hourHeight;
    hint.textContent =
      data.status !== 'ready'
        ? 'Schedule is stale or incomplete. Availability suggestions are disabled.'
        : options.length
          ? 'Highlighted starts fit the checked requirements. Click one to inspect the full appointment.'
          : 'Existing bookings are shown. Check the requirements and teams below, then choose Find Calendar-fit options.';
  }
  render();
  return {
    update(day, next) {
      if (/^\d{4}-\d{2}-\d{2}$/.test(day)) selectedDate = day;
      options = next;
      render();
    },
  };
}
