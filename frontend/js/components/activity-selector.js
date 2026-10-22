'use strict';
(() => {
  const app = document.getElementById('activity-app');
  const activity = document.getElementById('activity-choice');
  let catalog = [], snapshot, signature = '';
  function options(select, rows, value) {
    select.replaceChildren(...rows.map(row => {
      const option = document.createElement('option');
      option.value = row.id; option.textContent = row.label;
      return option;
    }));
    select.value = value || rows[0]?.id || '';
  }
  function activities(value) {
    options(activity, catalog.find(item => item.id === app.value)?.activities || [], value);
  }
  window.addEventListener('miaotask:state', event => {
    snapshot = event.detail;
    catalog = snapshot.catalog || [];
    const next = JSON.stringify([catalog, snapshot.app, snapshot.activity]);
    if (next !== signature) {
      signature = next;
      options(app, catalog, snapshot.app); activities(snapshot.activity);
    }
    const busy = snapshot.busy || ['running','connecting','scanning','paused','stopping'].includes(snapshot.status);
    app.disabled = activity.disabled = document.getElementById('activity-apply').disabled = busy || !catalog.length;
    document.getElementById('activity-name').textContent = catalog.find(a=>a.id===snapshot.app)?.activities.find(a=>a.id===snapshot.activity)?.label || '尚未安装活动包';
  });
  app.addEventListener('change', () => activities());
  document.getElementById('activity-apply').addEventListener('click', async () => {
    try {
      await MiaoAPI.request('/api/select_activity', {method:'POST', token:snapshot.token,
        payload:{app:app.value, activity:activity.value}});
      window.dispatchEvent(new Event('miaotask:activity-changed'));
    } catch (error) { window.dispatchEvent(new CustomEvent('miaotask:error', {detail:error.message})); }
  });
})();
