'use strict';
window.MiaoAPI = Object.freeze({
  async request(path, {method='GET', payload, token='', timeout=8000}={}) {
    const response = await fetch(path, {method, cache:'no-store', signal:AbortSignal.timeout(timeout),
      headers:payload===undefined?{}:{'Content-Type':'application/json','X-Miao-Token':token},
      body:payload===undefined?undefined:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '操作失败');
    return result;
  }
});
