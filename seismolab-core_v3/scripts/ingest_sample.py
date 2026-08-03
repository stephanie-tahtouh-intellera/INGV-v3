"""
Script di demo per SeismoLab Core.

Esegue la pipeline di ingestione su dati sintetici e mostra
l'output di ogni modulo. Usato durante U1 per la demo live.

Ogni sezione dell'output corrisponde a una delle quattro issue del modulo:
- Issue #12: MiniSEED parser con gap temporali (demo docente)
- Issue #17: alerting vulcanologico con soglie
- Issue #23: GPS queries (stub — NotImplementedError atteso)
- Issue #0:  rilevazione eventi con STA/LTA
"""

import math
import random

# ── Setup dati sintetici ──────────────────────────────────────────
BASE_TIME = 1_700_000_000.0
SAMPLE_RATE = 100.0

random.seed(42)


def sine_samples(n: int, amplitude: float = 1.0, freq: float = 2.0) -> list[float]:
    return [amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE)
            for i in range(n)]


def noisy_samples(n: int, noise: float = 0.05) -> list[float]:
    return [random.uniform(-noise, noise) for _ in range(n)]


# ════════════════════════════════════════════════════════════════
# SEZIONE 1 — Issue #12: MiniSEED parser
# ════════════════════════════════════════════════════════════════
print("=" * 60)
print("SEZIONE 1 — MiniSEED parser (Issue #12)")
print("=" * 60)

from seismolab.parsers.mseed import parse_mseed, validate_trace

