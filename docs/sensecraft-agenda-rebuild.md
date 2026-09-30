# Ricostruire l’agenda SenseCraft

Runbook per un agente che deve ripristinare o ricreare l’agenda E1002 già
implementata. Baseline: **30 settembre 2026**, dopo le correzioni di batteria
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

**Il solo clone Git non basta.** I sorgenti operativi, la configurazione e le
immagini sono esclusi da Git. Conservare un backup privato delle directory
seguenti, mantenendo i percorsi relativi al progetto. La guida non crea quel
backup. Le stesse immagini non sono riproducibili esattamente da nuovi prompt.

|Percorso|Ruolo nel ripristino|
|---|---|
|`.private/native-agenda/agenda.html`|Sorgente definitivo: CSS, JavaScript e fixture di sviluppo.|
|`.private/native-agenda/build.py`|Manifest degli asset, compilazione production, upload con cache e layout privato/portabile.|
|`.private/native-agenda/configure.py`|Configurazione una tantum, calendario/città, preview e salvataggio.|
|`.private/native-agenda/persist.py`|Salva pagina e template esistenti; richiede entrambi gli ID; effettua refresh deploy.|
|`.private/native-agenda/verify-live.py`|Readback dello snapshot e nuovo render; include una prova che richiede almeno dieci calendari nell’account.|
|`.private/native-agenda/check.js`|Controlli semantici di sviluppo e production.|
|`.private/native-agenda/config.json`|Impostazioni definitive e mappatura privata dei calendari.|
|`.private/native-agenda/candidate-private.json`|Layout finale completo, inclusi metadati del canvas.|
|`.private/native-agenda/candidate-portable.json`|Versione priva di sessione, calendari e binding batteria.|
|`.private/native-agenda/agenda-upload.html`|Artefatto production finale; conservarlo anche come riferimento.|
|`.private/native-agenda/uploads.json`|Cache `nomefile\|SHA-256` → URL media e hash.|
|`.private/native-agenda/thumbnail-uploads.json`|Cache delle miniature.|
|`.private/native-agenda/befana-long-titles.png`|Miniatura dimostrativa con eventi fittizi per il template riutilizzabile.|
|`.private/native-agenda/build-report.json`, `final-account-audit.json`|Baseline di compilazione e verifiche precedenti.|
|`.private/design-review/approved-originals/`|15 mockup approvati, lasciati immutati.|
|`.private/design-review/monthly/`|12 sfondi mensili.|
|`.private/design-review/design-manifest.json` e asset referenziati|Inventario con 35 hash delle immagini preservate, comprese simulazioni non caricate.|
|`.private/feasibility/private-settings.json`|Bootstrap privato richiesto dagli helper.|

Conservare anche gli altri file di queste directory per mantenere rapporti e
backup storici. Credenziali, configurazioni, miniature con eventi reali e
risposte dell’account vanno custodite come dati privati.

Prerequisiti operativi:

- Python 3 con `zoneinfo` e database dei fusi IANA; Node.js con i moduli standard
  usati da `check.js`. La baseline locale è stata ispezionata con Python 3.14.7
  e Node.js 26.10.0; non è una dichiarazione di versione minima.
- `.env` escluso da Git, con `SENSECRAFT_API_KEY`; caricarlo nell’ambiente senza
  stamparlo o abilitare shell tracing.
- Account autorizzato, Google collegato tramite SenseCraft e dispositivo E1002
  già associato. Gli helper non effettuano login, OAuth o associazione hardware.
- `private-settings.json` con `page_id`, `template_id`, `device_id`,
  `event_url` e `calendars`. Gli ID delle risorse sono interi. `event_url`
  contiene il parametro `session_id`; `calendars` contiene record
  `{id, name, initials, color}`. Usare i dati privati validi dell’installazione.

## Procedura di ripristino

Eseguire dalla radice del progetto, quando il ripristino e le scritture
all’account sono autorizzati. Per una richiesta di sola documentazione,
leggere questi passaggi senza eseguirli.

### 1. Recuperare la baseline e verificare le risorse

1. Leggere `AGENTS.md`; controllare branch, stato Git e modifiche esistenti.
2. Ripristinare il bundle privato. Confrontare le impronte sotto e i 35 hash
   del manifest; mantenere immutati gli originali approvati.
