'use strict';
(() => {
  const M = window.AgendaModel;
  const $ = id => document.getElementById(id);
  const palette = ['#D32F2F','#1565C0','#2E7D32','#7B1FA2','#EF6C00','#00838F','#C2185B','#5D4037','#455A64','#9E9D24'];
  const errors = {
    validation:'Controlla le impostazioni e le risorse selezionate.',
    key_missing:'Collega prima SenseCraft con una API Key.',
    key_invalid:'La API Key SenseCraft non è valida o non è più autorizzata. Incolla una chiave valida.',
    environment_override:'È attiva una chiave impostata nell’ambiente. Riavvia il configuratore senza SENSECRAFT_API_KEY prima di incollare una chiave diversa.',
    google_missing:'Collega Google Calendar attraverso SenseCraft.',
    google_expired:'Il collegamento Google è scaduto o revocato. Usa «Ricollega» per autorizzarlo di nuovo.',
    network:'Il servizio non è raggiungibile. Controlla la connessione e riprova.',
    upstream:'SenseCraft non ha accettato l’operazione. Puoi verificare le connessioni e riprovare.',
    protocol:'Il servizio ha restituito una risposta inattesa. Verifica le connessioni e riprova.',
    uncertain_upload:'Un upload potrebbe essere riuscito, ma la risposta è andata persa. Il tentativo è fermo: gestisci l’esito incerto prima di riprovare.',
    uncertain_create:'La creazione della pagina ha un esito incerto. Riprendi la stessa pubblicazione per riconciliare lo stato salvato.',
    readback:'La pagina o l’assegnazione al display non sono ancora verificate. Riprendi la pubblicazione per completare la verifica.',
    busy:'Un’anteprima o una pubblicazione è già in corso. Attendi, poi aggiorna lo stato o riprendi lo stesso tentativo.',
    stopped:'Il configuratore si sta chiudendo. Lo stato è conservato: riaprilo per riprendere.',
    forbidden:'La richiesta locale non è autorizzata. Ricarica il pannello per aggiornare la connessione.',
    not_found:'La risorsa locale non è disponibile. Aggiorna lo stato e riprova.',
    internal:'L’operazione non è stata completata. Lo stato di recupero è stato conservato.'
  };
  const phases = {preflight:'Verifica connessioni e selezioni',build:'Preparazione del template e degli sfondi',preview:'Rendering dell’anteprima',save_page:'Salvataggio della pagina privata',deploy:'Aggiornamento del display',verify:'Verifica pagina, assegnazione e snapshot',complete:'Operazione completata'};
  let state = null, draft = null, selectedDevice = '', saved = '', previewFingerprint = null;
  let busy = false, retryAction = null, failedAction = null, confirmation = null, lastFocus = null;
  let mappings = new Map(), themeFilter = 'all', cityGeneration = 0, cityTimer = null, job = null;
  let previewLoading = false;
  function announce(text) { $('announcement').textContent = text; }
  function make(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }
  async function request(url, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 180000);
    try {
      const options = {signal:controller.signal,credentials:'same-origin',cache:'no-store'};
      if (payload !== undefined) Object.assign(options,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state?.csrf_token || ''},body:JSON.stringify(payload)});
      const response = await fetch(url, options);
      let result;
      try { result = await response.json(); } catch { throw {code:'protocol'}; }
      if (!response.ok) throw result.error || {code:'internal'};
      return result;
    } catch (error) {
      if (error.code) throw error;
      throw {code:'network',retryable:true};
    } finally { clearTimeout(timer); }
  }
  function showError(error, action = null) {
    $('error-text').textContent = errors[error.code] || errors.internal;
    retryAction = action;
    $('retry').hidden = !action;
    $('uncertain-recovery').hidden = error.code !== 'uncertain_upload' && !state?.publication?.uncertain_uploads;
    $('global-error').hidden = false;
    if (['key_missing','key_invalid','google_missing','google_expired'].includes(error.code)) $('setup-details').open = true;
    $('global-error').scrollIntoView({block:'nearest'});
  }
  function clearError() { $('global-error').hidden = true; retryAction = null; }
  function setBusy(value) {
    busy = value;
    const locked = value || Boolean(job);
    for (const button of document.querySelectorAll('button')) {
      if (!['confirm-cancel','confirm-action','dismiss-error','retry'].includes(button.id)) button.disabled = locked;
    }
    for (const input of document.querySelectorAll('input,select')) input.disabled = locked;
    if (draft) updateDependencies();
  }
  async function perform(action, retry) {
    if (busy) return;
    clearError(); setBusy(true);
    try { await action(); } catch (error) { showError(error,retry === undefined ? () => perform(action) : retry); }
    finally { setBusy(false); }
  }
  function resourceError() {
    const issue = state.resource_errors?.find(item => !['google_missing','key_missing'].includes(item.code));
    if (issue) showError(issue,() => refresh());
  }
  function fillOptions(select, items, placeholder, chosen = '') {
    select.replaceChildren(new Option(placeholder,''));
    for (const item of items) {
      const option = new Option(item.label,String(item.id));
      option.disabled = Boolean(item.disabled);
      select.add(option);
    }
    if (chosen && !items.some(item => String(item.id) === chosen)) select.add(new Option('Selezione non più disponibile',chosen));
    select.value = chosen;
  }
  function updateConnections() {
    const keyText = {missing:'Da collegare',configured:'Configurata',valid:'Collegato',invalid:'Chiave non valida',unavailable:'Non disponibile'};
    const googleText = {missing:'Da collegare',configured:'Da verificare',valid:'Collegato',expired:'Da ricollegare',unavailable:'Non disponibile'};
    for (const [id, value, text, prefix] of [['key-status',state.connection.key,keyText,'SenseCraft'],['google-status',state.connection.google,googleText,'Google']]) {
      $(id).textContent = `${prefix}: ${text[value] || 'Da verificare'}`;
      $(id).className = `status-chip ${value === 'valid' ? 'good' : 'warn'}`;
    }
    if (['missing','invalid'].includes(state.connection.key) || ['missing','expired'].includes(state.connection.google)) $('setup-details').open = true;
    $('page-status').textContent = state.connection.page === 'existing' ? 'Destinazione: pagina privata esistente' : 'Destinazione: nuova pagina privata';
    $('page-explanation').textContent = state.connection.page === 'existing' ? 'La prossima pubblicazione aggiornerà la pagina privata già collegata.' : 'Una pagina privata verrà creata soltanto dopo la conferma di pubblicazione.';
    fillOptions($('device'),state.devices.map(item => ({id:item.id,label:`${item.name} · ${item.resolution || item.model || 'profilo sconosciuto'}${item.compatible ? '' : ' · non compatibile'}${item.online === false ? ' · offline' : ''}`,disabled:!item.compatible})),'Seleziona un display',selectedDevice);
    const importChoice = $('import-page').value;
    fillOptions($('import-page'),state.pages.map(item => ({id:item.id,label:item.name})),'Seleziona una pagina',importChoice);
    fillOptions($('agenda-page'),state.pages.filter(item => item.agenda).map(item => ({id:item.id,label:item.name})),'Seleziona una pagina agenda',$('agenda-page').value);
    $('recovery-panel').hidden = !state.publication.recover_available && !state.publication.pending;
    $('recover').hidden = !state.publication.recover_available;
    $('recovery-message').textContent = state.publication.pending ? `Pubblicazione interrotta: ${phases[state.publication.phase] || 'da completare'}. Riprendi con gli stessi valori tramite «Salva e pubblica».` : 'Puoi ripristinare localmente l’ultima configurazione pubblicata; la pagina remota resta invariata.';
    if (state.publication.published_at && !$('published-state').dataset.current) $('published-state').textContent = `Ultimo successo verificato: ${new Intl.DateTimeFormat('it',{dateStyle:'short',timeStyle:'short'}).format(new Date(state.publication.published_at * 1000))}. Configurazione disponibile per il ripristino locale.`;
    else if (state.publication.recover_available && !$('published-state').dataset.current) $('published-state').textContent = 'Una configurazione pubblicata in precedenza è disponibile per il ripristino.';
    if (state.publication.uncertain_uploads) {
      failedAction ||= () => openPublish();
      showError({code:'uncertain_upload'});
    }
  }
  function seedMappings() { for (const item of draft.calendars) mappings.set(item.id,M.clone(item)); }
  function updateDraft() {
    const current = M.fingerprint(draft,selectedDevice), dirty = current !== saved;
    $('draft-state').textContent = dirty ? 'Modifiche non salvate' : 'Impostazioni locali salvate';
    $('draft-dot').classList.toggle('dirty',dirty);
    if (previewFingerprint) $('preview-state').textContent = previewLoading ? 'Caricamento dell’immagine…' : current === previewFingerprint ? 'Anteprima dei valori correnti.' : 'Anteprima precedente: genera di nuovo per vedere le modifiche.';
    if (!dirty) $('save-state').textContent = 'I valori locali sono salvati. La pubblicazione è un’azione separata.';
    else $('save-state').textContent = 'Le modifiche restano in questo pannello finché non le salvi.';
    $('calendar-count').textContent = `${draft.calendars.length} / 10`;
    $('city-current').textContent = `Città selezionata: ${draft.city} · ${draft.timezone}`;
    updateDependencies();
  }
  function updateDependencies() {
    const deps = M.dependencies(draft);
    const locked = busy || Boolean(job);
    for (const field of ['cadence','specialDates','hemisphere','carnivalRule']) $(field).disabled = locked || !deps[field];
    $('automatic-options').classList.toggle('inactive',!deps.cadence);
    $('mode').disabled = locked || !draft.autoDark;
    $('fallback-field').hidden = !draft.autoDark;
    $('theme-hint').textContent = deps.theme ? 'Scegli il tuo sfondo. Le miniature seguono il modo chiaro o scuro selezionato.' : 'Gli sfondi cambiano automaticamente. Passa a «Manuale» per scegliere un tema; la scelta precedente resta memorizzata.';
    for (const radio of document.querySelectorAll('input[name=theme]')) radio.disabled = locked || !deps.theme;
    for (const row of document.querySelectorAll('.calendar-item')) {
      const selected = draft.calendars.some(item => item.id === row.dataset.calendar);
      row.querySelector('input[type=checkbox]').disabled = locked || (!selected && draft.calendars.length >= 10);
      const initialsInput = row.querySelector('.calendar-initials');
      const colorInput = row.querySelector('.calendar-color');
      initialsInput.disabled = locked || !selected || ['none','dot_only'].includes(draft.markerMode);
      colorInput.disabled = locked || !selected || draft.markerMode === 'none';
    }
  }
  function writeForm() {
    for (const field of document.querySelectorAll('[data-setting]')) {
      if (field.type === 'radio') field.checked = draft[field.name] === field.value;
      else if (field.type === 'checkbox') field.checked = draft[field.id];
      else field.value = draft[field.id];
    }
    for (const radio of document.querySelectorAll('[name=lighting]')) radio.checked = radio.value === (draft.autoDark ? 'solar' : draft.mode);
    $('intensity-range').value = draft.intensity;
    $('city-search').value = '';
    seedMappings(); renderCalendars(); renderThemes(); updateDraft();
  }
  function renderCalendars() {
    const query = $('calendar-search').value.toLocaleLowerCase('it');
    const records = [...state.calendars];
    for (const selected of draft.calendars) if (!records.some(item => String(item.id) === selected.id)) records.unshift({...selected,missing:true});
    $('calendar-list').replaceChildren();
    let visible = 0;
    records.forEach((record,index) => {
      const id = String(record.id), selected = draft.calendars.some(item => item.id === id);
      if (!String(record.name).toLocaleLowerCase('it').includes(query)) return;
      visible++;
      const row = make('div',`calendar-item${selected ? ' selected' : ''}`); row.dataset.calendar = id;
      const label = make('label','calendar-label'), checkbox = make('input'); checkbox.type = 'checkbox'; checkbox.checked = selected;
      const name = make('span','calendar-name',record.name);
      name.append(make('small','',record.missing ? 'Non più disponibile · rimuovi o aggiorna la lista' : `${record.access_role === 'owner' ? 'Proprio' : 'Sottoscritto o condiviso'}${record.primary ? ' · principale' : ''}`));
      label.append(checkbox,name);
      const top = make('div','calendar-row'); top.append(label); row.append(top);
      let mapping = mappings.get(id) || {id,name:record.name,initials:M.initials(record.name),color:palette[index % palette.length]};
      mapping.name = record.name; mappings.set(id,mapping);
      const mappingArea = make('div','calendar-mapping'); mappingArea.hidden = !selected;
      const initialField = make('div','field'), colorField = make('div','field');
      const initials = make('input','calendar-initials'); initials.type = 'text'; initials.maxLength = 8; initials.value = mapping.initials; initials.id = `initials-${index}`; initials.setAttribute('aria-label',`Iniziali di ${record.name}`);
      const initialsLabel = make('label','','Iniziali (1–4)'); initialsLabel.htmlFor = initials.id;
      const color = make('input','calendar-color'); color.type = 'color'; color.value = mapping.color; color.id = `color-${index}`; color.setAttribute('aria-label',`Colore di ${record.name}`);
      const colorLabel = make('label','','Colore'); colorLabel.htmlFor = color.id;
      initialField.append(initialsLabel,initials); colorField.append(colorLabel,color); mappingArea.append(initialField,colorField); row.append(mappingArea);
      checkbox.addEventListener('change',() => {
        if (checkbox.checked && draft.calendars.length >= 10) { checkbox.checked = false; return; }
        if (checkbox.checked) draft.calendars.push(M.clone(mapping));
        else draft.calendars = draft.calendars.filter(item => item.id !== id);
        row.classList.toggle('selected',checkbox.checked); mappingArea.hidden = !checkbox.checked;
        clearValidation(); updateDraft(); announce(`${draft.calendars.length} calendari selezionati.`);
      });
      for (const [input,field] of [[initials,'initials'],[color,'color']]) input.addEventListener('input',() => {
        mapping[field] = input.value;
        const entry = draft.calendars.find(item => item.id === id); if (entry) entry[field] = input.value;
        clearValidation(); updateDraft();
      });
      $('calendar-list').append(row);
    });
    $('calendar-empty').hidden = visible > 0;
    $('calendar-empty').textContent = query ? 'Nessun calendario corrisponde alla ricerca.' : state.connection.google === 'valid' ? 'Nessun calendario disponibile. Aggiorna la lista.' : 'Collega Google per scegliere i calendari.';
    updateDependencies();
  }
  function renderThemes() {
    const isDark = draft.mode === 'dark';
    $('theme-gallery').replaceChildren();
    $('theme-name').textContent = `· ${M.theme(draft.theme).label}`;
    for (const key of state.capabilities.themes) {
      const theme = M.theme(key,isDark);
      const label = make('label','theme-option'); label.hidden = themeFilter !== 'all' && theme.group !== themeFilter;
      const input = make('input'); Object.assign(input,{type:'radio',name:'theme',value:key,checked:draft.theme === key}); input.setAttribute('aria-label',theme.label);
      const tile = make('span','theme-tile');
      if (theme.asset) { const image = make('img'); image.src = theme.asset; image.alt = ''; image.loading = 'lazy'; tile.append(image); }
      else tile.append(make('span',`theme-surface ${key === 'dark' ? 'dark' : ''}`));
      tile.append(make('span','theme-label',theme.label)); label.append(input,tile);
      input.addEventListener('change',() => { draft.theme = key; $('theme-name').textContent = `· ${theme.label}`; updateDraft(); });
      $('theme-gallery').append(label);
    }
    updateDependencies();
  }
  function clearValidation() {
    for (const input of document.querySelectorAll('[aria-invalid]')) input.removeAttribute('aria-invalid');
    $('calendar-error').hidden = true;
  }
  function validPayload() {
    clearValidation();
    const issues = M.validate(draft,selectedDevice,state);
    if (issues.length) {
      for (const issue of issues) {
        if (issue.field === 'calendars') { $('calendar-error').textContent = issue.message; $('calendar-error').hidden = false; }
        else $(issue.field)?.setAttribute('aria-invalid','true');
      }
      $('error-text').textContent = issues.map(issue => issue.message).join(' ');
      $('retry').hidden = true; $('uncertain-recovery').hidden = true; $('global-error').hidden = false;
      const target = issues[0].field === 'calendars' ? $('calendar-list').querySelector('input:not(:disabled)') || $('refresh-calendars') : $(issues[0].field);
      target?.focus(); announce(issues[0].message); return null;
    }
    return {agenda:M.preferences(draft),device_id:selectedDevice};
  }
  async function refresh(initial = false) {
    const response = await request('/api/state'); state = response;
    if (initial || !draft) {
      draft = M.preferences(state.agenda); selectedDevice = state.device_id || '';
      saved = M.fingerprint(draft,selectedDevice);
      writeForm();
      $('workspace').hidden = false; $('loading').hidden = true;
    } else { renderCalendars(); updateDraft(); }
    updateConnections(); resourceError();
  }
  function confirmAction(title,copy,label,action) {
    if (busy || $('confirmation').open) return;
    lastFocus = document.activeElement; confirmation = action;
    $('confirmation-title').textContent = title; $('confirmation-copy').textContent = copy; $('confirm-action').textContent = label;
    $('confirmation').showModal(); $('confirm-cancel').focus();
  }
  function closeDialog() { confirmation = null; $('confirmation').close(); lastFocus?.focus(); }
  function openPublish(payload = null) {
    const current = payload || validPayload(); if (!current) return;
    const device = state.devices.find(item => String(item.id) === current.device_id);
    confirmAction('Salva e pubblica',`Salverai le impostazioni sul computer e ${state.connection.page === 'existing' ? 'aggiornerai la pagina privata' : 'creerai una pagina privata'} su SenseCraft.\n\nDisplay: ${device?.name || 'selezionato'}\nCalendari: ${current.agenda.calendars.length}\n\nVerrà richiesto l’aggiornamento del display e verificato lo stato remoto.`, 'Salva e pubblica',() => startJob('publish',current));
  }
  async function startJob(kind,payload) {
    const action = () => kind === 'publish' ? openPublish(payload) : perform(() => startJob(kind,payload));
    failedAction = action;
    const response = await request(`/api/${kind}`,kind === 'publish' ? {...payload,confirm:true} : payload);
    if (!/^[a-f0-9]+$/.test(response.job_id)) throw {code:'protocol'};
    job = {id:response.job_id,kind,payload};
    $('job-panel').hidden = false; $('job-status').textContent = kind === 'publish' ? 'Pubblicazione privata in corso…' : 'Generazione dell’anteprima…';
    await pollJob();
  }
  async function pollJob() {
    const current = job;
    try {
      for (;;) {
        const response = await request(`/api/jobs/${current.id}`);
        $('job-status').textContent = `${current.kind === 'publish' ? 'Pubblicazione' : 'Anteprima'} · ${phases[response.phase] || 'In corso'}`;
        if (response.status === 'failed') {
          $('job-status').textContent = 'Operazione interrotta. Il progresso recuperabile è conservato.';
          job = null;
          await refresh();
          showError(response.error || {code:'internal'},response.error?.code === 'uncertain_upload' ? null : failedAction);
          return;
        }
        if (response.status === 'succeeded') {
          $('job-panel').hidden = true; job = null;
          if (current.kind === 'preview') {
            const url = response.result?.preview_url;
            if (!/^\/api\/artifacts\/[a-f0-9]+\.png$/.test(url || '')) throw {code:'protocol'};
            previewLoading = true;
            $('preview-image').src = url;
            $('preview-image').hidden = false; $('preview-placeholder').hidden = true;
            previewFingerprint = M.fingerprint(current.payload.agenda,current.payload.device_id);
            $('preview-state').textContent = 'Caricamento dell’immagine…';
            announce('Anteprima generata senza salvare le impostazioni o la pagina.');
          } else {
            saved = M.fingerprint(current.payload.agenda,current.payload.device_id);
            const result = response.result || {};
            $('published-state').dataset.current = 'true';
            $('published-state').textContent = result.page_exact_readback && result.assignment_verified && result.snapshot_verified ? `Pagina, assegnazione e snapshot verificati · ${new Intl.DateTimeFormat('it',{hour:'2-digit',minute:'2-digit'}).format(new Date())}. L’osservazione fisica del display resta da verificare.` : 'Pubblicazione completata; controlla lo stato remoto. L’osservazione fisica del display resta da verificare.';
            announce('Configurazione salvata e pubblicazione privata completata.');
            await refresh();
          }
          updateDraft(); return;
        }
        if (!['queued','running'].includes(response.status)) throw {code:'protocol'};
        await new Promise(resolve => setTimeout(resolve,1000));
      }
    } catch (error) {
      if (job) {
        $('job-status').textContent = 'Il pannello ha perso il contatto con l’operazione. Verifica lo stesso tentativo senza avviarne un altro.';
        showError(error,() => perform(pollJob));
      } else throw error;
    }
  }
  async function saveLocal() {
    const payload = validPayload(); if (!payload) return;
    await perform(async () => {
      const result = await request('/api/save',payload);
      saved = M.fingerprint(result.agenda,result.device_id); updateDraft();
      announce('Impostazioni salvate localmente. Nessuna pubblicazione eseguita.');
    });
  }
  async function searchCities() {
    const query = $('city-search').value.trim(), generation = ++cityGeneration;
    $('city-results').replaceChildren(); $('city-results').hidden = true;
    if (query.length < 2) { $('city-status').textContent = 'Inserisci almeno due caratteri.'; return; }
    $('city-status').textContent = 'Ricerca in corso…';
    try {
      const response = await request(`/api/cities?q=${encodeURIComponent(query)}&language=it`);
      if (generation !== cityGeneration) return;
      for (const city of response.cities) {
        const button = make('button','city-result'); button.type = 'button';
        const text = make('span','',city.name); text.append(make('small','',[city.admin1,city.country,city.timezone].filter(Boolean).join(' · '))); button.append(text);
        button.disabled = busy;
        button.addEventListener('click',() => {
          if (busy) return;
          Object.assign(draft,{city:city.name,latitude:city.latitude,longitude:city.longitude,timezone:city.timezone});
          $('timezone').value = draft.timezone; $('city-search').value = city.name;
          $('city-results').hidden = true; $('city-status').textContent = 'Città e fuso aggiornati nella bozza.';
          clearValidation(); updateDraft(); $('city-search').focus();
        });
        $('city-results').append(button);
      }
      $('city-results').hidden = !response.cities.length;
      $('city-status').textContent = response.cities.length ? `${response.cities.length} risultati. Scegli la tua città.` : 'Nessuna città trovata. Prova un nome diverso.';
    } catch (error) {
      if (generation === cityGeneration) $('city-status').textContent = errors[error.code] || errors.network;
    }
  }
  async function startGoogle(reconnect) {
    await perform(async () => {
      const result = await request('/api/google/start',{reconnect});
      if (result.status === 'valid') { await refresh(); announce('Il collegamento Google esistente è valido.'); return; }
      $('oauth-guide').hidden = false;
      $('oauth-instructions').textContent = result.status === 'authorize' ? 'Apri l’autorizzazione Google con il pulsante qui sotto. Al termine torna a questo pannello e verifica il collegamento. Il tentativo resta valido per 10 minuti.' : 'Completa il collegamento nell’editor nativo SenseCraft, poi importa la connessione dalla pagina privata salvata.';
      let url;
      try { url = new URL(result.authorize_url || result.native_url); } catch { throw {code:'protocol'}; }
      if (url.protocol !== 'https:' || !['accounts.google.com','sensecraft.seeed.cc'].includes(url.hostname) || url.username || url.password) throw {code:'protocol'};
      $('oauth-link').href = url.href;
      $('oauth-link').textContent = result.authorize_url ? 'Autorizza con Google ↗' : 'Apri SenseCraft ↗';
      announce('Il percorso di collegamento Google è pronto.');
    });
  }
  async function importGoogle() {
    if (!$('import-page').value) { showError({code:'validation'}); $('import-page').focus(); return; }
    await perform(async () => { await request('/api/google/import',{page_id:$('import-page').value}); await refresh(); $('oauth-guide').hidden = true; announce('Collegamento Google importato e verificato.'); });
  }
  function recoverUploads() {
    confirmAction('Gestisci upload incerto','La risposta di un upload è andata persa: un file potrebbe essere già presente su SenseCraft.\n\nConfermando rimuovi solo il blocco locale dei tentativi incerti. Un file senza riferimento potrebbe restare nel tuo account. Le risorse completate e la pagina sono conservate. Potrai poi riprovare l’anteprima o confermare nuovamente la pubblicazione.', 'Sblocca il tentativo',() => perform(async () => {
      await request('/api/uploads/recover',{confirm:true});
      await refresh(); announce('Blocco locale rimosso. Puoi riprendere il tentativo.');
      if (failedAction) { retryAction = failedAction; $('error-text').textContent = 'Upload incerto gestito. Riprova lo stesso tentativo; per pubblicare verrà richiesta di nuovo la conferma.'; $('retry').hidden = false; $('uncertain-recovery').hidden = true; $('global-error').hidden = false; }
    }));
  }
  for (const field of document.querySelectorAll('[data-setting]')) field.addEventListener('input',() => {
    if (!draft || busy) return;
    if (field.type === 'radio') { if (field.checked) draft[field.name] = field.value; }
    else if (field.type === 'checkbox') draft[field.id] = field.checked;
    else draft[field.id] = field.type === 'number' ? (field.value === '' ? null : Number(field.value)) : field.value;
    if (field.id === 'intensity' && Number.isFinite(draft.intensity)) $('intensity-range').value = draft.intensity;
    if (field.id === 'mode') renderThemes();
    clearValidation(); updateDraft();
  });
  for (const radio of document.querySelectorAll('[name=lighting]')) radio.addEventListener('change',() => {
    if (busy) return;
    draft.autoDark = radio.value === 'solar'; if (!draft.autoDark) draft.mode = radio.value;
    $('mode').value = draft.mode; renderThemes(); updateDraft();
  });
  $('intensity-range').addEventListener('input',() => { if (busy) return; draft.intensity = Number($('intensity-range').value); $('intensity').value = draft.intensity; clearValidation(); updateDraft(); });
  $('device').addEventListener('change',() => { selectedDevice = $('device').value; clearValidation(); updateDraft(); });
  $('calendar-search').addEventListener('input',() => renderCalendars());
  $('city-search').addEventListener('input',() => { ++cityGeneration; clearTimeout(cityTimer); cityTimer = setTimeout(searchCities,400); });
  $('city-search').addEventListener('keydown',event => { if (event.key === 'Enter') { event.preventDefault(); clearTimeout(cityTimer); searchCities(); } if (event.key === 'Escape') $('city-results').hidden = true; });
  $('find-city').addEventListener('click',() => { clearTimeout(cityTimer); searchCities(); });
  for (const button of document.querySelectorAll('[data-theme-filter]')) button.addEventListener('click',() => {
    themeFilter = button.dataset.themeFilter;
    for (const other of document.querySelectorAll('[data-theme-filter]')) other.setAttribute('aria-pressed',String(other === button));
    renderThemes();
  });
  $('settings').addEventListener('submit',event => event.preventDefault());
  $('save').addEventListener('click',saveLocal);
  $('preview').addEventListener('click',() => { const payload = validPayload(); if (payload) perform(() => startJob('preview',payload),() => perform(() => startJob('preview',payload))); });
  $('publish').addEventListener('click',() => openPublish());
  $('confirm-cancel').addEventListener('click',closeDialog);
  $('confirmation').addEventListener('cancel',event => { event.preventDefault(); closeDialog(); });
  $('confirm-action').addEventListener('click',() => { const action = confirmation; closeDialog(); if (action) { if ($('confirmation-title').textContent === 'Salva e pubblica') perform(action,() => failedAction?.()); else action(); } });
  $('dismiss-error').addEventListener('click',clearError);
  $('retry').addEventListener('click',() => { const action = retryAction; clearError(); if (action) action(); });
  $('uncertain-recovery').addEventListener('click',recoverUploads);
  $('refresh-state').addEventListener('click',() => perform(() => refresh()));
  $('refresh-calendars').addEventListener('click',() => perform(async () => { state.calendars = (await request('/api/calendars')).calendars; renderCalendars(); announce('Lista calendari aggiornata.'); }));
  $('refresh-pages').addEventListener('click',() => perform(async () => { state.pages = (await request('/api/pages')).pages; updateConnections(); announce('Lista pagine aggiornata.'); }));
  $('select-page').addEventListener('click',() => {
    if (!$('agenda-page').value) { showError({code:'validation'}); $('agenda-page').focus(); return; }
    perform(async () => { await request('/api/page',{page_id:$('agenda-page').value}); await refresh(); announce('Destinazione locale aggiornata. Pagina remota invariata.'); });
  });
  $('validate-key').addEventListener('click',() => {
    const key = $('api-key').value.trim();
    if (!key) { $('api-key').setAttribute('aria-invalid','true'); showError({code:'key_missing'}); $('api-key').focus(); return; }
    perform(async () => { try { await request('/api/key',{api_key:key}); await refresh(); announce('API Key verificata e salvata localmente.'); } finally { $('api-key').value = ''; } },null);
  });
  $('connect-google').addEventListener('click',() => startGoogle(false));
  $('reconnect-google').addEventListener('click',() => startGoogle(true));
  $('import-google').addEventListener('click',importGoogle);
  $('check-google').addEventListener('click',() => perform(() => refresh()));
  $('recover').addEventListener('click',() => confirmAction('Ripristina configurazione','Sostituirai la bozza e le impostazioni locali con l’ultima configurazione pubblicata con successo. La pagina remota e il display non vengono modificati.', 'Ripristina locale',() => perform(async () => {
    const result = await request('/api/recover',{}); draft = M.preferences(result.agenda); selectedDevice = String(result.device_id);
    saved = M.fingerprint(draft,selectedDevice); mappings = new Map(); writeForm(); await refresh(); announce('Ultima configurazione pubblicata ripristinata localmente.');
  })));
  $('preview-image').addEventListener('load',() => { previewLoading = false; if (draft) updateDraft(); });
  $('preview-image').addEventListener('error',() => { previewLoading = false; $('preview-image').hidden = true; $('preview-placeholder').hidden = false; $('preview-state').textContent = 'Immagine non disponibile. Genera nuovamente l’anteprima.'; previewFingerprint = null; showError({code:'not_found'}); });
  window.addEventListener('beforeunload',event => { if (draft && (M.fingerprint(draft,selectedDevice) !== saved || busy || job)) { event.preventDefault(); event.returnValue = ''; } });
  if (typeof Intl.supportedValuesOf === 'function') for (const timezone of Intl.supportedValuesOf('timeZone')) $('timezone-options').append(new Option(timezone,timezone));
  perform(async () => {
    await refresh(true);
    if (state.active_job) {
      const active = state.active_job;
      draft = M.preferences(active.agenda); selectedDevice = String(active.device_id);
      writeForm();
      job = {id:active.job_id,kind:active.kind,payload:{agenda:M.preferences(active.agenda),device_id:selectedDevice}};
      failedAction = () => active.kind === 'publish' ? openPublish(job?.payload || {agenda:M.preferences(active.agenda),device_id:String(active.device_id)}) : perform(() => startJob('preview',{agenda:M.preferences(active.agenda),device_id:String(active.device_id)}));
      $('job-panel').hidden = false;
      await pollJob();
    }
    const params = new URLSearchParams(location.search);
    if (params.get('google') === 'connected') { announce('Collegamento Google completato.'); history.replaceState(null,'',location.pathname); }
  },() => perform(() => refresh(true)));
})();