raw_data = [
    # ETNA01.HHZ — tre record: due normali + uno con gap di 3s
    {"station": "ETNA01", "channel": "HHZ", "location": "00",
     "start_time": BASE_TIME, "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(100, amplitude=0.8)},
    {"station": "ETNA01", "channel": "HHZ", "location": "00",
     "start_time": BASE_TIME + 1.0, "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(100, amplitude=0.9)},
    {"station": "ETNA01", "channel": "HHZ", "location": "00",
     "start_time": BASE_TIME + 1.0 + 3.0,  # gap di 3 secondi
     "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(100, amplitude=0.7)},
    # ETNA01.HHN — canale Nord
    {"station": "ETNA01", "channel": "HHN", "location": "00",
     "start_time": BASE_TIME, "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(200, amplitude=0.6)},
    # STRO02.HHZ — seconda stazione, record contigui
    {"station": "STRO02", "channel": "HHZ", "location": "00",
     "start_time": BASE_TIME, "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(100, amplitude=1.2)},
    {"station": "STRO02", "channel": "HHZ", "location": "00",
     "start_time": BASE_TIME + 1.0, "sample_rate": SAMPLE_RATE,
     "samples": sine_samples(100, amplitude=1.3)},
]

result = parse_mseed(raw_data)

print(f"Tracce rilevate: {len(result.traces)}")
print(f"Record parsati:  {result.total_records_parsed}")
print(f"Record scartati: {result.total_records_skipped}  ← bug #12 se > 0")
print()

for trace in sorted(result.traces, key=lambda t: (t.station, t.channel)):
    report = validate_trace(trace)
    print(f"  {trace.station}.{trace.location}.{trace.channel}:")
    print(f"    campioni totali : {trace.total_samples}")
    print(f"    record          : {len(trace.records)}")
    print(f"    gap rilevati    : {len(trace.gaps)}")
    print(f"    copertura       : {trace.coverage_percent:.1f}%")
    if trace.gaps:
        for g in trace.gaps:
            print(f"    gap             : {g.gap_seconds:.2f}s "
                  f"(~{g.samples_lost} campioni persi)")
    if report["warnings"]:
        for w in report["warnings"]:
            print(f"    ⚠  {w}")
    print()

print(f"Stazioni nell'output: {sorted(result.stations)}")
print()
print("OUTPUT ATTESO con fix #12:")
print("  ETNA01.HHZ — 300 campioni, 1 gap di ~3.0s")
print("  ETNA01.HHN — 200 campioni, 0 gap")
print("  STRO02.HHZ — 200 campioni, 0 gap")
print("  Record scartati: 0")

# ════════════════════════════════════════════════════════════════
# SEZIONE 2 — Issue #17: alerting vulcanologico
# ════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("SEZIONE 2 — Alerting vulcanologico (Issue #17)")
print("=" * 60)

from seismolab.alerts.volcanic import (
    TremorReading, evaluate_alert, batch_evaluate,
    highest_alert, summarize_alerts,
)

readings = [
    TremorReading("ETNA01", BASE_TIME,      0.1,  0.1,  0.05, 0.5),
    TremorReading("ETNA01", BASE_TIME+3600, 0.35, 0.2,  0.1,  1.5),
    TremorReading("ETNA01", BASE_TIME+7200, 0.65, 0.45, 0.3,  3.5),
    TremorReading("ETNA01", BASE_TIME+7800, 1.1,  0.9,  0.8,  8.0),
    # STRO01 — con override soglie alzate
    TremorReading("STRO01", BASE_TIME,      0.55, 0.2,  0.1,  2.5),
    TremorReading("STRO01", BASE_TIME+3600, 0.65, 0.3,  0.15, 3.0),
]

alerts = batch_evaluate(readings)
print(f"Letture valutate: {len(readings)}")
print()
print("Dettaglio allerte:")
for a in alerts:
    src = f" [{a.threshold_source}]" if a.threshold_source != "default" else ""
    print(f"  {a.station} t+{int(a.timestamp - BASE_TIME):4d}s: "
          f"{a.level.value.upper():<7}{src}")
    if a.level.value != "green":
        print(f"    → {a.reason}")

peak = highest_alert(alerts)
print(f"\nLivello massimo: {peak.level.value.upper()} @ {peak.station}")
try:
    summary = summarize_alerts(alerts)
    print(f"Riepilogo: {summary['by_level']}")
except NotImplementedError:
    print("Riepilogo: summarize_alerts non ancora implementata (issue #17)")

print("\nOUTPUT ATTESO con fix #17:")
print("  ETNA01: GREEN → YELLOW → ORANGE → RED (soglie default)")
print("  STRO01: YELLOW → YELLOW (soglie override STRO01 alzate)")
print("  threshold_source: 'default' per ETNA01, 'station_override' per STRO01")

# ════════════════════════════════════════════════════════════════
# SEZIONE 3 — Issue #23: GPS queries
# ════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("SEZIONE 3 — GPS queries (Issue #23 — stub)")
print("=" * 60)

from seismolab.data.gps_query import fetch_recent_measurements

try:
    fetch_recent_measurements("ETNA01", hours=24)
    print("  ✗  ERRORE: fetch_recent_measurements non ha sollevato NotImplementedError")
except NotImplementedError as e:
    print(f"  ✓  NotImplementedError atteso: {e}")
except Exception as e:
    print(f"  ✗  Eccezione inattesa: {type(e).__name__}: {e}")

print("  Da implementare: get_connection, fetch_recent_measurements,")
print("                   fetch_displacement_summary, watch_anomalies")

# ════════════════════════════════════════════════════════════════
# SEZIONE 4 — Issue #0: event detector
# ════════════════════════════════════════════════════════════════
print()
print("=" * 60)
print("SEZIONE 4 — Event detector STA/LTA (Issue #0)")
print("=" * 60)

from seismolab.processing.event_detector import detect_events, batch_detect
import math

LTA_S = 5.0   # finestra LTA ridotta (default 30s è più lunga del segnale demo)

def make_event_signal(n=3000, event_start=1500, duration=200, amp=8.0):
    sig = noisy_samples(n, noise=0.02)
    for i in range(event_start, min(event_start + duration, n)):
        t = (i - event_start) / duration
        sig[i] += amp * math.sin(math.pi * t)
    return sig

station_data = {
    "ETNA01": (make_event_signal(), SAMPLE_RATE),              # ha un evento
    "ETNA02": (noisy_samples(3000, noise=0.02), SAMPLE_RATE),  # piatto
    "STRO01": (noisy_samples(3000, noise=0.02), SAMPLE_RATE),  # piatto
}

results = batch_detect(station_data, threshold=2.5, lta_window_s=LTA_S)

print("Conteggio eventi per stazione:")
for station, res in results.items():
    print(f"  {station}: {res.event_count} eventi rilevati")

print()
print("OUTPUT ATTESO con fix #0:")
print("  ETNA01: 1 evento")
print("  ETNA02: 0 eventi")
print("  STRO01: 0 eventi")
print()
print("OUTPUT CON BUG #0 (prima del fix):")
print("  ETNA01: 1 evento")
print("  ETNA02: 1 evento  ← bug: accumulo mutable default")
print("  STRO01: 1 evento  ← bug: accumulo mutable default")
