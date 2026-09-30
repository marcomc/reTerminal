# TODO

Attività aperte; non sono funzionalità già implementate.

## Google Calendar Today

- [x] Pannello Python locale con tutte le preferenze, preview nativa e pubblicazione
  privata confermata; configurazione duratura e recupero dei tentativi interrotti.
- [x] Setup key e riuso/importazione Google nativa senza modifica manuale dei JSON.
- [ ] Verificare il ritorno OAuth completo dal provider al callback loopback;
  l'importazione guidata della pagina nativa è il fallback implementato.
- [ ] Verificare il create pagina su un account nuovo reale: payload client/fixture
  disponibile, integrazione reale effettuata sulla pagina privata esistente.
- [ ] Individuare un inventario upload o idempotenza upstream per riconciliare
  risposte perse senza possibili file orfani; oggi recupero locale confermato.
- [ ] Adattare geometria e rendering ad altri modelli/risoluzioni. Il nome è
  indipendente dal dispositivo; la versione attuale resta `800×480`, dither `3`.
- [ ] Separare compilazione offline e upload nella build, preservando il
  controllo dei dati simulati nell’artefatto production.
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
