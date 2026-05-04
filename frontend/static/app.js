let lastRequest = null;
let lastPlan = null;
let importedCalendarEvents = [];

const $ = (id) => document.getElementById(id);

function setStatus(text, cls = '') {
  const el = $('status');
  el.textContent = text;
  el.className = 'status ' + cls;
}

function todayIso() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

function plusDaysIso(baseIso, days) {
  const d = new Date(`${baseIso || todayIso()}T12:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

$('currentDate').value = todayIso();

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${text}`);
  }
  return await res.json();
}

function rawInput() {
  return {
    current_date: $('currentDate').value || todayIso(),
    work_style: $('workStyle')?.value || 'balanced',
    fixed_events_text: [$('fixedEvents').value, importedCalendarEvents.join('\n')].filter(Boolean).join('\n'),
    availability_text: $('availability').value,
    tasks_text: $('tasks').value,
    assignment_details_text: $('assignmentDetails') ? $('assignmentDetails').value : '',
    preference_text: $('preferences').value,
    horizon_days: 10,
  };
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>'"]/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[c]));
}

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
}

function fmtDateLabel(dayIso) {
  const d = new Date(`${dayIso}T12:00:00`);
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function taskTypeClass(taskType) {
  return String(taskType || 'other').replace(/[^a-zA-Z0-9_-]/g, '_');
}

function taskTypeLabel(taskType) {
  return String(taskType || 'other').replace(/_/g, ' ');
}

function blockDurationText(block) {
  if (block.minutes) return minutesText(block.minutes);
  const start = new Date(block.start);
  const end = new Date(block.end);
  return minutesText((end - start) / 60000);
}

function renderSchedule(blocks) {
  const container = $('schedule');
  if (!blocks || !blocks.length) {
    container.innerHTML = '<p>No scheduled blocks.</p>';
    return;
  }
  const byDay = {};
  for (const b of blocks) {
    const day = b.start.slice(0, 10);
    if (!byDay[day]) byDay[day] = [];
    byDay[day].push(b);
  }
  container.innerHTML = Object.entries(byDay).sort().map(([day, items]) => {
    const sorted = items.slice().sort((a, b) => a.start.localeCompare(b.start));
    const total = sorted.reduce((sum, b) => sum + (b.minutes || 0), 0);
    const rows = sorted.map(b => {
      const cls = taskTypeClass(b.task_type);
      return `<div class="schedule-block ${cls}">
        <div class="time-pill">
          <strong>${fmtTime(b.start)}–${fmtTime(b.end)}</strong>
          <span>${blockDurationText(b)}</span>
        </div>
        <div class="block-main">
          <strong>${escapeHtml(b.task_title)}</strong>
          ${b.note ? `<span class="block-note">${escapeHtml(b.note)}</span>` : ''}
        </div>
        <span class="badge ${cls}">${escapeHtml(taskTypeLabel(b.task_type))}</span>
      </div>`;
    }).join('');
    return `<div class="day">
      <h4><span>${escapeHtml(fmtDateLabel(day))}</span><small>${escapeHtml(day)} · ${minutesText(total)}</small></h4>
      ${rows}
    </div>`;
  }).join('');
}

function renderParsed(parsed) {
  if (!parsed || !parsed.tasks) {
    $('parsed').innerHTML = '';
    return;
  }
  const rows = parsed.tasks.map(t => {
    const subtasks = (t.subtasks || []).map(s => s.title).join(' → ');
    return `<tr>
      <td>${escapeHtml(t.title)}${subtasks ? `<div class="subtasks">${escapeHtml(subtasks)}</div>` : ''}</td>
      <td>${escapeHtml(t.task_type)}</td>
      <td>${Math.round(t.estimated_minutes / 60 * 10) / 10}h${t.estimate_source === 'system' ? `<div class="subtasks">system est., ${escapeHtml(t.estimate_confidence || 'unknown')} confidence</div>` : ''}</td>
      <td>${escapeHtml(t.deadline.replace('T', ' ').slice(0, 16))}</td>
      <td>${escapeHtml(t.priority)}</td>
    </tr>`;
  }).join('');
  $('parsed').innerHTML = `<div class="table-wrap"><table>
    <thead><tr><th>Task</th><th>Type</th><th>Est.</th><th>Deadline</th><th>Priority</th></tr></thead>
    <tbody>${rows}</tbody>
  </table></div>`;
}

function renderList(id, items, cls = 'info-item') {
  const el = $(id);
  if (!el) return;
  if (!items || !items.length) {
    el.innerHTML = '<p class="muted">None.</p>';
    return;
  }
  el.innerHTML = items.map(x => `<div class="${cls}">${escapeHtml(x)}</div>`).join('');
}

function renderRisks(response) {
  const risks = [];
  if (response.risk_warnings) risks.push(...response.risk_warnings);
  if (response.unscheduled) {
    for (const u of response.unscheduled) {
      risks.push(`${u.task_title}: ${u.remaining_minutes} minutes unscheduled. ${u.reason}`);
    }
  }
  $('risks').innerHTML = risks.length
    ? `<h3>Risk warnings</h3>${risks.map(r => `<div class="risk">${escapeHtml(r)}</div>`).join('')}`
    : '';
}

function minutesText(minutes) {
  minutes = Math.max(0, Math.round(minutes || 0));
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h && m) return `${h}h ${m}m`;
  if (h) return `${h}h`;
  return `${m}m`;
}

