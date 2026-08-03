"""
Rilevatore di eventi sismici tramite algoritmo STA/LTA.

L'algoritmo Short-Term Average / Long-Term Average calcola in ogni istante
il rapporto tra l'energia del segnale su una finestra breve (STA, sensibile
agli onset) e una finestra lunga (LTA, rappresentativa del rumore di fondo).
Quando il rapporto supera una soglia, viene dichiarato un evento.

Questo modulo è usato per il monitoraggio in tempo reale:
detect_events viene chiamata su ogni nuova finestra di dati,
e gli eventi rilevati vengono accumulati per il report giornaliero.

Issue #0 — BUG SOTTILE:
La funzione detect_events ha un parametro con valore di default mutabile
(events: list = []). In Python, i valori di default dei parametri sono
valutati UNA SOLA VOLTA alla definizione della funzione — non ad ogni
chiamata. Questo significa che la stessa lista viene riutilizzata per
tutte le chiamate che non passano esplicitamente il parametro events.

Sintomo osservabile: il conteggio degli eventi rilevati cresce
misteriosamente chiamata dopo chiamata, anche su segnale piatto.
Su una singola chiamata il risultato è corretto. Il bug emerge
solo quando la funzione viene chiamata più volte in sequenza
(es. nel loop di monitoring su più stazioni).

Questo tipo di bug è insidioso perché:
1. I test su singola chiamata passano
2. Il problema è riproducibile solo con pattern di chiamata specifici
3. La causa non è nella logica dell'algoritmo ma in Python stesso
4. Il refactoring del parametro è banale; trovare il problema non lo è

Issue #0 (parte 2) — PROBLEMA DI PERFORMANCE:
compute_sta_lta ricalcola le somme STA e LTA da zero per ogni campione,
scorrendo l'intera finestra ad ogni iterazione. La complessità è
O(n * finestra): su una traccia di monitoraggio reale (una stazione
registra circa 8,6 milioni di campioni al giorno a 100 Hz) la funzione
diventa inutilizzabile, impiegando minuti per una singola traccia.

Sintomo osservabile: il tempo di esecuzione cresce in modo più che
lineare con la lunghezza della traccia. Su tracce brevi (test) è
impercettibile; su tracce reali blocca la pipeline di monitoraggio.

La correzione richiede di capire l'algoritmo: le somme STA e LTA possono
essere mantenute in modo incrementale (sliding window), sottraendo il
campione che esce ed aggiungendo quello che entra, portando la
complessità a O(n). Il risultato numerico deve restare identico.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SeismicEvent:
    """Evento sismico rilevato."""
    station: str
    onset_time: float       # timestamp UNIX del P-onset
    offset_time: float      # timestamp UNIX della coda
    peak_ratio: float       # valore massimo STA/LTA durante l'evento
    duration_s: float       # durata in secondi

    @property
    def is_significant(self) -> bool:
        """True se l'evento supera la soglia di significatività."""
        return self.peak_ratio >= 3.0 and self.duration_s >= 1.0


@dataclass
class DetectionResult:
    """Risultato della rilevazione su una traccia."""
    station: str
    events: list[SeismicEvent]
    sta_lta_ratios: list[float]    # serie temporale dei rapporti STA/LTA
    threshold_used: float
    samples_analyzed: int

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def significant_events(self) -> list[SeismicEvent]:
        return [e for e in self.events if e.is_significant]


def compute_sta_lta(
    samples: list[float],
    sample_rate: float,
    sta_window_s: float = 1.0,
    lta_window_s: float = 30.0,
) -> list[float]:
    """
    Calcola il rapporto STA/LTA per ogni campione della traccia.

    Args:
        samples:       lista di campioni di ampiezza
        sample_rate:   campioni al secondo
        sta_window_s:  finestra STA in secondi (default: 1s)
        lta_window_s:  finestra LTA in secondi (default: 30s)

    Returns:
        Lista di rapporti STA/LTA, uno per campione.
        I campioni nelle prime lta_window_s hanno rapporto 0.0.
    """
    sta_n = max(1, int(sta_window_s * sample_rate))
    lta_n = max(sta_n + 1, int(lta_window_s * sample_rate))
    ratios = []

    for i in range(len(samples)):
        if i < lta_n:
            ratios.append(0.0)
            continue

        # PERF (#0 parte 2): ricalcolo O(finestra) ad ogni campione.
        # Su tracce lunghe questo rende la funzione inutilizzabile.
        # Va sostituito con somme scorrevoli (sliding window) -> O(n).
        sta_samples = [abs(s) for s in samples[i - sta_n:i]]
        lta_samples = [abs(s) for s in samples[i - lta_n:i]]

        sta = sum(sta_samples) / len(sta_samples)
        lta = sum(lta_samples) / len(lta_samples)

        ratios.append(sta / lta if lta > 1e-10 else 0.0)

    return ratios


