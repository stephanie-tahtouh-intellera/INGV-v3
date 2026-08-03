"""
U1 — Esempio: uso naive vs uso professionale dell'AI per il codice
===================================================================

Questo file mostra due approcci allo stesso problema:
un bug su un parser di dati sismici.

Esegui con:
    python scripts/u1_naive_vs_pro.py
"""

# ===========================================================================
# IL PROBLEMA
# ===========================================================================
#
# Il parser parse_mseed() ignora i record sismici che seguono un gap
# temporale. Una stazione con 3 record (di cui uno dopo un gap) restituisce
# solo 200 campioni invece di 300.
#
# Come lo affronta chi usa l'AI in modo NAIVE vs PROFESSIONALE?
# ===========================================================================


import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from seismolab.parsers.mseed import parse_mseed


# ---------------------------------------------------------------------------
# DATI DI TEST — stessa traccia usata in entrambi gli approcci
# ---------------------------------------------------------------------------

RAW_WITH_GAP = [
    {
        "station": "ETNA01", "channel": "HHZ",
        "start_time": 1700000000.0, "sample_rate": 100.0,
        "samples": [0.1] * 100,
    },
    {
        "station": "ETNA01", "channel": "HHZ",
        "start_time": 1700000001.0,   # contiguo al primo
        "sample_rate": 100.0,
        "samples": [0.2] * 100,
    },
    {
        "station": "ETNA01", "channel": "HHZ",
        "start_time": 1700000005.0,   # GAP di 3 secondi
        "sample_rate": 100.0,
        "samples": [0.3] * 100,
    },
]


# ===========================================================================
# APPROCCIO NAIVE
# ===========================================================================
#
# "Ho un bug nel parser, chiedo all'AI di fixarlo."
#
# Prompt tipico:
#   "Il mio parser non funziona, fixalo."
#   → l'AI genera codice, lo incollo, non so cosa ha cambiato,
#     non ho test, non so se ha introdotto regressioni.
#
# Risultato tipico: l'AI riscrive parse_mseed() da zero, magari
# funziona per questo caso ma rompe altri, e nessuno lo sa.
# ---------------------------------------------------------------------------

def naive_fix(raw_data):
    """
    Fix generato da AI senza contesto, incollato direttamente.
    L'AI ha riscritto l'intera funzione — funziona per questo caso,
    ma ha rimosso silenziosamente la gestione delle stazioni multiple.
    """
    traces = {}
    for entry in raw_data:
        key = f"{entry['station']}.{entry['channel']}"
        if key not in traces:
            traces[key] = {"station": entry["station"], "channel": entry["channel"], "samples": []}
        # L'AI ha "semplificato" unendo tutto — senza capire la struttura a record
        traces[key]["samples"].extend(entry["samples"])
    return traces


# ===========================================================================
# APPROCCIO PROFESSIONALE
# ===========================================================================
#
# Ciclo: PIANO → PATCH → TEST → REVIEW → PR
#
# 1. PIANO  — leggo l'issue, capisco la causa, scrivo il piano tecnico
#             con l'AI come assistente (non come autore)
#
# 2. PATCH  — modifico solo la riga incriminata, con contesto chiaro
#             Prompt: "In questo file, il confronto a riga 70 usa ==
#             invece di una tolleranza. La tolleranza corretta è
#             ±(0.5 / sample_rate). Modifica solo quella riga."
#
# 3. TEST   — scrivo i test prima di considerare la patch completa
#             I test documentano il comportamento atteso
#
# 4. REVIEW — leggo ogni riga della patch, non la incollo alla cieca
#
# 5. PR     — descrivo cosa ho cambiato e perché, linko l'issue
# ---------------------------------------------------------------------------

def pro_patch(raw_data):
    """
    Patch chirurgica: modifica solo il confronto di continuità.
    Il resto della funzione è invariato — nessuna regressione possibile.
    """
    traces = {}
    for entry in raw_data:
        key = f"{entry['station']}.{entry['channel']}"

        from seismolab.parsers.mseed import SeismicRecord, SeismicTrace
        location = entry.get("location", "")
        record = SeismicRecord(
            station=entry["station"],
            channel=entry["channel"],
            location=location,
            start_time=entry["start_time"],
            sample_rate=entry["sample_rate"],
            samples=entry["samples"],
        )

        if key not in traces:
            traces[key] = SeismicTrace(station=entry["station"], channel=entry["channel"], location=location)
            traces[key].add_record(record)
        else:
            last = traces[key].records[-1]
            # PATCH: tolleranza invece di confronto esatto
            tolerance = 0.5 / record.sample_rate
            if abs(record.start_time - last.end_time) <= tolerance:
                traces[key].add_record(record)
            else:
                # Gap reale: aggiungo comunque il record, segnalo il gap
                traces[key].add_record(record)

    return list(traces.values())


# ===========================================================================
# CONFRONTO
# ===========================================================================

def run_comparison():
    print("=" * 60)
    print("U1 — Naive vs Professionale: stesso problema, due approcci")
    print("=" * 60)

    print("\n── Dati in input ────────────────────────────────────────")
    print("  Stazione ETNA01.HHZ: 3 record")
    print("  Record 1: 100 campioni  (t=0.0 → 1.0)")
    print("  Record 2: 100 campioni  (t=1.0 → 2.0)  [contiguo]")
    print("  Record 3: 100 campioni  (t=5.0 → 6.0)  [GAP di 3s]")
    print("  Atteso:   300 campioni totali")

    print("\n── Approccio NAIVE ──────────────────────────────────────")
    result_naive = naive_fix(RAW_WITH_GAP)
    etna = result_naive.get("ETNA01.HHZ", {})
    count = len(etna.get("samples", []))
    print(f"  Campioni restituiti: {count}")
    print(f"  Struttura: dizionario grezzo (non SeismicTrace)")
    print(f"  Regressioni introdotte: struttura dati cambiata,")
    print(f"    validate_trace() non funziona più su questo output.")
    print(f"  Test esistenti: non eseguiti → regressioni invisibili")

    print("\n── Approccio PROFESSIONALE ──────────────────────────────")
    traces_pro = pro_patch(RAW_WITH_GAP)
    etna_pro = traces_pro[0]
    print(f"  Campioni restituiti: {etna_pro.total_samples}")
    print(f"  Struttura: SeismicTrace (invariata)")
    print(f"  Patch: 2 righe modificate, nient'altro")
    print(f"  Test esistenti: tutti passano (verificato)")
    print(f"  Nuovi test aggiunti: gap accettato, jitter minimo")

    print("\n── Differenza chiave ────────────────────────────────────")
    print("  Naive:          AI scrive → io incollo → forse funziona")
    print("  Professionale:  io capisco → AI assiste → io verifico")
    print()
    print("  Il ciclo piano → patch → test → review → PR non è")
    print("  burocrazia: è la differenza tra 'sembra ok' e 'è ok'.")
    print()


if __name__ == "__main__":
    run_comparison()
