'use strict';
const $ = id => document.getElementById(id);
const busyStates = new Set(['connecting', 'scanning', 'running', 'paused', 'stopping']);
const statusLabels = {disconnected:'等待连接',connecting:'正在连接',ready:'设备已就绪',scanning:'识别中',running:'正在执行',paused:'已暂停',stopping:'正在停止',stopped:'已停止',finished:'本轮已结束',needs_attention:'需要手动处理',error:'操作失败'};
const phaseLabels = {locating:'LOCATING CAMPAIGN',ready:'READY TO GO',opening:'OPENING TASK',browsing:'BROWSING IN PROGRESS',returning:'BACK TO YOUR TASKS',scanning:'FINDING MORE TASKS',finished:'SESSION FINISHED',stopped:'SESSION STOPPED',needs_attention:'YOUR ATTENTION NEEDED'};
const taskLabels = {pending:'待执行',running:'执行中',done:'已核验',manual:'手动处理',failed:'未通过',disabled:'已跳过'};
const kindLabels = {browse:'浏览',search:'搜索',visit:'跳转',claim:'领奖',manual:'手动',done:'完成'};
let state, token='', filter='all', taskHash='', logsHash='', initialized=false, requesting=false, toastTimer;
function el(tag, cls, text) {const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
function config(){return {default_browse_seconds:Number($('browse-seconds').value),browse_extra_seconds:Number($('browse-extra').value),max_attempts:Number($('max-attempts').value),max_tasks:Number($('max-tasks').value),allow_cross_app:$('cross-app').checked,ocr:$('ocr').checked,scroll_browse:$('scroll').checked,claim_rewards:$('claim').checked};}
async function action(name){
  if(requesting)return;
  if(['run','scan','connect','configure'].includes(name)&&!$('settings-form').reportValidity())return;
  requesting=true;
  try{const payload={config:config(),auto_open:document.querySelector('input[name=mode]:checked').value==='auto'};
    if(name==='connect'){payload.device_type=$('device-type').value;payload.serial=$('serial').value.trim();}
    const response=await fetch('/api/'+name,{method:'POST',headers:{'Content-Type':'application/json','X-Miao-Token':token},body:JSON.stringify(payload)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'操作失败');if(name==='shutdown'){toast('助手已退出，可以关闭此页面');return;}if(name==='configure')toast('执行设置已应用');await poll();
  }catch(error){toast(error.message);}finally{requesting=false;}
}
async function discover(){
  $('discover').disabled=true;
  try{const response=await fetch('/api/devices');if(!response.ok)throw new Error('设备检测失败');const data=await response.json();const options=$('device-options');options.replaceChildren();
    for(const d of data.devices){const o=el('option','',`${d.model||d.type} · ${d.status}`);o.value=d.serial;options.append(o);}
    const ready=data.devices.filter(d=>d.status==='device');
    if(ready.length===1&&!$('serial').value){$('serial').value=ready[0].serial;$('device-type').value=ready[0].type;}
    $('device-hint').textContent=data.devices.length?data.devices.map(d=>`${d.model||d.serial} · ${{device:'已连接',unauthorized:'请在手机允许 USB 调试',offline:'设备离线'}[d.status]||d.status}`).join('；'):(data.errors.join('；')||'暂未检测到设备。请检查数据线和 USB 调试，也可填入已连接的无线调试地址。');
  }catch(e){toast(e.message);}finally{$('discover').disabled=false;}
}
function renderTasks(force=false){
  const tasks=state.tasks||[];const hash=JSON.stringify(tasks)+filter;if(!force&&hash===taskHash)return;taskHash=hash;$('task-count').textContent=tasks.length;
  const list=tasks.filter(t=>filter==='all'||(filter==='manual'?['manual','failed','disabled'].includes(t.status):!['manual','disabled'].includes(t.status)));
  const table=$('task-table');table.replaceChildren();
  if(!list.length){const box=el('div','empty-state');box.append(el('div','empty-icon','☷'),el('h3','',tasks.length?'这个分类暂时没有任务':'任务还没入场'),el('p','',tasks.length?'切换其他分类查看执行情况。':'连接设备后，点击「识别任务」查看任务列表。'));table.append(box);return;}
  for(const t of list){const row=el('div','task-row');const info=el('div');const title=el('div','task-title');title.append(el('span','task-type',kindLabels[t.kind]||t.kind),el('span','',t.title));info.append(title,el('div','task-detail',t.reason||t.detail||'按页面要求浏览并返回'));const progress=el('div','task-progress',`${t.current}/${t.total}`);row.append(info,progress,el('span','task-status '+t.status,taskLabels[t.status]||t.status));table.append(row);}
}
function renderLogs(){const logs=state.logs||[];const hash=logs.length?String(logs[logs.length-1].id):'';if(hash===logsHash)return;logsHash=hash;const list=$('log-list');const atBottom=list.scrollTop+list.clientHeight>=list.scrollHeight-30;list.replaceChildren();for(const log of logs){const line=el('div','log-line '+log.level);line.append(el('time','',log.time.slice(11,19)),el('span','log-level',log.level),el('span','log-text',log.message));list.append(line);}if(atBottom)list.scrollTop=list.scrollHeight;}
function render(){
  $('app-version').textContent=state.version||'';
  const busy=busyStates.has(state.status)||state.busy,running=state.status==='running',paused=state.status==='paused';
  $('connection-label').className='status-pill'+(state.connected?' connected':'');$('connection-label').replaceChildren(el('span'),document.createTextNode(statusLabels[state.status]||state.status));
  $('connect').disabled=busy;$('connect').textContent=state.connected?'重新连接 ↗':'连接设备 ↗';
  for(const id of ['run','scan','capture'])$(id).disabled=!state.connected||busy;
  $('pause').disabled=!running&&!paused;$('pause').textContent=paused?'▶ 继续':'Ⅱ 暂停';$('stop').disabled=!busy||state.status==='stopping';
  $('device-type').disabled=busy;$('serial').disabled=busy;
  $('save-settings').disabled=busy;
  $('phase-label').textContent=phaseLabels[state.phase]||'READY WHEN YOU ARE';
  $('execution-title').textContent=paused?'休息一下，进度还在':state.current_task||({disconnected:'准备好，再出发',ready:'手机已就绪',finished:'本轮任务已处理',needs_attention:'这一步，需要你来处理',error:'连接或执行遇到问题',stopped:'已停止执行'}[state.status]||statusLabels[state.status]);
  $('message').textContent=state.message;$('countdown').hidden=!running||!state.remaining;$('remaining').textContent=state.remaining||0;
  document.querySelector('.execution-card').classList.toggle('is-active',running);document.querySelector('.execution-card').classList.toggle('needs-attention',['error','needs_attention'].includes(state.status));
  const stats=state.stats||{};for(const [id,key] of [['completed','completed'],['claims','claims'],['cross','cross_app'],['skipped','skipped'],['failed','failed']])$('stat-'+id).textContent=stats[key]||0;
  const seconds=stats.elapsed||0;$('elapsed').textContent=`累计运行 ${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
  $('package-name').textContent=state.package||'设备未连接';$('preview-source').textContent=state.source==='ocr'?'本地 OCR 识别':state.source==='ui'?'页面控件识别':'手机截图预览';
  if(!initialized){const c=state.config;$('browse-seconds').value=c.default_browse_seconds;$('browse-extra').value=c.browse_extra_seconds;$('max-attempts').value=c.max_attempts;$('max-tasks').value=c.max_tasks;$('cross-app').checked=c.allow_cross_app;$('ocr').checked=c.ocr;$('scroll').checked=c.scroll_browse;$('claim').checked=c.claim_rewards;initialized=true;}
  renderTasks();renderLogs();
}
async function poll(){try{const response=await fetch('/api/state');if(!response.ok)throw new Error('控制台连接失败');state=await response.json();token=state.token;render();}catch(e){$('connection-label').replaceChildren(el('span'),document.createTextNode('服务已断开'));for(const id of ['run','scan','connect','capture','pause','stop'])$(id).disabled=true;}}
function preview(){if(state?.connected){$('phone-image').src='/api/screenshot?t='+Date.now();}}
$('phone-image').addEventListener('load',()=>{$('phone-image').hidden=false;$('phone-placeholder').hidden=true;$('preview-time').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false});});
$('phone-image').addEventListener('error',()=>{$('phone-image').hidden=true;$('phone-placeholder').hidden=false;});
for(const id of ['connect','scan','run','capture','stop'])$(id).addEventListener('click',()=>action(id));
$('pause').addEventListener('click',()=>action(state?.status==='paused'?'resume':'pause'));
$('save-settings').addEventListener('click',()=>action('configure'));
$('shutdown').addEventListener('click',()=>action('shutdown'));
$('discover').addEventListener('click',discover);
$('settings-form').addEventListener('submit',event=>event.preventDefault());
for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b===button));if(state)renderTasks(true);});
for(const name of ['tasks','logs'])$(name+'-tab').addEventListener('click',()=>{for(const other of ['tasks','logs']){const selected=name===other;$(other+'-tab').classList.toggle('active',selected);$(other+'-tab').setAttribute('aria-selected',String(selected));$(other+'-panel').hidden=!selected;}});
poll().then(()=>{discover();preview();});setInterval(poll,1000);setInterval(preview,4000);
