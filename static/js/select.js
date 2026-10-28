/* Accessible select-only combobox. The server-rendered select remains the source
   of truth and the complete fallback when JavaScript is unavailable. */
(() => {
  'use strict';
  const gettext = window.gettext || (text => text);
  let opened = null;
  let sequence = 0;
  document.querySelectorAll('select:not([multiple]):not([size])').forEach(select => {
    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';
    select.before(wrapper);
    wrapper.append(select);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'select-trigger';
    button.id = `${select.id || 'select'}-trigger-${++sequence}`;
    button.setAttribute('role', 'combobox');
    button.setAttribute('aria-haspopup', 'listbox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-autocomplete', 'none');
    const value = document.createElement('span');
    const arrow = document.createElement('span');
    arrow.className = 'select-arrow';
    arrow.setAttribute('aria-hidden', 'true');
    button.append(value, arrow);
    const list = document.createElement('div');
    list.id = `${button.id}-list`;
    list.className = 'select-list';
    list.setAttribute('role', 'listbox');
    // Keep focus on the combobox until an option click commits selection.
    // Otherwise focusout hides the list between pointerdown and click.
    list.addEventListener('pointerdown', event => event.preventDefault());
    list.hidden = true;
    button.setAttribute('aria-controls', list.id);
    const labels = [...select.labels];
    labels.forEach((label, i) => {
      if (!label.id) label.id = `${button.id}-label-${i}`;
      label.htmlFor = button.id;
    });
    const labelIds = labels.map(label => label.id).join(' ');
    if (labelIds) {
      button.setAttribute('aria-labelledby', labelIds);
      list.setAttribute('aria-labelledby', labelIds);
    } else button.setAttribute('aria-label', select.getAttribute('aria-label') || select.name);
    ['aria-describedby', 'aria-invalid', 'aria-required'].forEach(name => {
      if (select.hasAttribute(name)) button.setAttribute(name, select.getAttribute(name));
    });
    if (select.required) button.setAttribute('aria-required', 'true');
    select.classList.add('select-native');
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    wrapper.append(button, list);
    let active = -1;
    let options = [];
    let search = '';
    let lastKey = 0;
    const enabled = index => index >= 0 && index < select.options.length && !select.options[index].disabled && !select.options[index].parentElement.disabled;
    const close = () => {
      list.hidden = true;
      button.setAttribute('aria-expanded', 'false');
      button.removeAttribute('aria-activedescendant');
      if (opened === close) opened = null;
    };
    const highlight = index => {
      if (!enabled(index)) return;
      active = index;
      options.forEach((option, i) => option.classList.toggle('is-active', i === active));
      button.setAttribute('aria-activedescendant', options[active].id);
      options[active].scrollIntoView({block: 'nearest'});
    };
    const sync = () => {
      value.textContent = select.selectedOptions[0]?.textContent || gettext('Choose an option');
      button.disabled = select.disabled;
      options.forEach((option, i) => option.setAttribute('aria-selected', String(i === select.selectedIndex)));
    };
    const choose = index => {
      if (!enabled(index)) return;
      select.selectedIndex = index;
      sync();
      select.dispatchEvent(new Event('change', {bubbles: true}));
      close();
      button.focus();
    };
    const render = () => {
      list.replaceChildren();
      options = [...select.options].map((option, i) => {
        const item = document.createElement('div');
        item.id = `${list.id}-${i}`;
        item.className = 'select-option';
        item.setAttribute('role', 'option');
        item.setAttribute('aria-disabled', String(!enabled(i)));
        item.textContent = option.textContent;
        item.addEventListener('click', () => choose(i));
        item.addEventListener('pointermove', () => highlight(i));
        list.append(item);
        return item;
      });
      sync();
    };
    const open = () => {
      if (select.disabled) return;
      if (opened && opened !== close) opened();
      list.hidden = false;
      button.setAttribute('aria-expanded', 'true');
      const space = window.innerHeight - button.getBoundingClientRect().bottom;
      list.classList.toggle('above', space < 260 && button.getBoundingClientRect().top > space);
      opened = close;
      const first = [...select.options].findIndex((_, i) => enabled(i));
      highlight(enabled(select.selectedIndex) ? select.selectedIndex : first);
    };
    button.addEventListener('click', () => list.hidden ? open() : close());
    button.addEventListener('keydown', event => {
      const key = event.key;
      if (key === 'Tab') { close(); return; }
      if (key === 'Escape') { if (!list.hidden) event.preventDefault(); close(); return; }
      if (key === 'Enter' || key === ' ') {
        event.preventDefault();
        if (list.hidden) open(); else choose(active);
        return;
      }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(key)) {
        event.preventDefault();
        if (list.hidden) { open(); if (!['Home', 'End'].includes(key)) return; }
        const step = key === 'ArrowUp' || key === 'End' ? -1 : 1;
        let index = key === 'Home' ? 0 : key === 'End' ? options.length - 1 : active + step;
        while (index >= 0 && index < options.length) {
          if (enabled(index)) { highlight(index); break; }
          index += step;
        }
        return;
      }
      if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        if (list.hidden) open();
        const now = Date.now();
        search = (now - lastKey > 700 ? '' : search) + key.toLowerCase();
        lastKey = now;
        const match = [...select.options].findIndex((option, i) => enabled(i) && option.textContent.trim().toLowerCase().startsWith(search));
        if (match >= 0) highlight(match);
      }
    });
    wrapper.addEventListener('focusout', event => { if (!wrapper.contains(event.relatedTarget)) close(); });
    document.addEventListener('pointerdown', event => { if (!wrapper.contains(event.target)) close(); });
    select.addEventListener('change', sync);
    select.addEventListener('invalid', event => { event.preventDefault(); button.setAttribute('aria-invalid', 'true'); button.focus(); });
    select.form?.addEventListener('reset', () => { close(); setTimeout(sync, 0); });
    new MutationObserver(() => { close(); render(); }).observe(select, {childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected', 'label']});
    render();
  });
})();
