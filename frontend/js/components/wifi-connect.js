'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const status = byId('wifi-status');
  let snapshot, requesting = false, finding = false, reflectedSerial = '';
  const ids = ['wifi-pair','wifi-connect','wifi-discover','wifi-pair-address','wifi-connect-address','wifi-code'];
  function render() {
    const busy = requesting || snapshot?.busy || ['running','connecting','scanning','paused','stopping'].includes(snapshot?.status);
    for (const id of ids) byId(id).disabled = Boolean(busy || id === 'wifi-discover' && finding);
  }
  function mode(first) {
    byId('wifi-pair-panel').hidden = !first;
    byId('wifi-connect-title').textContent = first ? '2. 连接手机' : '连接已配对手机';
    for (const [id, active] of [['wifi-first',first],['wifi-known',!first]]) {
      byId(id).classList.toggle('is-open', active);
      byId(id).setAttribute('aria-pressed', String(active));
    }
    if (!first) byId('wifi-code').value = '';
  }
  async function submit(pair) {
    if (requesting) return;
    let payload;
    if (pair) {
      const address = byId('wifi-pair-address').value.trim(), code = byId('wifi-code').value.trim();
      if (!address || !/^[0-9]{6}$/.test(code)) { status.textContent = '请填写配对弹窗中的 IP:端口和六位配对码。'; return; }
      payload = {pair_address:address, pair_code:code};
    } else {
      const address = byId('wifi-connect-address').value.trim();
      if (!address) { status.textContent = '请填写无线调试主页面的 IP:端口。'; return; }
      payload = {connect_address:address};
    }
    requesting = true; render();
    try {
      await MiaoAPI.request('/api/wifi/' + (pair ? 'pair' : 'connect'), {
        method:'POST', token:snapshot?.token, payload,
      });
      status.textContent = pair ? '正在配对，请保持手机的配对码弹窗打开…' : '正在连接并读取手机实例…';
      window.dispatchEvent(new Event('miaotask:activity-changed'));
    } catch (error) { status.textContent = error.message; }
    finally { byId('wifi-code').value = ''; delete payload.pair_code; requesting = false; render(); }
  }
  byId('wifi-first').addEventListener('click', () => mode(true));
  byId('wifi-known').addEventListener('click', () => mode(false));
  byId('wifi-pair').addEventListener('click', () => submit(true));
  byId('wifi-connect').addEventListener('click', () => submit(false));
  byId('wifi-code').addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); submit(true); }
  });
  byId('wifi-connect-address').addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); submit(false); }
  });
  byId('wifi-discover').addEventListener('click', async () => {
    finding = true; render(); status.textContent = '正在查找无线调试广播…';
    try {
      const result = await MiaoAPI.request('/api/wifi/devices', {timeout:20000});
      for (const kind of ['pair','connect']) {
        const addresses = new Set((result.services || []).filter(item => item.kind === (kind === 'pair' ? 'pairing' : kind)).map(item => item.address));
        if (kind === 'connect') for (const item of result.devices || []) if (/^(?:[0-9.]+|\[[0-9a-fA-F:]+\]):[0-9]+$/.test(item.serial)) addresses.add(item.serial);
        byId('wifi-'+kind+'-options').replaceChildren(...[...addresses].map(address => {
          const option = document.createElement('option'); option.value = address; return option;
        }));
      }
      status.textContent = result.services?.length || result.devices?.length
        ? '已发现无线地址，可在输入框下拉选择；请与自己手机显示的地址核对后操作。'
        : (result.errors || []).join('；') || '没有收到无线广播，请手动填写手机显示的地址；同一 Wi-Fi 仍可能有设备隔离。';
    } catch (error) { status.textContent = error.message; }
    finally { finding = false; render(); }
  });
  window.addEventListener('miaotask:state', event => {
    snapshot = event.detail; render();
    if (snapshot.phase === 'connecting' || snapshot.phase === 'connect_failed' || snapshot.wifi_paired && snapshot.status === 'disconnected') status.textContent = snapshot.message;
    if (snapshot.connected && snapshot.status === 'ready' && snapshot.device?.serial?.includes(':')) {
      status.textContent = '无线设备已就绪，可以开始自动执行。日统计与同一手机的 USB 连接共用。';
      if (reflectedSerial !== snapshot.device.serial) {
        reflectedSerial = snapshot.device.serial;
        byId('serial').value = snapshot.device.serial;
        byId('device-type').value = 'uiautomator2';
      }
    }
    if (!snapshot.connected) reflectedSerial = '';
  });
})();
