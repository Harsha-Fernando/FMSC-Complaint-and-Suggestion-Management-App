/* Independent enhancements for the shared workspace. */
(() => {
  'use strict';
  const gettext = window.gettext || (text => text);
  document.documentElement.classList.add('js');
  const toggle = document.querySelector('.mobile-menu');
  const sidebar = document.querySelector('.sidebar');
  const narrow = window.matchMedia('(max-width: 760px)');
  const closeNav = () => {
    sidebar?.classList.remove('is-open');
    document.body.classList.remove('navigation-collapsed');
    toggle?.setAttribute('aria-expanded', String(!narrow.matches));
  };
  toggle?.setAttribute('aria-expanded', String(!narrow.matches));
  narrow.addEventListener('change', closeNav);
  toggle?.addEventListener('click', () => {
    if (narrow.matches) {
      const open = sidebar.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
      if (open) sidebar.querySelector('.nav a')?.focus();
    } else {
      const collapsed = document.body.classList.toggle('navigation-collapsed');
      toggle.setAttribute('aria-expanded', String(!collapsed));
    }
  });
  const account = document.querySelector('.account-menu');
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      if (sidebar?.classList.contains('is-open')) { closeNav(); toggle.focus(); }
      if (account?.open) { account.open = false; account.querySelector('summary').focus(); }
    }
  });
  document.addEventListener('click', event => { if (account && !account.contains(event.target)) account.open = false; });
  // Server-side validation remains authoritative; move focus to its first error.
  const error = document.querySelector('.has-error input, .has-error textarea, .has-error .select-trigger, .has-error select, .form-errors');
  if (error) { if (!error.matches('input, textarea, button, select')) error.tabIndex = -1; error.focus(); }
  const link = document.querySelector('[data-notification-summary]');
  if (link) {
    let busy = false;
    const refresh = async () => {
      if (document.hidden || busy) return;
      busy = true;
      try {
        const response = await fetch(link.dataset.notificationSummary, {headers: {'Accept': 'application/json'}, credentials: 'same-origin', cache: 'no-store'});
        if (!response.ok || response.redirected) return;
        const data = await response.json();
        const count = Number(data.unread_count);
        if (!Number.isFinite(count)) return;
        link.setAttribute('aria-label', count ? interpolate(gettext('Notifications, %(count)s unread'), {count}, true) : gettext('Notifications'));
        const dot = link.querySelector('.notification-dot');
        if (count) {
          const mark = dot || document.createElement('span');
          mark.className = 'notification-dot';
          mark.setAttribute('aria-hidden', 'true');
          mark.textContent = count > 99 ? '99+' : String(count);
          if (!dot) link.append(mark);
        } else dot?.remove();
        const notice = document.querySelector('[data-new-notifications]');
        if (notice && count > Number(notice.dataset.initialUnread)) notice.hidden = false;
      } catch { /* Keep the last known count during connection loss. */ }
      finally { busy = false; }
    };
    window.clearInterval(window.__fmscNotificationTimer);
    window.__fmscNotificationTimer = window.setInterval(refresh, 30000);
    document.addEventListener('visibilitychange', refresh);
    window.addEventListener('focus', refresh);
  }
})();
