# Template SenseCraft

Sorgenti riutilizzabili dei template sviluppati nel progetto.

## Indice

- [Catalogo](#catalogo)
- [Organizzazione](#organizzazione)

## Catalogo

|Template|Implementazione|Personalizzazione|
|---|---|---|
|[Google Calendar Today](google-calendar-today/README.md)|HTML eseguito dal renderer SenseCraft; profilo attuale `800×480`, dither `3`.|Script API una tantum; pannello grafico non implementato.|

## Organizzazione

Ogni directory contiene sorgenti, strumenti, esempi senza credenziali e
documentazione del proprio template. Versionare soltanto gli asset necessari
al runtime o alla riconfigurazione. Materiale decisionale e mockup di controlli
non implementati non fanno parte del template operativo.

Configurazioni dell’account, credenziali, risposte API, build, cache e preview
con eventi reali restano in `.private/`, esclusa tramite `.gitignore`.
