# Changelog

## Unreleased

### Added

- Sorgenti di Google Calendar Today sotto `templates/google-calendar-today/`:
  HTML, helper Python, controlli JavaScript esistenti ed esempi senza credenziali.
- 25 decorazioni runtime, miniatura fittizia e manifest SHA-256.
- Catalogo template, licenza MIT per il codice e TODO espliciti.
- `.env.example` e regole Git condivise per stato privato e cache Python.

### Changed

- Nome del design e del template riutilizzabile: `Google Calendar Today`,
  senza modello hardware. Rinomina confermata tramite API; il profilo layout
  e le impostazioni restano invariati.
- Sorgenti separati dallo stato dell’account; bootstrap e configurazioni locali
  sono in `.private/native-agenda/`, mentre la key resta in `.env`.
- Helper versionati autorevoli, con compatibilità per i vecchi comandi locali.
- Runbook di ricostruzione aggiornato per sorgenti versionati, dati privati,
  configurazione e limiti effettivi dell’installazione.

### Removed

- Dal progetto: design review, mockup decisionali, prompt e probe esplorativi
  non necessari al funzionamento o alla riconfigurazione. Conservate soltanto
  le immagini richieste dalla build; gli originali rimossi sono recuperabili
  dal Cestino locale.

La riorganizzazione dei sorgenti non effettua nuovi upload o deploy e non
implementa il pannello grafico delle preferenze.
