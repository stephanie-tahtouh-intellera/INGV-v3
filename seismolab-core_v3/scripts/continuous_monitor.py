"""
Monitoraggio continuo di una stazione sismica.

Le tracce non arrivano tutte insieme: la pipeline riceve record successivi
della stessa stazione. Questo script simula quel flusso e usa
detect_events_continuous per mantenere il conteggio degli eventi lungo tutta
la traccia, non blocco per blocco.

Uso:
    python scripts/continuous_monitor.py
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seismolab.processing.event_detector import detect_events_continuous

SAMPLE_RATE = 100.0
LTA_WINDOW_S = 5.0
DURATA_BLOCCO = 3000          # 30 secondi a 100 Hz


def blocco_con_evento(n=DURATA_BLOCCO, inizio=1500, durata=200, ampiezza=9.0):
    campioni = [0.02] * n
    for i in range(inizio, min(inizio + durata, n)):
        t = (i - inizio) / durata
        campioni[i] += ampiezza * math.sin(math.pi * t)
    return campioni


def blocco_quieto(n=DURATA_BLOCCO):
    return [0.02] * n


def main():
    # Tre record consecutivi della stessa traccia di ETNA01: il primo e il
    # terzo contengono un evento, il secondo è quieto.
    record = [blocco_con_evento(), blocco_quieto(), blocco_con_evento()]

    print("=" * 60)
    print("MONITORAGGIO CONTINUO — ETNA01")
    print("=" * 60)
    print(f"Record ricevuti: {len(record)}")
    print(f"Campioni per record: {DURATA_BLOCCO}")
    print()

    risultato = detect_events_continuous(
        station="ETNA01",
        chunks=record,
        sample_rate=SAMPLE_RATE,
        lta_window_s=LTA_WINDOW_S,
    )

    print(f"Eventi rilevati sulla traccia completa: {risultato.event_count}")
    print(f"Campioni analizzati: {risultato.samples_analyzed}")
    print()
    for i, ev in enumerate(risultato.events, 1):
        marca = "significativo" if ev.is_significant else "sotto soglia"
        print(f"  evento {i}: onset {ev.onset_time:7.2f}s dall'inizio del "
              f"proprio record  durata {ev.duration_s:5.2f}s  "
              f"picco {ev.peak_ratio:5.2f}  {marca}")

    print()
    print("Il conteggio deve riguardare tutta la traccia: gli eventi dei record")
    print("già elaborati non vanno perduti quando arriva il record successivo.")


if __name__ == "__main__":
    main()