def detect_events(
    station: str,
    samples: list[float],
    sample_rate: float,
    threshold: float = 2.5,
    sta_window_s: float = 1.0,
    lta_window_s: float = 30.0,
    events: list = [],          # BUG (#0): mutable default argument
) -> DetectionResult:
    """
    Rileva eventi sismici tramite STA/LTA su una traccia.

    Args:
        station:      codice stazione
        samples:      campioni di ampiezza
        sample_rate:  campioni al secondo
        threshold:    soglia STA/LTA per dichiarare un evento (default: 2.5)
        sta_window_s: finestra STA in secondi
        lta_window_s: finestra LTA in secondi
        events:       lista di eventi preesistenti da cui partire
                      *** BUG: non usare [] come default — vedere issue #0 ***

    Returns:
        DetectionResult con gli eventi rilevati sulla traccia.

    NOTA: il parametro `events=[]` è un mutable default argument.
    Ogni chiamata senza passare events esplicitamente condivide la stessa
    lista. Gli eventi si accumulano tra chiamate successive.
    """
    ratios = compute_sta_lta(samples, sample_rate, sta_window_s, lta_window_s)
    threshold_n = threshold

    in_event = False
    event_start = 0
    peak_ratio = 0.0

    for i, ratio in enumerate(ratios):
        t = i / sample_rate

        if not in_event and ratio >= threshold_n:
            in_event = True
            event_start = t
            peak_ratio = ratio

        elif in_event:
            if ratio > peak_ratio:
                peak_ratio = ratio
            if ratio < threshold_n * 0.7:   # isteresi al 70%
                events.append(SeismicEvent(
                    station=station,
                    onset_time=event_start,
                    offset_time=t,
                    peak_ratio=peak_ratio,
                    duration_s=t - event_start,
                ))
                in_event = False
                peak_ratio = 0.0

    # Chiude un evento ancora aperto a fine finestra
    if in_event:
        events.append(SeismicEvent(
            station=station,
            onset_time=event_start,
            offset_time=len(samples) / sample_rate,
            peak_ratio=peak_ratio,
            duration_s=len(samples) / sample_rate - event_start,
        ))

    return DetectionResult(
        station=station,
        events=events,
        sta_lta_ratios=ratios,
        threshold_used=threshold,
        samples_analyzed=len(samples),
    )


def batch_detect(
    station_data: dict[str, tuple[list[float], float]],
    threshold: float = 2.5,
    lta_window_s: float = 30.0,
) -> dict[str, DetectionResult]:
    """
    Esegue la rilevazione su più stazioni.

    Args:
        station_data: {station: (samples, sample_rate)}
        threshold:    soglia STA/LTA comune

    Returns:
        Dizionario {station: DetectionResult}

    NOTA: questo wrapper chiama detect_events per ogni stazione.
    Con il bug del mutable default, i risultati delle stazioni
    successive includono gli eventi di tutte le precedenti.
    """
    results = {}
    for station, (samples, sample_rate) in station_data.items():
        results[station] = detect_events(
            station=station,
            samples=samples,
            sample_rate=sample_rate,
            threshold=threshold,
            lta_window_s=lta_window_s,
            # BUG: events non viene passato esplicitamente
        )
    return results


def detect_events_continuous(
    station: str,
    chunks: list[list[float]],
    sample_rate: float,
    threshold: float = 2.5,
    sta_window_s: float = 1.0,
    lta_window_s: float = 30.0,
) -> DetectionResult:
    """
    Rilevazione su una traccia che arriva a blocchi consecutivi.

    Le tracce di monitoraggio non arrivano tutte insieme: la pipeline riceve
    record successivi della stessa stazione, uno dopo l'altro. Questa funzione
    li analizza in sequenza e mantiene l'elenco degli eventi trovati
    dall'inizio della traccia, restituendo un unico risultato cumulativo.

    Usata da scripts/continuous_monitor.py sulla rete in esercizio.

    Args:
        station:     codice stazione
        chunks:      blocchi consecutivi di campioni della stessa traccia
        sample_rate: campioni al secondo

    Returns:
        DetectionResult con tutti gli eventi della traccia.
    """
    accumulati: list = []
    ultimo = None
    campioni_totali = 0

    for blocco in chunks:
        ultimo = detect_events(
            station=station, samples=blocco, sample_rate=sample_rate,
            threshold=threshold, sta_window_s=sta_window_s,
            lta_window_s=lta_window_s, events=accumulati,
        )
        accumulati = ultimo.events
        campioni_totali += len(blocco)

    if ultimo is None:
        return DetectionResult(station=station, events=[], sta_lta_ratios=[],
                               threshold_used=threshold, samples_analyzed=0)

    return DetectionResult(
        station=station, events=accumulati,
        sta_lta_ratios=ultimo.sta_lta_ratios,
        threshold_used=threshold, samples_analyzed=campioni_totali,
    )
