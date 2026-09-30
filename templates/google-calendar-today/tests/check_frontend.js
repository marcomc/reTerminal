/* Run with Node.js; no browser transport and no installed dependencies. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const model = require('../configurator/static/model.js');
const root = path.resolve(__dirname,'..');
const raw = JSON.parse(fs.readFileSync(path.join(root,'examples/config.example.json'),'utf8'));
const config = model.preferences(raw.agenda || raw);
config.calendars = [{id:'sample-a',name:'Calendario esempio',initials:'AA',color:'#123456'}];
const resources = {devices:[{id:'sample-device',compatible:true}],calendars:[{id:'sample-a'}]};
let checks = 0;
function check(condition, label) { assert.ok(condition,label); checks++; }
check(!model.validate(config,'sample-device',resources).length,'Valid preferences pass');
for (const count of [0,11]) { const draft = model.clone(config); draft.calendars = Array.from({length:count},(_,i) => ({...config.calendars[0],id:String(i)})); check(model.validate(draft,'sample-device').some(item => item.field === 'calendars'),`Reject count ${count}`); }
for (const count of [1,10]) { const draft = model.clone(config); draft.calendars = Array.from({length:count},(_,i) => ({...config.calendars[0],id:String(i)})); check(!model.validate(draft,'sample-device').length,`Accept count ${count}`); }
for (const initials of ['', '     ', 'ABCDE']) { const draft = model.clone(config); draft.calendars[0].initials = initials; check(model.validate(draft,'sample-device').length > 0,'Reject invalid initials'); }
for (const initials of ['A','ABCD','🌙🌞']) { const draft = model.clone(config); draft.calendars[0].initials = initials; check(!model.validate(draft,'sample-device').length,'Allow unicode initials within four codepoints'); }
for (const intensity of [0,1,49,50,51,99,100]) check(!model.validate({...config,intensity},'sample-device').length,`Intensity ${intensity}`);
for (const intensity of [-1,101,50.5,null,NaN,'50']) check(model.validate({...config,intensity},'sample-device').some(item => item.field === 'intensity'),'Reject invalid intensity');
for (const sizes of [[24,24],[32,24],[32,32]]) check(!model.validate({...config,titleSize:sizes[0],minTitleSize:sizes[1]},'sample-device').length,'Valid font bounds');
for (const sizes of [[23,23],[33,24],[25,26],[28.5,24]]) check(model.validate({...config,titleSize:sizes[0],minTitleSize:sizes[1]},'sample-device').length > 0,'Reject invalid font bounds');
check(model.validate(config,'',resources).some(item => item.field === 'device'),'Require device');
check(model.validate(config,'missing',resources).some(item => item.field === 'device'),'Reject missing device');
check(model.validate(config,'sample-device',{...resources,calendars:[]}).some(item => item.field === 'calendars'),'Reject vanished calendar');
check(model.validate({...config,timezone:'invalid/timezone'},'sample-device').some(item => item.field === 'timezone'),'Reject timezone');
check(model.validate({...config,latitude:Infinity},'sample-device').some(item => item.field === 'city-search'),'Reject nonfinite coordinate');
const stripped = model.preferences({...config,session_id:'sample-secret',batteryBinding:{apiKey:'sample-secret'},api_key:'sample-secret'});
check(!JSON.stringify(stripped).includes('sample-secret'),'No credential fields forwarded');
check(model.fingerprint(config,42) === model.fingerprint(config,'42'),'String device IDs');
check(model.fingerprint(config,'sample-device') !== model.fingerprint({...config,intensity:config.intensity+1},'sample-device'),'Dirty changes detected');
for (const backgroundMode of ['manual','automatic']) for (const cadence of ['months','seasons']) for (const specialDates of [false,true]) for (const autoDark of [false,true]) {
  const draft = {...config,backgroundMode,cadence,specialDates,autoDark};
  const before = JSON.stringify(draft), deps = model.dependencies(draft);
  check(deps.theme === (backgroundMode === 'manual'),'Manual themes enabled only manually');
  check(deps.hemisphere === (backgroundMode === 'automatic' && cadence === 'seasons'),'Hemisphere relevance');
  check(deps.carnivalRule === (backgroundMode === 'automatic' && specialDates),'Carnival relevance');
  check(deps.mode === autoDark,'Solar fallback independent of theme');
  check(JSON.stringify(draft) === before,'Disabled controls preserve values');
}
const themes = ['white','dark','floral','unicorn','lgbtq','spring','summer','autumn','winter','easter','christmas','epiphany','halloween','carnival',...Array.from({length:12},(_,i) => `month-${String(i+1).padStart(2,'0')}`)];
const manifest = JSON.parse(fs.readFileSync(path.join(root,'assets/manifest.json'),'utf8'));
const approved = new Set(manifest.decorations.map(item => `/assets/${item.path}`));
for (const key of themes) for (const dark of [false,true]) { const item = model.theme(key,dark); check(Boolean(item.label),'Localized theme label'); check(!item.asset || approved.has(item.asset),`Approved asset ${item.asset}`); }
check(themes.length === 26,'All 26 themes');
console.log(`${checks} frontend model checks passed.`);
