/* Change language using Django's CSRF-protected set_language view. Unsaved form
   entries and selected files survive only in memory; nothing is written to storage. */
(() => {
  'use strict';
  const gettext = window.gettext || (text => text);
  const formKey = form => `${form.method.toLowerCase()}:${new URL(form.action || location.href, location.href).pathname}`;
  function restore() {
    const drafts = window.__fmscLanguageDraft;
    delete window.__fmscLanguageDraft;
    if (!drafts) return;
    const forms = [...document.forms].filter(form => !form.hasAttribute('data-language-form'));
    for (const draft of drafts) {
      const form = forms.filter(item => formKey(item) === draft.key)[draft.index];
      if (!form) continue;
      for (const saved of draft.fields) {
        const field = [...form.elements].find(item => item.name === saved.name && item.type === saved.type && (!['radio', 'checkbox'].includes(item.type) || item.value === saved.value));
        if (!field) continue;
        if (saved.type === 'file') {
          if (saved.files.length && window.DataTransfer) {
            const transfer = new DataTransfer();
            saved.files.forEach(file => transfer.items.add(file));
            field.files = transfer.files;
          }
        } else if (['radio', 'checkbox'].includes(saved.type)) field.checked = saved.checked;
        else if (saved.type === 'select-multiple') [...field.options].forEach(option => option.selected = saved.values.includes(option.value));
        else field.value = saved.value;
      }
    }
    // Other progressive enhancements initialize after this script.
    document.addEventListener('DOMContentLoaded', () => {
      forms.forEach(form => form.querySelectorAll('input[type=file], select').forEach(field => field.dispatchEvent(new Event('change', {bubbles:true}))));
    }, {once:true});
  }
  restore();
  const menus = [...document.querySelectorAll('[data-language-menu]')];
  document.addEventListener('click', event => menus.forEach(menu => { if (!menu.contains(event.target)) menu.open = false; }));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') menus.forEach(menu => { if (menu.open) { menu.open = false; menu.querySelector('summary').focus(); } });
  });
  let switching = false;
  document.querySelectorAll('[data-language-form]').forEach(form => {
    form.addEventListener('submit', async event => {
      if (!window.fetch || !window.FormData || !event.submitter) return;
      event.preventDefault();
      if (switching) return;
      switching = true;
      const menu = form.closest('[data-language-menu]');
      menu?.setAttribute('aria-busy','true');
      const body = new FormData(form);
      body.set('language',event.submitter.value);
      const drafts=[];
      const indexes=new Map();
      [...document.forms].filter(item => !item.hasAttribute('data-language-form')).forEach(item => {
        const key=formKey(item), index=indexes.get(key)||0;
        indexes.set(key,index+1);
        const fields=[...item.elements].filter(field => field.name && !field.disabled && !['password','submit','button','reset','hidden'].includes(field.type)).map(field => ({name:field.name, type:field.type, value:field.value, checked:field.checked, values:field.selectedOptions ? [...field.selectedOptions].map(option => option.value) : [], files:field.files ? [...field.files] : []}));
        if (fields.length) drafts.push({key,index,fields});
      });
      try {
        const response=await fetch(form.action,{method:'POST',body,credentials:'same-origin',cache:'no-store'});
        if (!response.ok || new URL(response.url).origin !== location.origin) throw new Error('Language switch failed');
        const html=await response.text();
        if (!html.includes('<html')) throw new Error('No translated page');
        history.replaceState(history.state, "", new URL(response.url).pathname + new URL(response.url).search + location.hash);
        window.clearInterval(window.__fmscNotificationTimer);
        delete window.django; // Start a fresh JavaScript catalog, including when returning to English.
        window.__fmscLanguageDraft=drafts;
        document.open(); document.write(html); document.close();
      } catch {
        delete window.__fmscLanguageDraft;
        switching=false;
        menu?.removeAttribute('aria-busy');
        let status=document.querySelector('.language-status');
        if (!status) { status=document.createElement('p');status.className='language-status';status.setAttribute('role','alert');document.body.append(status); }
        status.textContent=gettext('Could not change the language. Your entries are still here. Please try again.');
      }
    });
  });
})();
