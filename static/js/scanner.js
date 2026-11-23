(function () {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const statusEl = document.getElementById('camera-status');
  const resultEl = document.getElementById('scan-result');
  const historyEl = document.getElementById('scan-history');
  const modeButtons = document.querySelectorAll('.segmented button');
  const manualForm = document.getElementById('manual-form');
  const stationInput = document.getElementById('station-id');
  const imageInput = document.getElementById('qr-image');
  const technical = document.getElementById('technical-details');
  const technicalText = document.getElementById('technical-text');

  let mode = 'in';
  let scanning = true;
  let busy = false;

  stationInput.value = localStorage.getItem('station_id') || '';
  stationInput.addEventListener('change', () => localStorage.setItem('station_id', stationInput.value));

  function setStatus(label, kind) {
    statusEl.className = 'status-pill status-' + kind;
    statusEl.textContent = label;
  }

  function showTechnical(detail) {
    if (!detail) { technical.hidden = true; return; }
    technical.hidden = false;
    technicalText.textContent = detail;
  }

  function translateCameraError(err) {
    const name = err && err.name || '';
    const detail = name + ': ' + ((err && err.message) || 'Unknown camera error');
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return { message: 'Camera blocked. Allow camera access in browser settings, or use manual entry.', detail };
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return { message: 'No camera found. Use manual entry or upload a QR image.', detail };
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return { message: 'Camera is in use or unavailable. Close other apps, or use manual entry.', detail };
    }
    if (name === 'OverconstrainedError') {
      return { message: 'Camera does not support the requested settings. Use manual entry.', detail };
    }
    return { message: 'Camera unavailable. Check browser permissions or use manual entry.', detail };
  }

  function showResult(data) {
    if (data.status === 'processing') {
      resultEl.innerHTML = '<span class="status-pill status-info">Processing scan…</span>';
      return;
    }
    const ok = data.status === 'ok';
    const warning = ['duplicate', 'already_checked_out', 'outside_window', 'not_checked_in', 'replayed'].includes(data.status);
    const kind = ok ? 'status-success' : warning ? 'status-warning' : 'status-error';
    const title = ok
      ? (data.direction === 'out' ? 'Checked out' : 'Checked in')
      : (data.message || 'Scan failed');
    resultEl.innerHTML =
      '<span class="status-pill ' + kind + '">' + escapeHtml(title) + '</span>' +
      (data.fullname ? '<h3 style="margin-top:12px">' + escapeHtml(data.fullname) + '</h3>' : '') +
      '<p class="meta">' +
        (data.student_id ? escapeHtml(data.student_id) + ' · ' : '') +
        (data.program && data.year ? escapeHtml(data.program) + ' ' + data.year + '-' + escapeHtml(data.section || '') + ' · ' : '') +
        (data.time ? '<span class="time">' + escapeHtml(data.time) + '</span>' : '') +
      '</p>';
    showTechnical(data.detail);

    const li = document.createElement('li');
    li.innerHTML =
      '<span class="status-pill ' + kind + '">' + (ok ? (data.direction === 'out' ? 'Out' : 'In') : '!') + '</span> ' +
      escapeHtml(data.fullname || data.student_id || 'Failed scan') +
      ' <span class="time">' + new Date().toLocaleTimeString() + '</span>';
    if (historyEl.querySelector('.empty-state')) historyEl.innerHTML = '';
    historyEl.insertBefore(li, historyEl.firstChild);

    setTimeout(() => {
      scanning = true;
      busy = false;
    }, 1800);
  }

  function escapeHtml(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[c]);
  }

  async function submitScan(body) {
    busy = true;
    scanning = false;
    showResult({ status: 'processing', message: 'Processing scan…' });
    try {
      const response = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode,
          station_id: stationInput.value || null,
          client_scan_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()),
          ...body
        })
      });
      showResult(await response.json());
    } catch (err) {
      showResult({ status: 'offline', message: 'Could not reach the server. Check your connection.', detail: String(err) });
      scanning = true;
      busy = false;
    }
  }

  function decodeCode() {
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
    canvas.height = video.videoHeight;
    canvas.width = video.videoWidth;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: 'dontInvert' });
    if (code && scanning && !busy) submitScan({ text: code.data });
  }

  function tick() {
    decodeCode();
    requestAnimationFrame(tick);
  }

  modeButtons.forEach(button => {
    button.addEventListener('click', () => {
      mode = button.dataset.mode;
      modeButtons.forEach(b => b.classList.toggle('active', b === button));
      manualForm.querySelector('button[type=submit]').textContent = 'Record ' + (mode === 'in' ? 'check-in' : 'check-out');
    });
  });

  manualForm.addEventListener('submit', event => {
    event.preventDefault();
    const studentId = document.getElementById('student-id').value.trim();
    if (!studentId) return;
    submitScan({ student_id: studentId });
    document.getElementById('student-id').value = '';
  });

  imageInput.addEventListener('change', async event => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      canvas.width = image.width;
      canvas.height = image.height;
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      const data = context.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(data.data, data.width, data.height, { inversionAttempts: 'attemptBoth' });
      URL.revokeObjectURL(url);
      if (code) submitScan({ text: code.data });
      else showResult({ status: 'invalid_qr', message: 'No QR code found in that image.' });
    };
    image.src = url;
  });

  setStatus('Starting camera', 'warning');
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then(stream => {
        video.srcObject = stream;
        setStatus('Ready', 'success');
        requestAnimationFrame(tick);
      })
      .catch(err => {
        const error = translateCameraError(err);
        setStatus('Camera blocked', 'error');
        showResult({ status: 'camera_error', message: error.message, detail: error.detail });
      });
  } else {
    const error = translateCameraError({ name: 'NotFoundError', message: 'getUserMedia unavailable' });
    setStatus('Camera unavailable', 'error');
    showResult({ status: 'camera_error', message: error.message, detail: error.detail });
  }
})();