function renderGlance(payload) {
  const response = payload.response || payload;
  const schedule = response.schedule || [];
  const scheduledMinutes = schedule.reduce((sum, b) => sum + (b.minutes || 0), 0);
  const unscheduledMinutes = (response.unscheduled || []).reduce((sum, u) => sum + (u.remaining_minutes || 0), 0);
  const days = new Set(schedule.map(b => (b.start || '').slice(0, 10))).size;
  const firstBlock = schedule.length ? schedule.slice().sort((a, b) => a.start.localeCompare(b.start))[0] : null;
  const planStatus = unscheduledMinutes ? 'Warnings' : (response.validation?.valid ? 'Ready' : 'Review');
  const firstText = firstBlock ? `${firstBlock.task_title} · ${firstBlock.start.slice(0, 10)} ${fmtTime(firstBlock.start)}` : 'No block scheduled';
  $('glance').innerHTML = `
    <div class="glance-card"><span>Plan status</span><strong>${escapeHtml(planStatus)}</strong></div>
    <div class="glance-card"><span>Scheduled</span><strong>${minutesText(scheduledMinutes)}</strong></div>
    <div class="glance-card"><span>Unscheduled</span><strong>${minutesText(unscheduledMinutes)}</strong></div>
    <div class="glance-card"><span>Days planned</span><strong>${days}</strong></div>
    <div class="glance-card wide"><span>First recommended block</span><strong>${escapeHtml(firstText)}</strong></div>`;
}

function renderNextSteps(payload) {
  const response = payload.response || payload;
  const steps = [];
  const schedule = response.schedule || [];
  const unscheduledMinutes = (response.unscheduled || []).reduce((sum, u) => sum + (u.remaining_minutes || 0), 0);
  const systemEstimates = (payload.parsed?.tasks || []).filter(t => t.estimate_source === 'system');
  if (schedule.length) {
    const first = schedule.slice().sort((a, b) => a.start.localeCompare(b.start))[0];
    steps.push(`Start with ${first.task_title} at ${first.start.slice(0, 10)} ${fmtTime(first.start)}.`);
  }
  if (unscheduledMinutes) {
    steps.push(`Add ${minutesText(unscheduledMinutes)} of availability, reduce scope, or relax block-size constraints to fully schedule remaining work.`);
  }
  if (systemEstimates.length) {
    steps.push(`Review ${systemEstimates.length} system effort estimate(s); replacing them with your own estimates will make the plan more reliable.`);
  }
  if (response.risk_warnings?.length) {
    steps.push('Check the risk warnings before relying on this plan for a deadline-heavy week.');
  }
  $('nextSteps').innerHTML = steps.length
    ? `<h3>Recommended next steps</h3>${steps.map(s => `<div class="next-step">${escapeHtml(s)}</div>`).join('')}`
    : '';
}

