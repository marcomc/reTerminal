// Focused semantic checks against the exact native document source.
const fs=require('node:fs');const vm=require('node:vm');const assert=require('node:assert/strict');
const path=require('node:path');
const template=path.resolve(__dirname,'..');
const state=process.env.SENSECRAFT_AGENDA_STATE_DIR?path.resolve(process.env.SENSECRAFT_AGENDA_STATE_DIR):path.resolve(template,'../../.private/native-agenda');
const production=process.argv.includes('--production');const source=fs.readFileSync((production?path.join(state,'agenda-upload.html'):path.join(template,'src/agenda.html')),'utf8').split('<script>')[1].split('</script>')[0].replace(/\nload\(\);\s*$/,'');
function context(cfg={}){const c=vm.createContext({URLSearchParams,URL,Date,Intl,Math,console,location:{search:'',hash:'#config='+encodeURIComponent(JSON.stringify(cfg))}});vm.runInContext(source,c);return c;}
let checked=0;function check(c,expression,expected){assert.deepEqual(JSON.parse(JSON.stringify(vm.runInContext(expression,c))),expected);checked++;}
const c=context();check(c,'easter(2026)','2026-04-05');check(c,'easter(2027)','2027-03-28');
for(const [day,theme] of [['2027-01-06','epiphany'],['2026-10-31','halloween'],['2026-12-24','christmas'],['2026-12-25','christmas'],['2026-12-26','christmas'],['2026-12-27','month-12'],['2026-04-05','easter'],['2026-02-17','carnival']])check(c,`selectedTheme('${day}')`,theme);
for(let month=1;month<=12;month++){let mm=String(month).padStart(2,'0');check(c,`selectedTheme('2026-${mm}-15')`,'month-'+mm);}
check(context({specialDates:false}),"selectedTheme('2027-01-06')",'month-01');
check(context({backgroundMode:'manual',theme:'floral'}),"selectedTheme('2027-01-06')",'floral');
for(const [month,theme]of [['03','spring'],['06','summer'],['09','autumn'],['12','winter']])check(context({cadence:'seasons'}),`selectedTheme('2026-${month}-15')`,theme);
check(context({cadence:'seasons',latitude:-34}),"selectedTheme('2026-06-15')",'winter');
for(const [language,weekday] of [['it','mercoledì'],['en','Wednesday'],['fr','mercredi'],['de','Mittwoch'],['es','miércoles']])check(context({language}),"civilWeekday('2026-09-30')",weekday);
check(context({timezone:'Pacific/Kiritimati'}),"civilWeekday('2026-09-30')",'mercoledì');
check(context({timezone:'Pacific/Kiritimati'}),"dayKey(new Date('2026-09-30T23:00:00Z'))",'2026-10-01');
const n=context({timezone:'UTC',calendars:[{id:'A',initials:'AA',color:'#ff0000'}],excludeBirthdays:true});vm.runInContext("now=new Date('2026-09-30T08:00:00Z')",n);
const events=[{id:'past',calendarId:'A',summary:'Past',start:{dateTime:'2026-09-30T07:00:00Z'}},{id:'future',calendarId:'A',summary:'Future',start:{dateTime:'2026-09-30T09:00:00Z'}},{id:'other',calendarId:'B',summary:'Other',start:{dateTime:'2026-09-30T09:00:00Z'}},{id:'birthday',calendarId:'A',summary:"Example's birthday",start:{date:'2026-09-30'},end:{date:'2026-10-01'}},{id:'ongoing',calendarId:'A',summary:'Multiday',start:{date:'2026-09-28'},end:{date:'2026-10-02'}},{id:'tomorrow',calendarId:'A',summary:'Tomorrow',start:{dateTime:'2026-10-01T09:00:00Z'}},{id:'cancelled',calendarId:'A',status:'cancelled',summary:'Cancelled',start:{dateTime:'2026-09-30T10:00:00Z'}},{id:'too-late',calendarId:'A',summary:'Outside horizon',start:{dateTime:'2026-10-05T09:00:00Z'}}];
check(n,`normalize(${JSON.stringify(events)}).map(e=>e.id)`,['ongoing','future','tomorrow']);check(n,`normalize(${JSON.stringify([...events,events[1]])}).length`,3);
check(c,"moon(new Date('2026-09-30T12:00:00Z')).label",'Calante');
for(const [value,expected]of [[0,'0%'],[100,'100%'],[78.4,'78%'],[null,'—'],[101,'—'],[-1,'—'],['invalid','—']])check(c,`batteryPercentage(${JSON.stringify(value)})`,expected);
const active=context({timezone:'UTC',calendars:[{id:'A',initials:'AA',color:'#ff0000'}]});vm.runInContext("now=new Date('2026-09-30T17:13:00Z')",active);
const ongoing={id:'active',calendarId:'A',summary:'Shift',start:{dateTime:'2026-09-30T14:00:00Z'},end:{dateTime:'2026-09-30T17:30:00Z'}};
check(active,`normalize([${JSON.stringify(ongoing)}]).length`,1);
vm.runInContext("now=new Date('2026-09-30T17:30:00Z')",active);check(active,`normalize([${JSON.stringify(ongoing)}]).length`,0);
vm.runInContext("now=new Date('2026-09-30T17:13:00Z')",active);
const overnight={...ongoing,id:'overnight',start:{dateTime:'2026-09-29T22:00:00Z'},end:{dateTime:'2026-09-30T18:00:00Z'}};check(active,`normalize([${JSON.stringify(overnight)}])[0].key`,'2026-09-30');
const evening={...ongoing,id:'evening',start:{dateTime:'2026-10-01T21:00:00Z'},end:{dateTime:'2026-10-01T23:00:00Z'}};check(active,`normalize([${JSON.stringify(evening)}]).length`,1);
const many=Array.from({length:100},(_,i)=>({...evening,id:'many-'+i}));check(active,`normalize(${JSON.stringify(many)}).length`,100);
fs.mkdirSync(state,{recursive:true,mode:0o700});fs.writeFileSync(path.join(state,production?'semantic-production-checks.json':'semantic-checks.json'),JSON.stringify({checked,passed:true},null,2));console.log('Native source semantic checks passed:',checked);
