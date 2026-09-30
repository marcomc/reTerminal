# TODO

Attività aperte; non sono funzionalità già implementate.

## Google Calendar Today

- [ ] Pannello grafico per calendari, colori, temi e indicatori. Verificare
  prima le possibilità di integrazione in SenseCraft; nessun servizio ospitato
  aggiuntivo è autorizzato dalla fase corrente.
- [ ] Procedura di installazione per un nuovo utente: Google OAuth nativo,
  selezione calendari e configurazione privata del componente HTML. Il
  marketplace non completa automaticamente questa sequenza.
- [ ] Adattare geometria e rendering ad altri modelli/risoluzioni. Il nome è
  indipendente dal dispositivo; la versione attuale resta `800×480`, dither `3`.
- [ ] Separare compilazione offline e upload nella build, preservando il
  controllo dei dati simulati nell’artefatto production.
- [ ] Rendere facoltativa la verifica dei dieci calendari in `verify-live.py`:
  oggi richiede almeno dieci calendari collegati.
- [ ] Paginare anche il readback del template in `persist.py`, che attualmente
  cerca il target nelle prime 100 voci dopo il salvataggio.
- [ ] Valutare un binding batteria con credenziali più limitate: oggi la key
  account è nel fragment privato del layout e va protetta come una credenziale.
- [ ] Valutare convenzioni regionali di Carnevale e maggiore precisione
  astronomica solo se necessarie. Il runtime usa Martedì Grasso e luna stimata.

## API e futuro MCP

- [ ] Implementare il MCP seguendo `docs/mcp-implementation-brief.md` quando
  richiesto; in questa fase sono presenti documentazione e helper API.
- [ ] Verificare i contratti ancora indicati come non confermati nelle API notes,
  mantenendo separati authoring, pubblicazione, moderazione e deploy.
- [ ] A ogni nuovo apprendimento API aggiornare sia le API notes sia il brief
  MCP, senza riportare dati dell’account o credenziali.
