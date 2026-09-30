# Google Calendar Today

Agenda multi-calendario per SenseCraft, con temi e indicatori astronomici.
Il nome del template non dipende dal dispositivo. Il layout attuale è
implementato per `800×480` landscape, dither `3`: altri profili richiedono
adattamento e verifica.

## Indice

- [Sorgenti e stato privato](#sorgenti-e-stato-privato)
- [Funzionalità e limiti](#funzionalità-e-limiti)
- [Preparazione](#preparazione)
- [Personalizzazione](#personalizzazione)
- [Build e installazione](#build-e-installazione)
- [Asset e licenza](#asset-e-licenza)

## Sorgenti e stato privato

```text
templates/google-calendar-today/         sorgenti versionabili
├── src/agenda.html                     CSS, logica e fixture dimostrative
├── scripts/                            build, configure, persist, verify-live
├── examples/                           configurazioni senza dati di account
├── assets/                             sfondi runtime, miniatura e inventario
└── LICENSE                             MIT per il codice

.private/native-agenda/                 stato locale escluso da Git
├── config.json                         sessione e calendari dell’installatore
├── private-settings.json               risorse private e bootstrap Google
├── agenda-upload.html                  artefatto generato
├── candidate-private.json              layout con binding privati
├── candidate-portable.json             export senza binding
└── ...                                 cache, backup, rapporti e preview
```

Gli script leggono la key da `SENSECRAFT_API_KEY`; non caricano `.env`
automaticamente. Scrivono nello stato privato, anche se lanciati da un’altra
directory. `SENSECRAFT_AGENDA_STATE_DIR` permette una directory alternativa
privata esterna ai sorgenti: escluderla da Git se è dentro il repository.

I vecchi entry point sotto `.private/native-agenda/` sono compatibilità locale;
i file in `scripts/` sono l’implementazione autorevole. I vecchi backup e gli
esperimenti API non sono sorgenti del template.

## Funzionalità e limiti

- Da 1 a 10 calendari, iniziali e colori per calendario; quattro modalità marker.
- Eventi ancora attivi mantenuti fino all’ora di fine; riempimento dello spazio
  verticale, titoli con riduzione limitata e sfumatura.
- Cinque lingue, clock sempre visibile, città/fuso e indicatori opzionali.
- Sfondi manuali, mensili o stagionali, festività e dark tra tramonto e alba.
- Intensità 0–100 e batteria trasparente con colori del tema.

**Il pannello grafico delle preferenze è un mockup, non un’interfaccia
implementata in SenseCraft.** Le impostazioni sono funzionanti tramite
`configure.py`. Il collegamento Google avviene nel percorso nativo SenseCraft;
l’importazione del template non completa OAuth e mappatura automaticamente.
Il runtime è l’HTML caricato su SenseCraft: non richiede uno script periodico,
un server locale o un servizio ospitato da noi.

## Preparazione

Eseguire dalla radice del repository. Servono Python 3 con `zoneinfo`, una key
SenseCraft e risorse già create nell’account. Per i controlli semantici esistenti
serve Node.js; gli script usano soltanto librerie standard.

Per una nuova installazione locale:

```sh
mkdir -p .private/native-agenda
cp templates/google-calendar-today/examples/config.example.json \
  .private/native-agenda/config.json
cp templates/google-calendar-today/examples/private-settings.example.json \
  .private/native-agenda/private-settings.json
chmod 600 .private/native-agenda/config.json \
  .private/native-agenda/private-settings.json
```

Non sovrascrivere la configurazione di un’installazione esistente. Sostituire
i placeholder privatamente con sessione Google autorizzata, ID delle risorse
e calendari dell’installatore. Gli esempi non costituiscono un account pronto.

Caricare `.env` senza tracing o stampa:

```sh
set -a
source .env
set +a
```

La key va in `.env`, escluso da Git. Il binding batteria viene generato dallo
script; non inserire la key nei sorgenti o negli esempi. La procedura completa
per nuove risorse è nel [runbook](../../docs/sensecraft-agenda-rebuild.md).

## Personalizzazione

```sh
python3 templates/google-calendar-today/scripts/configure.py --help
python3 templates/google-calendar-today/scripts/configure.py --list-calendars
python3 templates/google-calendar-today/scripts/configure.py \
  --set backgroundMode=manual --set theme=floral --set intensity=40 --preview
```

La preview viene scritta in `.private/native-agenda/configured-preview.png`;
non modifica la pagina. Per applicare le stesse opzioni:

```sh
python3 templates/google-calendar-today/scripts/configure.py \
  --set backgroundMode=manual --set theme=floral --set intensity=40 \
  --save --deploy
```

La selezione usa gli indici della lista appena letta:

```sh
python3 templates/google-calendar-today/scripts/configure.py \
  --calendar '1:AA:#D32F2F' --calendar '2:BB:#1565C0' --preview
```

`--calendar` sostituisce l’intero insieme scelto; ripeterlo da 1 a 10 volte.
Gli indici sopra sono esempi. Anteprime e draft non vengono applicati
automaticamente: ripetere le opzioni desiderate con `--save`.
Schema completo nel [brief MCP](../../docs/mcp-implementation-brief.md#settings-schema).

## Build e installazione

```sh
python3 templates/google-calendar-today/scripts/build.py --production
```

La build carica gli asset mancanti e l’HTML tramite API e genera i candidati
nello stato privato. **Effettua upload persistenti**, ma non salva la pagina.
Richiede anche il bootstrap privato; non è una build offline. Conservare
configurazione e layout finale prima di eseguirla. Il canvas generato è
`800×480`; per un ripristino preservare i metadati dell’editor come descritto
nel runbook. Senza `--production` sono presenti le fixture di simulazione.

Per installare su pagina e template già esistenti, dopo la preview:

```sh
python3 templates/google-calendar-today/scripts/persist.py
python3 templates/google-calendar-today/scripts/verify-live.py
```

`persist.py` salva pagina e template, carica miniature e richiede il refresh;
non è un comando di sola lettura. `verify-live.py` legge stato e snapshot,
richiede un nuovo render e scrive rapporti privati. La verifica opzionale dei
dieci calendari richiede almeno dieci calendari collegati: con meno calendari,
seguire le letture del runbook. Il clone non include login, OAuth, associazione
hardware o creazione completa delle risorse per un account vuoto.

I controlli semantici esistenti sono in `scripts/check.js`; con `--production`
leggono l’artefatto compilato nello stato privato. Non richiedono accesso API.
Non confondere readback/deploy accettato con conferma fisica del display.

## Asset e licenza

`assets/monthly/` contiene i dodici sfondi mensili; `assets/themes/` contiene
le tredici decorazioni tematiche, comprese le festività e Halloween dark.
`assets/thumbnail.png` è la miniatura con eventi fittizi usata dal template
riutilizzabile. `assets/manifest.json` registra i loro hash. Gli originali
tematici usati dal runtime hanno lettering da mockup: il CSS lo ritaglia;
queste immagini restano necessarie alla build e non sono materiale di review.
Bianco/dark sono superfici CSS e non richiedono immagini separate.
Confronti, pannelli concettuali, prompt e prove decisionali sono stati rimossi
dal progetto. Gli asset runtime sono rimasti byte per byte invariati.

Il codice HTML, JavaScript e Python è sotto [MIT](LICENSE). Documentazione,
mockup e artwork originali del progetto sono sotto [CC BY 4.0](../../LICENSE).
Le licenze non riguardano il servizio SenseCraft o i marchi di terzi.
