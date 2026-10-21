'use strict';
let selectedDevice = 'default';
window.MiaoAPI = Object.freeze({
  get device(){return selectedDevice;},
  selectDevice(id){selectedDevice=id;},
  url(path, device=selectedDevice){const url=new URL(path,location.origin);url.searchParams.set('device',device);return url.pathname+url.search;},
  async request(path, {method='GET', payload, token='', timeout=8000, device=selectedDevice}={}) {
    const response = await fetch(this.url(path,device), {method, cache:'no-store', signal:AbortSignal.timeout(timeout),
      headers:payload===undefined?{}:{'Content-Type':'application/json','X-Miao-Token':token},
      body:payload===undefined?undefined:JSON.stringify(payload)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '操作失败');
    return result;
  }
});
