(function () {
  const container = document.getElementById('attendance');
  const search = document.getElementById('search');
  const sectionFilter = document.getElementById('section-filter');
  const statusFilter = document.getElementById('status-filter');
  const lastUpdated = document.getElementById('last-updated');
  const wsStatus = document.getElementById('ws-status');
  const canManage = document.getElementById('live-config').dataset.canManage === 'true';
  let needsRefresh = false;

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  function correctionControls(student) {
    if (!canManage) return '';
    return '<span class="no-print" style="display:inline-flex;gap:4px">' +
      '<input type="datetime-local" data-record="' + student.id + '" value="" aria-label="Correct time">' +
      '<button class="btn btn-sm" type="button" data-record="' + student.id + '" data-action="checkin_time">Set in</button>' +
      '<button class="btn btn-sm" type="button" data-record="' + student.id + '" data-action="checkout_time">Set out</button>' +
      '<button class="btn btn-sm btn-danger" type="button" data-record="' + student.id + '" data-action="delete">Delete</button>' +
      '</span>';
  }

  async function refresh() {
    const params = new URLSearchParams({
      search: search.value.trim(),
      section: sectionFilter.value,
      status: statusFilter.value
    });
    try {
      const response = await fetch('/api/attendance?' + params.toString());
      const data = await response.json();
      let total = 0, inside = 0, out = 0;
      data.forEach(year => { total += year.total; });
      data.forEach(year => year.programs.forEach(program => program.sections.forEach(section => section.students.forEach(student => {
        student.inside ? inside++ : out++;
      }))));
      document.getElementById('kpi-total').textContent = total;
      document.getElementById('kpi-inside').textContent = inside;
      document.getElementById('kpi-out').textContent = out;

      if (!total) {
        container.innerHTML = '<p class="empty-state">No scans yet. Start scanning to see attendance activity here.</p>';
      } else {
        container.innerHTML = data.map(year =>
          '<div class="year-section"><h2>Year ' + escapeHtml(year.year) + ' <span class="meta">(' + year.total + ')</span></h2>' +
          year.programs.map(program =>
            '<div class="program-section"><h3>' + escapeHtml(program.program) + ' <span class="meta">(' + program.total + ')</span></h3>' +
            program.sections.map(section =>
              '<div class="section-group"><h4>Section ' + escapeHtml(section.section) + ' <span class="meta">(' + section.total + ')</span></h4>' +
              '<ul>' + section.students.map(student =>
                '<li><span class="status-pill ' + (student.inside ? 'status-success' : 'status-info') + '">' + (student.inside ? 'In' : 'Out') + '</span>' +
                ' <span class="who">' + escapeHtml(student.student_id) + ' · ' + escapeHtml(student.last_name) + ', ' + escapeHtml(student.first_name) + '</span>' +
                ' <span class="meta">' + escapeHtml(student.checkin_time) + ' → ' + escapeHtml(student.checkout_time || '—') + '</span>' +
                ' ' + correctionControls(student) + '</li>'
              ).join('') + '</ul></div>'
            ).join('') + '</div>'
          ).join('') + '</div>'
        ).join('');
      }
      lastUpdated.textContent = new Date().toLocaleTimeString();
    } catch (err) {
      container.innerHTML = '<p class="empty-state">Could not load attendance. Retrying…</p>';
    }
  }

  [search, sectionFilter, statusFilter].forEach(el => {
    el.addEventListener('input', () => { needsRefresh = false; refresh(); });
  });

  container.addEventListener('click', async event => {
    const button = event.target.closest('button[data-action]');
    if (!button) return;
    const recordId = button.dataset.record;
    const action = button.dataset.action;
    const input = container.querySelector('input[data-record="' + recordId + '"]');
    let value = null;
    if (action !== 'delete') {
      if (!input || !input.value) { alert('Enter a corrected time first.'); return; }
      value = new Date(input.value).toISOString();
    }
    if (action === 'delete' && !confirm('Delete this attendance record?')) return;
    await fetch('/attendance/' + recordId + '/correction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, value })
    });
    refresh();
  });

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(protocol + '//' + location.host + '/ws/dashboard');
    socket.onopen = () => { wsStatus.textContent = 'Live'; wsStatus.style.color = 'var(--success)'; };
    socket.onmessage = () => { needsRefresh = true; };
    socket.onclose = () => {
      wsStatus.textContent = 'Reconnecting';
      wsStatus.style.color = 'var(--warning)';
      setTimeout(connect, 3000);
    };
  }

  refresh();
  connect();
  setInterval(() => { if (needsRefresh) { needsRefresh = false; refresh(); } }, 1000);
})();
