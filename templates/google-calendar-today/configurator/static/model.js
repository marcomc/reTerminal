/* Pure preference operations shared by the browser and dependency-free checks. */
'use strict';
(function (scope) {
  const labels = {white:'Bianco / base',dark:'Scuro / base',floral:'Floreale',unicorn:'Unicorno',lgbtq:'LGBTQ',spring:'Primavera',summer:'Estate',autumn:'Autunno',winter:'Inverno',easter:'Pasqua',christmas:'Natale',epiphany:'Epifania',halloween:'Halloween',carnival:'Carnevale italiano'};
  const months = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];
  const monthFiles = ['january','february','march','april','may','june','july','august','september','october','november','december'];
  const fields = ['language','timezone','city','latitude','longitude','showTimezone','showSunrise','showSunset','showMoon','showBattery','excludeBirthdays','markerMode','backgroundMode','cadence','specialDates','theme','mode','autoDark','intensity','titleSize','minTitleSize','calendars','hemisphere','carnivalRule'];
  const clone = value => JSON.parse(JSON.stringify(value));
  function preferences(value) {
    const result = {};
    for (const field of fields) if (Object.hasOwn(value, field)) result[field] = clone(value[field]);
    result.calendars = (result.calendars || []).map(item => ({id:String(item.id),name:String(item.name || ''),initials:String(item.initials || ''),color:String(item.color || '')}));
    return result;
  }
  function fingerprint(agenda, device) {
    return JSON.stringify({agenda:preferences(agenda),device_id:device == null ? '' : String(device)});
  }
  function theme(key, dark = false) {
    if (key.startsWith('month-')) {
      const number = Number(key.slice(6));
      const stem = `${String(number).padStart(2,'0')}-${monthFiles[number - 1]}`;
      return {key,label:months[number - 1],group:'months',asset:`/assets/monthly/${stem}${dark ? '-dark' : ''}.png`};
    }
    return {key,label:labels[key] || key,group:'themes',asset:['white','dark'].includes(key) ? null : `/assets/themes/${key}${dark ? '-dark' : ''}.png`};
  }
  function dependencies(agenda) {
    const auto = agenda.backgroundMode === 'automatic';
    return {cadence:auto,specialDates:auto,hemisphere:auto && agenda.cadence === 'seasons',carnivalRule:auto && agenda.specialDates,theme:!auto,mode:agenda.autoDark};
  }
  function validate(agenda, device, available) {
    const errors = [];
    const add = (field,message) => errors.push({field,message});
    if (!device) add('device','Scegli un display compatibile prima di continuare.');
    if (available && !available.devices.some(item => String(item.id) === String(device) && item.compatible)) add('device','Il display selezionato non è disponibile o non è compatibile.');
    if (agenda.calendars.length < 1 || agenda.calendars.length > 10) add('calendars','Seleziona da 1 a 10 calendari.');
    if (new Set(agenda.calendars.map(item => item.id)).size !== agenda.calendars.length) add('calendars','Ogni calendario può essere selezionato una sola volta.');
    for (const item of agenda.calendars) {
      if (!item.initials.trim() || Array.from(item.initials).length > 4) add('calendars',`Le iniziali di «${item.name}» devono contenere da 1 a 4 caratteri.`);
      if (!/^#[\da-f]{6}$/i.test(item.color)) add('calendars',`Scegli un colore valido per «${item.name}».`);
      if (available && !available.calendars.some(calendar => String(calendar.id) === item.id)) add('calendars',`«${item.name}» non è più disponibile. Aggiorna la lista o rimuovilo.`);
    }
    for (const field of ['intensity','titleSize','minTitleSize']) {
      const min = field === 'intensity' ? 0 : 24, max = field === 'intensity' ? 100 : 32;
      if (!Number.isInteger(agenda[field]) || agenda[field] < min || agenda[field] > max) add(field,`Inserisci un numero intero da ${min} a ${max}.`);
    }
    if (agenda.minTitleSize > agenda.titleSize) add('minTitleSize','Il minimo non può superare la dimensione dei titoli.');
    try { new Intl.DateTimeFormat('it',{timeZone:agenda.timezone}).format(); } catch { add('timezone','Inserisci un fuso orario valido.'); }
    if (!agenda.city || !Number.isFinite(agenda.latitude) || !Number.isFinite(agenda.longitude) || Math.abs(agenda.latitude) > 90 || Math.abs(agenda.longitude) > 180) add('city-search','Scegli una città dai risultati della ricerca.');
    return errors;
  }
  function initials(name) { return Array.from(name.trim().split(/\s+/).slice(0,2).map(word => Array.from(word)[0] || '').join('').toUpperCase()).slice(0,4).join('') || 'CA'; }
  const model = {fields,clone,preferences,fingerprint,theme,dependencies,validate,initials};
  if (typeof module !== 'undefined' && module.exports) module.exports = model;
  else scope.AgendaModel = model;
})(globalThis);
