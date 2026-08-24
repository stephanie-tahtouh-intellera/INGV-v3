
# SeismoLab Core


# Coach — Piano tecnico & Prompt (`coach_piano_prompt.jsx`)

Strumento interattivo per i partecipanti: incolla il tuo piano tecnico o il tuo prompt per una delle issue sotto e ricevi feedback mirato (cosa funziona, cosa è ancora generico, una domanda guida) senza che ti venga data la soluzione.

### Installazione e uso

**Come aprire `coach_piano_prompt.jsx`**

Il file è un componente React con export default, pensato per girare come artifact Claude. Hai due modi per usarlo:

1. **Come artifact Claude (consigliato, nessuna installazione)**
   - Apri una conversazione su claude.ai (o nell'app desktop/mobile).
   - Carica il file `coach_piano_prompt.jsx` nella chat, oppure incolla il suo contenuto e chiedi a Claude di "renderizzarlo come artifact".
   - L'artifact si apre automaticamente in un pannello a lato; usa il pulsante di fullscreen in alto a destra del pannello per espanderlo a tutto schermo.
   - Non serve installare nulla: l'ambiente artifact fornisce già React e la storage API (`window.storage`) usata per salvare la cronologia dei tentativi.
   - Perché la valutazione funzioni devi essere autenticato con un account Claude attivo, dato che il componente chiama l'API di Claude (`api.anthropic.com`) al click su **Valuta**.

2. **Come progetto React standalone (per uso locale/offline dell'interfaccia, senza il pulsante "Valuta" funzionante)**
   - Crea un progetto React (es. con Vite): `npm create vite@latest seismolab-coach -- --template react`
   - Copia `coach_piano_prompt.jsx` dentro `src/`, rinominandolo ad es. `Coach.jsx`.
   - Importalo in `src/App.jsx`: `import Coach from './Coach'; export default function App() { return <Coach />; }`
   - Installa le dipendenze e avvia: `npm install && npm run dev`
   - Nota: fuori dall'ambiente artifact, `window.storage` non esiste e la chiamata a `api.anthropic.com` dal browser fallirà per CORS/assenza di chiave — questa modalità serve solo a vedere e testare l'interfaccia, non a ottenere feedback reali. Per la valutazione funzionante, usa l'opzione 1.

**Uso una volta aperto**

1. Seleziona l'issue su cui stai lavorando (`#17`, `#23` o `#0`).
2. Scegli la fase: **Piano tecnico** o **Prompt**.
3. Scrivi il testo nell'area dedicata e premi **Valuta**.
4. Il componente chiama l'API di Claude internamente per generare il feedback.
5. I tentativi precedenti restano visibili in fondo alla pagina per tracciare i progressi durante la sessione.

> Lo strumento non scrive mai la soluzione al posto tuo: il suo scopo è aiutarti a capire cosa manca nel tuo ragionamento.

---

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