function renderPlan(payload) {
  const response = payload.response || payload;
  $('summary').textContent = response.summary || 'Schedule generated.';
  renderGlance(payload);
  renderNextSteps(payload);
  renderList('replanChanges', response.replan_changes || [], 'change');
  renderList('rationale', response.rationale || payload.explanation?.rationale || [], 'info-item');
  renderList('validationSummary', response.validation_summary || [], 'check-item');
  const assumptionItems = [];
  if (payload.parsed?.assumptions?.length) assumptionItems.push(...payload.parsed.assumptions);
  if (payload.parsed?.clarification_questions?.length) assumptionItems.push(...payload.parsed.clarification_questions.map(q => `Clarification: ${q}`));
  $('assumptions').innerHTML = assumptionItems.length
    ? `<h3>Planning assumptions</h3>${assumptionItems.map(a => `<div class="assumption">${escapeHtml(a)}</div>`).join('')}`
    : '';
  renderRisks(response);
  renderSchedule(response.schedule || []);
  renderParsed(payload.parsed);
  $('debug').textContent = JSON.stringify({
    validation: response.validation,
    objective_score: response.objective_score,
    parser_mode: payload.parsed?.parser_mode,
    assumptions: payload.parsed?.assumptions,
    clarification_questions: payload.parsed?.clarification_questions,
    day_summaries: response.day_summaries,
  }, null, 2);
}


function unfoldIcs(text) {
  const raw = text.replace(/\r\n/g, '\n').split('\n');
  const lines = [];
  for (const line of raw) {
    if ((line.startsWith(' ') || line.startsWith('\t')) && lines.length) {
      lines[lines.length - 1] += line.slice(1);
    } else {
      lines.push(line.trimEnd());
    }
  }
  return lines;
}

function parseIcsDate(value) {
  const clean = String(value || '').split(':').pop().replace(/Z$/, '');
  const m = clean.match(/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2}))?/);
  if (!m) return null;
  return {
    date: `${m[1]}-${m[2]}-${m[3]}`,
    time: m[4] ? `${m[4]}:${m[5]}` : '00:00',
  };
}

function parseIcsFile(text) {
  const lines = unfoldIcs(text);
  const events = [];
  let cur = null;
  for (const line of lines) {
    if (line === 'BEGIN:VEVENT') cur = {};
    else if (line === 'END:VEVENT' && cur) {
      if (cur.summary && cur.start && cur.end) {
        events.push(`${cur.start.date} ${cur.start.time}-${cur.end.time} ${cur.summary}`);
      }
      cur = null;
    } else if (cur) {
      if (line.startsWith('SUMMARY')) cur.summary = line.split(':').slice(1).join(':').replace(/\\,/g, ',');
      if (line.startsWith('DTSTART')) cur.start = parseIcsDate(line);
      if (line.startsWith('DTEND')) cur.end = parseIcsDate(line);
    }
  }
  return events;
}


function autoGrowTextarea(el) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = `${Math.min(el.scrollHeight + 4, 360)}px`;
}

function renderImportedEventsPreview() {
  const preview = $('calendarImportPreview');
  if (!preview) return;
  if (!importedCalendarEvents.length) {
    preview.innerHTML = '';
    return;
  }
  preview.innerHTML = `<strong>Imported fixed events</strong>${importedCalendarEvents.map(e => `<span>${escapeHtml(e)}</span>`).join('')}`;
}

