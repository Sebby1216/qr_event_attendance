(function () {
  const params = new URLSearchParams(window.location.search);
  const message = params.get('msg');
  const type = params.get('type') || 'info';
  if (message) {
    const target = document.querySelector('.content');
    if (target) {
      const notice = document.createElement('div');
      const kind = /^(success|error|warning)$/.test(type) ? type : 'info';
      notice.className = 'notice notice-' + kind;
      notice.textContent = message;
      target.insertBefore(notice, target.firstChild);
    }
  }
})();

function confirmAction(message, action) {
  if (window.confirm(message)) action();
}
