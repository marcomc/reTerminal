# Ricostruire l’agenda SenseCraft

Runbook per un agente che deve ripristinare o ricreare Google Calendar Today
nel profilo E1002 già implementato. Baseline: **30 settembre 2026**, dopo le correzioni di batteria
dark, eventi ancora attivi, orario di fine, capacità verticale e selezione
estesa dei calendari. Questa guida è indipendente dalla costruzione del MCP.

## Indice

- [Risultato da riprodurre](#risultato-da-riprodurre)
- [Materiale necessario](#materiale-necessario)
- [Procedura di ripristino](#procedura-di-ripristino)
- [Installazione con risorse nuove](#installazione-con-risorse-nuove)
- [Configurazione e comportamento](#configurazione-e-comportamento)
- [API e recupero dagli errori](#api-e-recupero-dagli-errori)
- [Criteri di completamento](#criteri-di-completamento)
- [Impronte della baseline](#impronte-della-baseline)

## Risultato da riprodurre

```text
SenseCraft: pagina privata, gruppo dispositivo 800×480, dither 3
  └─ HTML caricato su OSS SenseCraft
       ├─ codice e riferimenti alle decorazioni senza dati dell’account
       ├─ configurazione privata nel fragment #config=… del layout
       └─ letture durante il rendering:
            calendario → API SenseCraft con sessione Google autorizzata
            batteria   → API SenseCraft con binding privato dispositivo/key
            alba/tramonto → Open-Meteo
```

Tutta la logica di layout, temi, lingue e modalità solare è nel documento HTML.
Gli script Python servono una volta per costruire, configurare e installare.
Dopo il deploy non occorre un processo locale, un servizio ospitato da noi o
uno scheduler. Ora ed eventi corrispondono all’ultimo rendering, non a un
orologio continuamente aggiornato sul pannello.

«Esattamente» significa stessi sorgenti, immagini, impostazioni e geometria.
Eventi, ora, dati solari e batteria restano live: i loro valori cambieranno.
La mappatura dei sei calendari della baseline si recupera dal backup privato;
nomi e identificativi non sono riportati qui.

## Materiale necessario

| Percorso | Ruolo |
| --- | --- |
| `templates/google-calendar-today/src/agenda.html` | HTML/CSS/JS autorevole e fixture development |
| `templates/google-calendar-today/assets/` | 24 coppie light/dark, manifest SHA-256 e miniatura fittizia |
| `templates/google-calendar-today/scripts/` | Helper API versionati |
| `sensecraft.local.json` | Preferenze persistenti e mapping calendari; ignorato |
| `sensecraft.connection.local.json` | Key, sessione Google, ID risorse; ignorato, permessi 0600 |
| `.private/native-agenda/` | Candidati, cache, preview e backup rigenerabili |

Servono Python 3 con `zoneinfo`/database IANA, Node.js per i controlli,
account autorizzato, Google collegato e dispositivo associato.
La cancellazione di `.private/` non deve perdere preferenze o connessioni valide.
Le vecchie configurazioni in quella directory sono backup storici.

Il loader migra il precedente JSON unificato. La key esplicitamente esportata
in `SENSECRAFT_API_KEY` ha precedenza sulla connessione locale; `.env` è una
sorgente legacy letta senza esecuzione shell. Non stampare i valori privati.

## Procedura di ripristino

Il percorso grafico consigliato legge i due JSON persistenti, genera una preview
production e applica **Salva e pubblica** con readback di pagina/assegnazione e
snapshot. Produce anche `agenda-upload.html` e `persisted-private.json`, così
`verify-live.py` può verificare lo stesso layout riconciliato. Il seguente percorso
CLI resta disponibile; non eseguirlo contemporaneamente al configuratore.

Dalla root, con autorizzazione alle scritture dell'account:

1. Leggere `AGENTS.md`, controllare Git e conservare modifiche estranee.
2. Recuperare sorgenti e i due JSON persistenti da backup privato.
   Verificare gli hash degli asset; non sovrascrivere una configurazione valida.
3. Validare e leggere le risorse correnti usando la connessione privata.
   Riconciliare i calendari selezionati con la lista Google fresca.

   ```sh
   python3 templates/google-calendar-today/scripts/configure.py --check-only
   node templates/google-calendar-today/scripts/check.js
   ```

4. Compilare production e controllare anche l'artefatto generato:

   ```sh
   python3 templates/google-calendar-today/scripts/build.py --production
   node templates/google-calendar-today/scripts/check.js --production
   ```

   La build carica PNG e HTML mancanti dalla cache, genera i candidati privato
   e portabile e il rapporto. Effettua upload persistenti, ma non salva la pagina.
   Senza `--production` conserva le fixture: non installarle sul dispositivo.

5. Il percorso page-only di `persist.py` fa backup della pagina fresca,
   riconcilia il nuovo URL HTML conservando metadati/geometria dell'editor,
   genera una preview, salva e legge nuovamente la pagina privata.
   Non legge, ricrea o aggiorna template riutilizzabili.

   ```sh
   python3 templates/google-calendar-today/scripts/persist.py --preview-only
   # Inspect .private/native-agenda/production-before-save.png before saving.
   python3 templates/google-calendar-today/scripts/persist.py --deploy
   python3 templates/google-calendar-today/scripts/verify-live.py
   ```

   Il `stageSize` dell'editor può differire dal gruppo dispositivo `800×480`.
   La batteria è già nell'HTML: eliminare soltanto l'eventuale `native-battery`
   legacy. Prima del salvataggio ispezionare la preview production: titoli,
   orari, marker, contrasto dark, batteria trasparente e spazio verticale.

6. Confrontare pagina, assegnazione e snapshot contro `persisted-private.json`,
   scritto soltanto dopo il readback esatto della pagina. Un refresh accettato non prova
   lo schermo fisico. La verifica normale usa i calendari selezionati;
   la prova su dieci calendari è opzionale (`--ten-calendars`).

Se `.private/` viene rimossa, rigenerare da sorgenti/asset e dai due JSON;
il configuratore riusa la cache duratura della connessione. Gli helper CLI
legacy possono richiedere nuovi upload se la loro cache rigenerabile manca.

## Installazione con risorse nuove

Usare il [configuratore locale](../templates/google-calendar-today/configurator/README.md)
per setup e nuove installazioni:

```sh
python3 templates/google-calendar-today/configurator
```

La key viene validata e salvata nella connessione locale. Il pannello riusa Google
oppure guida nell'OAuth nativo e nell'importazione della connessione dalla pagina
privata salvata. Consente la scelta di calendari/dispositivo e crea la pagina
privata alla conferma **Salva e pubblica**; non dipende da template riutilizzabili.
La creazione `{pages: [...]}` è derivata dal client e coperta da fixture; lo stato
della prova live è nelle API notes. Il ritorno OAuth completo al loopback resta
una verifica distinta. Gli helper sotto restano il percorso manuale avanzato.

1. Associare il dispositivo tramite SenseCraft, poi identificarlo tramite
   `GET /api/v2/user/device/list`; il modello è in `board.type`.
2. Creare la pagina privata nel percorso nativo finché il payload completo
   di creazione non è validato; non inventare un contratto.
3. Collegare Google via OAuth SenseCraft e ottenere la sessione autorizzata
   dell'installatore. Non riutilizzare sessioni di altre persone.
4. Preparare la configurazione senza sovrascrivere file esistenti:

   ```sh
   cp sensecraft.local.example.json sensecraft.local.json
   cp sensecraft.connection.local.example.json sensecraft.connection.local.json
   chmod 600 sensecraft.local.json sensecraft.connection.local.json
   ```

   Compilare privatamente key, sessione, ID pagina/dispositivo e mapping.
   Gli esempi non sono un account pronto. La sessione può scadere o essere revocata.
5. Compilare/installare/verificare seguendo la procedura sopra.

Il template riutilizzabile è stato ritirato, conservando pagina privata,
Google e assegnazione del dispositivo. Non serve per questo percorso.
Il marketplace non completa automaticamente OAuth/mapping dell'HTML.

## Configurazione e comportamento

Per la stessa installazione, **`sensecraft.local.json` contiene le preferenze autorevoli**. Per una nuova
installazione, conservare il comportamento sotto e cambiare soltanto le scelte
dell’utente e i binding privati.

|Elemento|Baseline e opzioni implementate|
|---|---|
|Lingua|`it`; disponibili `it`, `en`, `fr`, `de`, `es` per etichette/date, senza tradurre i titoli degli eventi.|
|Località|Default dimostrativo `Europe/Rome`, Roma, `41.9`, `12.5`; configurare città, coordinate e fuso reali privatamente.|
|Visibilità|`showTimezone`, `showSunrise`, `showSunset`, `showMoon`, `showBattery`: tutti true nella baseline; l’orologio è sempre mostrato.|
|Calendari|Sei nella baseline; da 1 a 10 record distinti `{id, name, initials, color}`. Iniziali 1–4 caratteri; colore `#RRGGBB`.|
|Marker|`initials_and_dot`; alternative `initials_only`, `dot_only`, `none`. Il titolo recupera lo spazio dei marker nascosti.|
|Sfondo|`backgroundMode=automatic`, `cadence=months`, `specialDates=true`, `intensity=50`. Intensità intera 0–100: opacità del velo `1 - intensity/100`.|
|Modalità|`autoDark=true`, `mode=light`, `theme=white`. Alba/tramonto determinano il dark al rendering; assenza di dati solari usa la modalità manuale.|
|Stagioni|`hemisphere=auto`: segue la latitudine; alternative `north`, `south`. Stagioni meteorologiche, cambio a marzo/giugno/settembre/dicembre.|
|Festività|Befana 6 gennaio, Pasqua domenica, Halloween 31 ottobre, Natale 24–26 dicembre; `carnivalRule=shrove_tuesday`, Pasqua meno 47 giorni, oppure `none`. Override solo in automatico.|
|Temi manuali|`white`, `dark`, `floral`, `unicorn`, `lgbtq`, `spring`, `summer`, `autumn`, `winter`, `month-01`…`month-12`, `easter`, `christmas`, `epiphany`, `halloween`, `carnival`.|
|Titoli|`titleSize=28`, `minTitleSize=25`: misura del testo, riduzione solo del titolo, poi sfumatura di coda; singola riga.|
|Compleanni|`excludeBirthdays=true`: filtro euristico sui titoli riconoscibili degli eventi all-day.|

Esempi di configurazione senza salvataggio:

```sh
python3 templates/google-calendar-today/scripts/configure.py \
  --set markerMode=initials_only --set showTimezone=false --set intensity=37 --preview
python3 templates/google-calendar-today/scripts/configure.py --city Roma --city-index 1 --preview
```

La geocodifica usa Open-Meteo, seleziona il risultato indicato e imposta nome,
coordinate e timezone. Senza `--preview` o `--save`, le modifiche vanno in
`config-draft.json`; il draft non viene promosso automaticamente. Per applicarlo,
ripetere le opzioni con `--save` o promuovere esplicitamente il file privatamente.

### Layout e regole da conservare

- Header: titolo rosso maiuscolo 23 px, giorno della settimana, data
  `DD-MM-YYYY`, ora; niente «oggi» davanti al giorno. Seconda riga compatta
  con alba, tramonto, fase lunare e fuso opzionali. Batteria a destra, nello
  stesso spazio orizzontale dell’orologio (88 px).
- Batteria: lettura live, fondo trasparente, testo/icona con colore del tema
  e sottile contorno; `0%` valido, valore assente/non valido `—`.
- Eventi: oggi e date successive restituite dall’API, ammesse finché lo spazio
  consente righe complete; cancellati esclusi. Conservare
  eventi iniziati ma non terminati; rimuoverli quando `end.dateTime <= now`.
  Gli eventi notturni ancora attivi vengono raggruppati sotto oggi. Se l’ora
  di fine manca, il fallback di scadenza è l’inizio; timestamp invalidi esclusi.
- All-day: confronti su date civili con fine esclusiva; mantenere quelli
  plurigiornalieri attivi. Deduplicare per calendario, evento e inizio occorrenza.
  Ordinare per data e ora, con all-day prima degli eventi temporizzati.
- Righe: passo 44 px, inizio temporizzato fisso 28 px, fine sotto a 13 px
  e colore attenuato, titolo accanto, marker allineato a destra. In dark le
  iniziali hanno contorno bianco e il punto un bordo contrastante.
- Area eventi: y=88–461 su 480 px. Misurare altezza disponibile ed elementi;
  nessun limite numerico fisso di appuntamenti. Inserire un’intestazione di
  giorno futuro solo se entra almeno una riga. Footer compatto con il numero
  di appuntamenti rimasti fuori dall’area visibile.
- Luna: fase e crescente/calante indicativi, calcolati sul mese sinodico medio;
  non sono effemeridi precise. Alba/tramonto anche nelle intestazioni future.
- Runtime: `load()` legge eventi, sole e batteria in parallelo e applica
  composizione e regole nel renderer SenseCraft. Il successivo refresh normale
  applica i cambi di data/tema/modalità. Intervallo osservato: 1800 secondi;
  leggere quello corrente, senza promettere una consegna a un istante esatto.

## API e recupero dagli errori

Base: `https://sensecraft-hmi-api.seeed.cc`. Account API: header **`api-key`**.
Per risposte JSON controllare stato HTTP e `code == 200`; un HTTP 200 può
contenere un errore applicativo. Le preview restituiscono bytes PNG.

|Passaggio|Richiesta e postcondizione|
|---|---|
|Upload|`POST /api/v1/oss/file/upload`, multipart `file`, `type=image\|document\|thumbnail`; usare `result.file_url`.|
|Calendari|`GET /api/v2/calendar/list?session_id=…`, con `api-key`; record in `result.calendarList`.|
|Eventi runtime|`GET /api/v2/calendar/events`, query `session_id`, `calendar_ids` separati da virgola, `type=2`, `time_zone`; `result.events`. HTML usa `credentials: "omit"`, senza key account per questa lettura.|
|Sole|`GET https://api.open-meteo.com/v1/forecast`, query `latitude`, `longitude`, `daily=sunrise,sunset`, `timezone`, `forecast_days=16`.|
|Batteria runtime|`GET /api/v1/user/device/iot_data/{deviceId}`, header `api-key`, `credentials: "omit"`; `result.battery.level`.|
|Preview|`POST /render/preview`, `{layout, resolution: "800x480", dither: 3, img_format: "png"}`.|
|Pagina|`GET /api/v2/user/page/detail?page_id=…`; salvare con `PUT /api/v2/user/page`, `{id, data: "JSON serializzato", thumbnail}`; leggere di nuovo e confrontare JSON.|
|Template riutilizzabile|Ritirato; non richiesto né aggiornato nel percorso privato.|
|Deploy pagina|`POST /api/v2/user/device/deploy`, `{mode: "refresh", page_ids: [ID], mac_addresses: [MAC]}`.|
|Assegnazione|`GET /api/v2/user/device/playlist?mac_address=…&type=all`; identificare la pagina tramite `source_page_id` oppure `id`.|
|Snapshot|`GET /api/v2/user/page/detail?page_id={entry.id}&kind=snapshot` se l’entry è uno snapshot; confrontare `data`, risoluzione e dither con il candidato.|

Le API qui sono quelle già osservate e provate per questa implementazione.
Consultare [API field notes](sensecraft-hmi-api.md) per provenienza e limiti
delle singole evidenze. Non occorre ripetere discovery per il percorso normale.

|Problema|Azione dell’agente|
|---|---|
|Errore locale dopo una scrittura|Leggere la risorsa prima di riprovare: una mutazione riuscita può omettere `result`. L’helper corretto usa `v.get('result')`.|
|Timeout su create/upload/save|Ricercare e confrontare lo stato privato risultante prima di ripetere; idempotenza upstream non provata.|
|Evento mancante|Confrontare `calendarId` con la selezione fresca e poi la capacità visiva; un evento può appartenere a un calendario non selezionato o essere sotto le righe visibili.|
|Eventi fuori intervallo|Filtrare nel consumer: `type=2` copre date future anche oltre il mese; `type=4` con millisecondi non ha un contratto `[start,end)` provato.|
|Production senza helper nuovi|Conservare il confine di stripping prima di `function batteryPercentage(` e controllare semantica su production; la sola sintassi non basta.|
|Editor salva un URL precedente|Rileggere e fare backup; riconciliare solo URL/binding richiesti preservando metadati; preview, save e snapshot readback. Se continua, coordinarsi con chi usa l’editor.|
|Tentazione di tornare ai componenti nativi|Usare il percorso HTML già provato: i transform nativi non attendono Promise; opacità immagine/SVG nativi non hanno fornito la composizione necessaria.|
|Template in revisione|Riportare lo stato osservato. Il deploy della pagina non richiede approvazione marketplace; l’agente non può approvare la moderazione del servizio.|

Il fragment privato contiene sessione Google e, con batteria attiva, la key
account. Trattarlo come una credenziale: escluso da log, documenti pubblici,
miniature dimostrative ed export. Il fatto che non sia nel file HTML caricato
non lo rende un deposito pubblico o permanente di credenziali.

## Criteri di completamento

- [ ] Bundle e artwork recuperati; originali confrontati con il manifest.
- [ ] Configurazione privata della baseline conservata oppure nuove scelte
  dell’installatore validate contro la lista Google fresca.
- [ ] Production compilato senza clock/eventi/letture simulati; controlli
  semantici su entrambi gli artefatti e sintassi JavaScript superati.
- [ ] Layout finale riconciliato; gruppo E1002 `800×480`, dither `3`;
  metadati estranei alla modifica preservati.
- [ ] Privacy verificata su documento caricato, template portabile e miniature.
- [ ] Preview reale del production ispezionata, inclusi batteria dark,
  marker, titoli lunghi e righe disponibili.
- [ ] Pagina privata salvata e confrontata tramite readback.
- [ ] Refresh accettato; assegnazione e snapshot confrontati con la pagina.
- [ ] Lettura successiva/render successivo verificati; intervallo e online
  riportati separatamente dalla consegna fisica.
- [ ] Consegna fisica dichiarata solo con osservazione del pannello relativa
  a questa revisione. `device_image` è metadato/miniatura del servizio,
  **non** prova di uno screenshot del display.
- [ ] Nuovi apprendimenti API registrati con data sia nelle API notes sia
  nel brief MCP; eventuali limiti aggiornati in questa guida.

La baseline dispone di readback, snapshot e renderer verificati; il rapporto
finale non contiene una conferma fisica del pannello per l’ultima revisione.
Conservare questa distinzione nei resoconti del ripristino.

## Impronte della baseline

Per gli asset correnti usare `templates/google-calendar-today/assets/manifest.json`.
Gli hash storici degli script e i mockup decisionali non sono un contratto
operativo: i sorgenti versionati e i due JSON persistenti sono l'autorità.
Le decorazioni attuali sono prive di testo, con `mockup_crop: false` e varianti
`darkUrl`; il fallback di inversione CSS riguarda solo asset legacy senza dark.