function applyImportedEvents(events, statusText) {
  importedCalendarEvents = events.slice(0, 80);
  const existing = $('fixedEvents').value.trim();
  const marker = '# Imported calendar events are shown below and included automatically.';
  if (importedCalendarEvents.length && !existing.includes(marker)) {
    $('fixedEvents').value = `${existing}${existing ? '\n' : ''}${marker}`;
    autoGrowTextarea($('fixedEvents'));
  }
  $('calendarImportStatus').textContent = statusText || (importedCalendarEvents.length ? `Imported ${importedCalendarEvents.length} calendar event(s). They are included as fixed events when generating a schedule.` : '');
  renderImportedEventsPreview();
}

const calendarInput = $('calendarFile');
if (calendarInput) {
  calendarInput.addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const text = await file.text();
    const events = parseIcsFile(text).slice(0, 80);
    if (!events.length) {
      $('calendarImportStatus').textContent = 'No VEVENT entries with start/end times were found.';
      importedCalendarEvents = [];
      renderImportedEventsPreview();
      return;
    }
    applyImportedEvents(events, `Imported ${events.length} calendar event(s). They are included as fixed events when generating a schedule.`);
  });
}

for (const id of ['fixedEvents', 'availability', 'tasks', 'assignmentDetails', 'preferences', 'progress']) {
  const el = $(id);
  if (el) el.addEventListener('input', () => autoGrowTextarea(el));
}

async function loadDemo(stage = 'details') {
  setStatus('Loading demo...', 'busy');
  try {
    const sample = await api(`/api/v1/sample?stage=${encodeURIComponent(stage)}`);
    importedCalendarEvents = [];
    renderImportedEventsPreview();
    $('calendarImportStatus').textContent = '';
    if ($('calendarFile')) $('calendarFile').value = '';
    $('currentDate').value = sample.current_date;
    $('fixedEvents').value = sample.fixed_events_text || '';
    autoGrowTextarea($('fixedEvents'));
    $('availability').value = sample.availability_text || '';
    autoGrowTextarea($('availability'));
    $('tasks').value = sample.tasks_text || '';
    autoGrowTextarea($('tasks'));
    if ($('assignmentDetails')) {
      $('assignmentDetails').value = sample.assignment_details_text || '';
      autoGrowTextarea($('assignmentDetails'));
    }
    $('preferences').value = sample.preference_text || '';
    autoGrowTextarea($('preferences'));
    if ($('workStyle')) $('workStyle').value = sample.work_style || 'balanced';
    setStatus(stage === 'basic' ? 'Basic demo loaded' : 'Detailed demo loaded', 'ok');
  } catch (err) {
    setStatus('Error loading demo', 'error');
    $('debug').textContent = err.message;
  }
}

$('loadSample').addEventListener('click', () => loadDemo('details'));
const basicDemoButton = $('loadBasicDemo');
if (basicDemoButton) basicDemoButton.addEventListener('click', () => loadDemo('basic'));
const detailedDemoButton = $('loadDetailedDemo');
if (detailedDemoButton) detailedDemoButton.addEventListener('click', () => loadDemo('details'));
const calendarDemoButton = $('addCalendarBlockers');
if (calendarDemoButton) {
  calendarDemoButton.addEventListener('click', () => {
    const base = $('currentDate').value || todayIso();
    const d1 = plusDaysIso(base, 1);
    const d2 = plusDaysIso(base, 2);
    const events = [
      `${d1} 19:00-20:00 Project meeting`,
      `${d2} 19:30-20:30 Office hour`,
    ];
    applyImportedEvents(events, `Added ${events.length} demo calendar blocker(s). They are included as fixed events when generating a schedule.`);
    setStatus('Calendar blockers added', 'ok');
  });
}

async function generateSchedule() {
  setStatus('Planning...', 'busy');
  try {
    const payload = await api('/api/v1/plan', {
      method: 'POST',
      body: JSON.stringify(rawInput()),
    });
    lastPlan = payload;
    lastRequest = payload.request;
    renderPlan(payload);
    setStatus('Schedule generated', 'ok');
  } catch (err) {
    setStatus('Planning failed', 'error');
    $('debug').textContent = err.stack || err.message;
  }
}

