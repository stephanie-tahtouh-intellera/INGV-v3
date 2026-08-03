# SeismoLab Core

Libreria Python interna per l'acquisizione, validazione e analisi di dati geofisici multi-sorgente.

Gestisce dati provenienti da tre tipologie di sensori:
- **Stazioni sismiche** — tracce in formato MiniSEED
- **Sensori vulcanologici** — ampiezza del tremore, soglie di allerta
- **Ricevitori GPS** — coordinate e spostamenti da database PostGIS

## Requisiti

- Python 3.13+
- Dipendenze: vedi `requirements.txt`

```bash
git clone https://github.com/stephanie-tahtouh-intellera/INGV-v3.git
cd INGV-v3/seismolab-core_v3
pip install -r requirements.txt
```

## Struttura

```
seismolab/
├── parsers/mseed.py              # Parser tracce sismiche MiniSEED
├── alerts/volcanic.py            # Sistema di alerting vulcanologico
├── data/gps_query.py             # Query su dati GPS da PostGIS
└── processing/event_detector.py  # Rilevazione eventi sismici (STA/LTA)
```

## Esecuzione rapida

```bash
python scripts/ingest_sample.py
```

## Test

```bash
pytest tests/
```

## Issue aperte

| # | Titolo | Modulo | Priorità |
|---|--------|--------|----------|
| 12 | Parser MiniSEED fallisce su tracce con gap temporali | parsers | Alta |
| 17 | Soglie di allerta vulcanologica hardcoded nel codice | alerts | Media |
| 23 | Aggiungere endpoint query dati GPS da PostGIS | data | Media |
| 0  | Conteggio eventi non deterministico su analisi multi-stazione | processing | Alta |

> L'issue #12 è l'esempio sviluppato dal docente durante la giornata (non assegnabile).
> I partecipanti scelgono tra la #17, la #23 e la #0.
> Per la #0 il titolo descrive il sintomo osservabile, non la causa: trovarla fa parte dell'esercizio.

## Contribuire

1. Assegnarsi un'issue
2. Creare un branch: `git checkout -b fix/issue-XX-descrizione`
3. Implementare la modifica con test
4. Aprire una Pull Request verso `main`

---

*Progetto interno INGV — Piano Formazione AI 2026*
