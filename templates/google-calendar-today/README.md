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

sensecraft.local.json                    preferenze persistenti; ignorato
sensecraft.connection.local.json         key, sessione Google, risorse; ignorato

.private/native-agenda/                 output rigenerabili esclusi da Git
├── agenda-upload.html                  artefatto generato
├── candidate-private.json              layout con binding privati
├── candidate-portable.json             export senza binding
└── ...                                 cache, backup, rapporti e preview
```

Gli helper risolvono i percorsi dalla root indipendentemente dalla directory
corrente. Le preferenze sono in `sensecraft.local.json`; key, sessione e ID
in `sensecraft.connection.local.json` (permessi 0600). Il loader migra il
precedente formato unificato. Una key esplicitamente esportata ha precedenza;
`.env` è compatibilità legacy, letta senza esecuzione shell.

`SENSECRAFT_AGENDA_CONFIG`, `SENSECRAFT_AGENDA_CONNECTION` e
`SENSECRAFT_AGENDA_STATE_DIR` consentono altri percorsi privati esclusi da Git.
Eliminare `.private/` non deve perdere preferenze o connessioni ancora valide.
I vecchi entrypoint in quella directory restano compatibilità locale.

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

Per una nuova configurazione locale, senza sovrascrivere file esistenti:

```sh
cp sensecraft.local.example.json sensecraft.local.json
cp sensecraft.connection.local.example.json sensecraft.connection.local.json
chmod 600 sensecraft.local.json sensecraft.connection.local.json
```

Impostare privatamente key, sessione Google, risorse e mapping dell'installatore.
Gli esempi non effettuano OAuth o bootstrap. Il binding batteria viene costruito
nel layout privato: non mettere credenziali nei sorgenti o negli esempi.
La [guida di ricostruzione](../../docs/sensecraft-agenda-rebuild.md) descrive
ripristino e nuove risorse; il
[configuratore pianificato](../../docs/sensecraft-configurator-goal.md)
è distinto dagli helper CLI attuali.

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
Richiede la connessione privata; non è una build offline. Conservare
configurazione e layout finale prima di eseguirla. Il canvas generato è
`800×480`; per un ripristino preservare i metadati dell’editor come descritto
nel runbook. Senza `--production` sono presenti le fixture di simulazione.

Per installare sulla pagina privata esistente, dopo la preview:

```sh
python3 templates/google-calendar-today/scripts/persist.py --preview-only
# Inspect .private/native-agenda/production-before-save.png before saving.
python3 templates/google-calendar-today/scripts/persist.py --deploy
python3 templates/google-calendar-today/scripts/verify-live.py
```

`persist.py` aggiorna soltanto la pagina privata, preserva i metadati dell'editor,
carica la miniatura reale, effettua readback; `--deploy` richiede il refresh. `--preview-only`
consente di ispezionare il candidato prima del salvataggio.
Il template riutilizzabile ritirato non è richiesto o ricreato.
`verify-live.py` controlla selezione e snapshot contro `persisted-private.json`,
che conserva il layout riconciliato dopo il readback esatto; la prova su dieci calendari
è opzionale con `--ten-calendars`. Il percorso CLI richiede risorse esistenti;
non completa login, OAuth o bootstrap di un account vuoto.

Per i test locali:

```sh
python3 -m unittest discover -s templates/google-calendar-today/tests
```

I controlli semantici esistenti sono in `scripts/check.js`; con `--production`
leggono l’artefatto compilato nello stato privato. Non richiedono accesso API.
Non confondere readback/deploy accettato con conferma fisica del display.

## Asset e licenza

Gli sfondi sono decorazioni prive di lettering/UI: 12 temi e 12 mesi,
ciascuno con variante dark. Il manifest registra hash e associazioni;
`mockup_crop: false` usa tutto lo sfondo senza ritaglio. La miniatura con
esempi fittizi è separata e non viene usata come sfondo.
Bianco/dark base sono superfici CSS.

Il codice HTML, JavaScript e Python è sotto [MIT](LICENSE). Documentazione,
mockup e artwork originali del progetto sono sotto [CC BY 4.0](../../LICENSE).
Le licenze non riguardano il servizio SenseCraft o i marchi di terzi.