async function replanFromProgress() {
  if (!lastRequest) {
    setStatus('Generate a schedule first', 'error');
    return;
  }
  if (!$('progress').value.trim()) {
    renderList('replanChanges', ['No progress update was provided. Describe what was completed or missed, then click Replan again.'], 'change');
    setStatus('Progress update needed', 'error');
    return;
  }
  setStatus('Replanning...', 'busy');
  try {
    const payload = await api('/api/v1/replan', {
      method: 'POST',
      body: JSON.stringify({
        original_request: lastRequest,
        progress_text: $('progress').value,
        progress_updates: [],
      }),
    });
    renderPlan(payload);
    lastPlan = { response: payload, request: lastRequest };
    setStatus('Replanned', 'ok');
  } catch (err) {
    setStatus('Replan failed', 'error');
    $('debug').textContent = err.stack || err.message;
  }
}

async function runEvaluation() {
  setStatus('Running evaluation...', 'busy');
  try {
    const payload = await api('/api/v1/evaluate');
    $('summary').textContent = 'Evaluation complete: PlanPilot compared against simple scheduling baselines.';
    const agg = payload.aggregate || {};
    const pp = agg.planpilot || {};
    const edd = agg.earliest_deadline || {};
    const naive = agg.naive_equal_split || {};
    $('glance').innerHTML = `
      <div class="glance-card"><span>PlanPilot score</span><strong>${escapeHtml(pp.avg_objective_score ?? 'n/a')}</strong></div>
      <div class="glance-card"><span>EDD baseline</span><strong>${escapeHtml(edd.avg_objective_score ?? 'n/a')}</strong></div>
      <div class="glance-card"><span>Equal-split baseline</span><strong>${escapeHtml(naive.avg_objective_score ?? 'n/a')}</strong></div>
      <div class="glance-card"><span>Conflict count</span><strong>${escapeHtml(pp.total_calendar_conflicts ?? 'n/a')}</strong></div>
      <div class="glance-card wide"><span>Eval set</span><strong>${escapeHtml(pp.cases ?? 0)} synthetic scheduling scenarios with deadline, calendar, and dependency constraints</strong></div>`;
    $('nextSteps').innerHTML = '<h3>Evaluation takeaway</h3><div class="next-step">PlanPilot is checked with repeatable tests, not only visual inspection.</div><div class="next-step">The objective score rewards feasible schedules, dependency order, and preference-aware placement.</div>';
    $('schedule').innerHTML = '';
    $('parsed').innerHTML = '';
    $('risks').innerHTML = '';
    if ($('assumptions')) $('assumptions').innerHTML = '';
    renderList('rationale', ['Evaluation follows the course idea of converting product requirements into tests.', 'Baselines are earliest-deadline-first and naive equal split.'], 'info-item');
    renderList('validationSummary', ['✅ Evaluation run completed', `✅ PlanPilot score: ${pp.avg_objective_score ?? 'n/a'}`, `✅ Calendar conflicts: ${pp.total_calendar_conflicts ?? 'n/a'}`, `✅ Deadline violations: ${pp.total_deadline_violations ?? 'n/a'}`], 'check-item');
    renderList('replanChanges', [], 'change');
    $('debug').textContent = JSON.stringify(payload.aggregate, null, 2);
    setStatus('Evaluation complete', 'ok');
  } catch (err) {
    setStatus('Evaluation failed', 'error');
    $('debug').textContent = err.stack || err.message;
  }
}

window.generateSchedule = generateSchedule;
window.replanFromProgress = replanFromProgress;
window.runEvaluation = runEvaluation;

const generateButton = $('generate');
if (generateButton) generateButton.addEventListener('click', generateSchedule);
const replanButton = $('replan');
if (replanButton) replanButton.addEventListener('click', replanFromProgress);
const runEvalButton = $('runEval');
if (runEvalButton) runEvalButton.addEventListener('click', runEvaluation);

// Start blank: placeholders show what to enter. Use the example buttons to preload scenarios.
setStatus('Idle', '');
