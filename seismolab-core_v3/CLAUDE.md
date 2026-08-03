# SeismoLab Core — istruzioni per il modello AI

Sei un assistente per il progetto SeismoLab Core (Python 3.13), libreria per
il processamento e monitoraggio di dati geofisici (sismica, vulcanologia, GPS).

## Convenzioni del progetto

- **Type hints** obbligatorie per tutte le funzioni pubbliche
- **pytest** con fixture (`tests/conftest.py`) — mai `unittest`
- **Query SQL** con `psycopg2` e placeholder `%s` — mai f-string, mai `.format()`
- **Connessioni DB** ricevute come parametro, mai aperte internamente alle funzioni
- **Nessuna dipendenza** non presente in `requirements.txt`
- **Dataclass** per i tipi di dominio (`SeismicRecord`, `TremorReading`, ecc.)

## Stile delle patch

- Patch chirurgiche: modifica solo le righe indicate nell'issue
- Non riscrivere funzioni esistenti se non esplicitamente richiesto
- Non rinominare parametri o variabili senza richiesta
- Non aggiungere importazioni non necessarie
- I test esistenti devono passare invariati dopo ogni patch

## Struttura del repository

```
seismolab/parsers/mseed.py       # Issue #12 — parser MiniSEED
seismolab/alerts/volcanic.py     # Issue #17 — alerting vulcanologico
seismolab/data/gps_query.py      # Issue #23 — query GPS PostGIS
seismolab/processing/event_detector.py  # Issue #0 — STA/LTA (demo docente)
tests/conftest.py                # fixture condivise
```

## Stazioni di riferimento

- `ETNA01`, `ETNA02`: stazioni sull'Etna (soglie default)
- `STRO01`, `STRO02`: stazioni su Stromboli (soglie alzate per attività basale)
- Sample rate standard: 100 Hz (HH* channels)