3. Copiare `config.json` e `candidate-private.json` in backup privati distinti
   **prima** della build. Saranno necessari per preservare la geometria finale.
4. Verificare che `.env` e `.private/` risultino ignorati con `git check-ignore`;
   se necessario aggiungere `.private/` a `.git/info/exclude`.
5. Caricare la key e validare la configurazione:

   ```sh
   set -a
   source .env
   set +a
   python3 .private/native-agenda/configure.py --check-only
   ```

6. Leggere via API pagina, dispositivo e template correnti usando gli ID del
   bootstrap. Salvare le risposte complete privatamente, senza stamparle.
   Confrontare la configurazione decodificata del fragment con il backup.

**Completato quando:** sorgenti/asset sono disponibili, configurazione valida,
risorse attuali identificate e stato precedente recuperabile. Se sessione o
risorse non sono più valide, seguire il ramo [risorse nuove](#installazione-con-risorse-nuove).

### 2. Compilare il documento production

```sh
node .private/native-agenda/check.js
python3 .private/native-agenda/build.py --production
node .private/native-agenda/check.js --production
```

`build.py` effettua upload persistenti quando la cache non contiene lo stesso
hash. Non salva la pagina, ma riscrive configurazione, candidati e rapporto
locali. Legge comunque `private-settings.json`, anche quando `config.json`
esiste. Senza `--production` il risultato contiene percorsi di simulazione:
usare sempre l’opzione per un’installazione reale.

La build:

1. Carica i PNG mensili e gli originali decorativi; salta `white` e `dark`.
2. Inserisce gli URL nel placeholder `/* ASSET_MANIFEST */{}` del sorgente.
3. Rimuove clock/eventi/meteo/batteria simulati, conservando gli helper runtime.
4. Carica `agenda-upload.html` come `type=document`.
5. Aggiorna il binding batteria privato dalla key nell’ambiente.
6. Genera due layout: privato e portabile; verifica l’assenza dei valori privati
   nel documento caricato e nel layout portabile.

La baseline contiene **25 asset decorativi caricati**; il manifest complessivo
preserva 35 immagini. Gli originali che contengono lettering da mockup sono
ritagliati via CSS; non vengono modificati. L’eventuale `darkUrl` dedicato
ha precedenza sul filtro CSS di inversione e rotazione della tinta.

Estrarre il JavaScript dall’artefatto appena compilato per il controllo
sintattico, evitando un vecchio `production-check.js`:

```sh
python3 - <<'PY'
from pathlib import Path
root = Path('.private/native-agenda')
html = (root / 'agenda-upload.html').read_text()
js = html.split('<script>', 1)[1].split('</script>', 1)[0]
(root / 'production-check.js').write_text(js)
PY
node --check .private/native-agenda/production-check.js
```

**Completato quando:** i 51 controlli passano su ciascuna delle due versioni,
JavaScript valido, `build-report.json` dichiara `production: true` e privacy
verificata. In un ripristino con gli stessi URL media, confrontare anche l’hash
del production finale. Nuovi URL comportano un hash diverso pur mantenendo
lo stesso codice e artwork.

### 3. Preservare il layout finale e ispezionare la preview

La build rigenera un canvas canonico `800×480`. Il layout finale della
baseline conserva invece `stageSize: {width: 1508, height: 834}` dell’editor,
con gruppo dispositivo `800×480`. Sono due geometrie distinte.

Per ripristinare la stessa installazione:

1. Usare il backup finale del layout come base, conservandone tutti i metadati.
2. Sostituire soltanto `htmlConfig.htmlUrl` del figlio `id: "native-agenda"`
   con quello del candidato appena compilato, comprensivo del fragment privato.
3. Lasciare un solo componente HTML nel gruppo; la batteria è già al suo interno.
   Rimuovere l’eventuale vecchio figlio `native-battery`.
4. Salvare il risultato in `candidate-private.json`. Applicare gli stessi
   metadati non privati al candidato portabile, mantenendo il suo URL sanificato.
5. Richiedere una preview del candidato production e ispezionarla **prima**
   del salvataggio della pagina.

Comando per la preview reale, senza stampare layout, URL privato o risposte:

```sh
python3 - <<'PY'
import json, os, urllib.request
from pathlib import Path
root = Path('.private/native-agenda')
layout = json.loads((root / 'candidate-private.json').read_text())
payload = {'layout': layout, 'resolution': '800x480',
           'dither': 3, 'img_format': 'png'}
request = urllib.request.Request(
    'https://sensecraft-hmi-api.seeed.cc/render/preview',
    data=json.dumps(payload).encode(),
    headers={'api-key': os.environ['SENSECRAFT_API_KEY'],
             'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=60) as response:
    image = response.read()
assert image.startswith(b'\x89PNG'), 'Preview non PNG: fermarsi e analizzare privatamente'
(root / 'rebuild-preview.png').write_bytes(image)
PY
```

Controllare titoli lunghi, orario fisso, orario di fine, marker allineati a
destra, contrasto sullo sfondo, spazio verticale e batteria trasparente.
Per confrontare modalità o date simulate, usare una copia privata di sviluppo;
il candidato da installare deve sempre referenziare il production senza fixture.

`configure.py --preview` usa l’URL della pagina attualmente salvata: prima del
salvataggio può quindi mostrare il documento precedente. La preview diretta
del candidato evita questa ambiguità.

**Completato quando:** metadati preservati, URL production corretto in entrambi
i candidati, nessun binding privato nel portabile e preview effettiva ispezionata.

### 4. Salvare, distribuire e leggere lo stato risultante

Con pagina e template esistenti, eseguire:

```sh
python3 .private/native-agenda/persist.py
```

L’helper legge e salva backup dello stato corrente, genera una preview reale,
carica miniature, aggiorna pagina e template, confronta i readback e richiede
il refresh del dispositivo. La pagina riceve la miniatura reale; il template
riceve quella con dati fittizi. Il template portabile esclude `session_id`,
calendari e `batteryBinding`, e imposta `showBattery: false`.

`persist.py` legge tutti i template paginati prima della scrittura; il suo
readback successivo cerca però nelle prime 100 voci. Se il target non è lì,
paginare il readback prima di concludere che la scrittura è fallita.

Se l’account ha almeno dieci calendari collegati:

```sh
python3 .private/native-agenda/verify-live.py
```

Per account con meno calendari, effettuare le stesse letture di verifica
descritte sotto, separando la prova opzionale dei dieci calendari: l’helper
attuale si arresta su quell’asserzione prima di verificare lo snapshot.

**Completato quando:** pagina privata e portabile corrispondono ai candidati,
deploy accettato, snapshot assegnato uguale alla pagina desiderata, nuova preview
dello snapshot ispezionata e stato fisico riportato con il suo livello di prova.

## Installazione con risorse nuove

Gli helper sono strumenti di ripristino di risorse esistenti, non un bootstrap
completo di un account vuoto. Usare questa sequenza se gli ID o la sessione del
backup non sono più utilizzabili:

1. Leggere `GET /api/v2/user/device/list`, identificare E1002 tramite `board.type`
   e registrare privatamente ID e MAC correnti. Associare il dispositivo tramite
   la procedura SenseCraft se non è ancora associato.
2. Creare una pagina layout E1002 dal normale editor SenseCraft. Il percorso
   `POST /api/v2/user/page` è noto, ma questi helper e le note attuali non fissano
   un payload di creazione completo validato: usare il bootstrap nativo evita
   di inventare un contratto. Tutta la costruzione successiva usa le API.
3. Collegare Google dalla configurazione dati di SenseCraft, scegliere i
   calendari e usare **Load Data**. Recuperare privatamente il `session_id`
   autorizzato dal callback/configurazione salvata o dall’URL della sorgente
   eventi. Non riutilizzare la sessione di un altro installatore.
4. Preparare `private-settings.json` con le nuove risorse ed `event_url` valido.
   Preparare `config.json` dai default del sorgente, con sessione e mappatura
   privata. La key resta in `.env`; il binding viene costruito dall’helper.
5. Compilare per ottenere i candidati. Inserire l’HTML nella nuova pagina via
   API e fare readback prima di usare `configure.py`, che richiede un figlio
   `native-agenda` già esistente nella pagina salvata.
6. Rileggere i calendari e configurare le scelte con indici **della lista fresca**:

   ```sh
   python3 .private/native-agenda/configure.py --list-calendars
   python3 .private/native-agenda/configure.py \
     --calendar '1:AA:#D32F2F' --calendar '2:BB:#1565C0' \
     --set language=it --set intensity=50 --preview
   ```

   Gli indici e le iniziali sopra sono esempi: sostituirli con le scelte private
   dell’installatore. Ripetere `--calendar` da una a dieci volte. L’opzione
   sostituisce l’intera selezione. Per salvare, ripetere le stesse opzioni con
   `--save`; per distribuire aggiungere `--deploy`, che richiede `--save`.
7. Se serve un nuovo template riutilizzabile e la creazione è autorizzata,
   seguire il payload in [Create payload proven by client source](sensecraft-hmi-api.md#create-payload-proven-by-client-source):
   usare `candidate-portable.json` serializzato in `data`, `api_data` sanificato,
   miniatura fittizia, modello E1002, risoluzione `800x480`, dither `3` e il nuovo
   `record_page_id`. Registrare privatamente `result.id` come `template_id`.
   La creazione può richiedere moderazione; non è necessaria per il dispositivo.
8. Eseguire la procedura di ripristino con i nuovi ID. Se si desidera soltanto
   la pagina privata, usare preview, pagina `PUT`, deploy e readback via API,
   evitando `persist.py`, che aggiorna obbligatoriamente anche un template.

Importare un template dal marketplace non compila questo fragment né avvia
automaticamente tutta la procedura OAuth/mappatura. Non esiste nella baseline
un pannello nativo con le checkbox personalizzate: le impostazioni sono
funzionanti tramite configurazione una tantum.

## Configurazione e comportamento

Per la stessa installazione, **`config.json` finale è l’autorità**. Per una nuova
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
python3 .private/native-agenda/configure.py \
  --set markerMode=initials_only --set showTimezone=false --set intensity=37 --preview
python3 .private/native-agenda/configure.py --city Roma --city-index 1 --preview
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
- Eventi: oggi e fino a tre date successive; cancellati esclusi. Conservare
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
|Sole|`GET https://api.open-meteo.com/v1/forecast`, query `latitude`, `longitude`, `daily=sunrise,sunset`, `timezone`, `forecast_days=4`.|
|Batteria runtime|`GET /api/v1/user/device/iot_data/{deviceId}`, header `api-key`, `credentials: "omit"`; `result.battery.level`.|
|Preview|`POST /render/preview`, `{layout, resolution: "800x480", dither: 3, img_format: "png"}`.|
|Pagina|`GET /api/v2/user/page/detail?page_id=…`; salvare con `PUT /api/v2/user/page`, `{id, data: "JSON serializzato", thumbnail}`; leggere di nuovo e confrontare JSON.|
|Template esistente|`PUT /api/v2/user/template`; usare i campi preservati dall’helper, `data`/`api_data` stringhe JSON e `category_ids` interi; leggere tutta la lista paginata per verificare.|
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
- [ ] Pagina e, se richiesto, template salvati e confrontati tramite readback.
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

SHA-256 dei sorgenti privati ispezionati il 30 settembre 2026. Questa sezione
identifica la versione da recuperare; gli hash non sostituiscono il backup.

```text
agenda.html
af114122f905df61a36073313863c1a7d2e0e0fd90ef9a135b0d5b77840a4419
agenda-upload.html
1dee64e75f27d7643a1b75687cb4c1e4463bc4ae593e7f8845ef10d22365f487
build.py
e297b4e44d14c9ead3a5ab9734b5db25c8c6e8ce5efae65509b190e3bd813318
configure.py
2ddeea4b955590b2bc77a8bb5a6fe7c1074cda88866aa0642b2f6e74b8a23c33
persist.py
0d68da9c7e5ee99dad0634e4d1a436983ccfa46350a874e0d372d9d29498f7d8
verify-live.py
516842467056d44877c2935f7431c131ea16aff7e89ba893053704770dde3e17
check.js
f4559f1d34ed8fb14557574751ec6cefc5971b4aafb7e86117241becd5df9f1f
```
