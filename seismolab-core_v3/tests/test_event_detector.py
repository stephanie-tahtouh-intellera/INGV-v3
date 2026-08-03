"""
Test per seismolab/processing/event_detector.py

Questi test dimostrano il bug del mutable default argument in detect_events.
Usati dal docente durante la demo di triage in tempo reale.

Il pattern: un test su singola chiamata passa; un test su chiamate multiple
rivela il bug — il secondo test è quello che il partecipante scrive
durante il triage mentre il docente guida la diagnosis.
"""

import pytest
import math
from seismolab.processing.event_detector import (
    detect_events, batch_detect, compute_sta_lta,
    SeismicEvent, DetectionResult,
)

SAMPLE_RATE = 100.0


LTA_S = 5.0    # finestra LTA ridotta per i test (default 30s è troppo lunga)
LTA_N = int(LTA_S * SAMPLE_RATE)   # 500 campioni


def make_flat_signal(n: int = 3000, noise: float = 0.01) -> list[float]:
    """Segnale piatto con rumore minimo — nessun evento atteso."""
    import random
    random.seed(42)
    return [random.uniform(-noise, noise) for _ in range(n)]


def make_signal_with_event(n: int = 3000, event_start: int = 1500,
                            event_duration: int = 200,
                            amplitude: float = 5.0) -> list[float]:
    """Segnale con un singolo evento simulato (burst sinusoidale).
    n deve essere > LTA_N + event_start per avere la finestra LTA riempita.
    """
    samples = make_flat_signal(n)
    for i in range(event_start, min(event_start + event_duration, n)):
        t = (i - event_start) / event_duration
        samples[i] += amplitude * math.sin(math.pi * t)
    return samples


def _detect(station, samples, threshold=2.5):
    """Wrapper che passa esplicitamente events=[] per evitare il mutable default."""
    return detect_events(station, samples, SAMPLE_RATE,
                         threshold=threshold,
                         lta_window_s=LTA_S)


# ══════════════════════════════════════════════════════════════════
# Test su singola chiamata — questi passano con il bug
# ══════════════════════════════════════════════════════════════════

class TestSingleCall:

    def test_no_events_on_flat_signal(self):
        samples = make_flat_signal()
        result = detect_events("ETNA01", samples, SAMPLE_RATE,
                               threshold=2.5, lta_window_s=LTA_S, events=[])
        assert result.event_count == 0

    def test_detects_event_in_signal(self):
        samples = make_signal_with_event(amplitude=8.0)
        result = detect_events("ETNA02", samples, SAMPLE_RATE,
                               threshold=2.5, lta_window_s=LTA_S, events=[])
        assert result.event_count >= 1

    def test_result_has_correct_station(self):
        result = detect_events("STRO01", make_flat_signal(), SAMPLE_RATE,
                               lta_window_s=LTA_S, events=[])
        assert result.station == "STRO01"

    def test_threshold_affects_detection(self):
        """Soglia alta → meno eventi; soglia bassa → più eventi."""
        samples = make_signal_with_event(amplitude=6.0)
        high = detect_events("T", samples, SAMPLE_RATE,
                             threshold=5.0, lta_window_s=LTA_S, events=[])
        low = detect_events("T", samples, SAMPLE_RATE,
                            threshold=1.5, lta_window_s=LTA_S, events=[])
        assert low.event_count >= high.event_count


# ══════════════════════════════════════════════════════════════════
# Test su chiamate multiple — questi RIVELANO il bug
# Il docente guida il partecipante a scrivere questi test durante la demo
# ══════════════════════════════════════════════════════════════════

class TestMultipleCalls:

    def test_two_calls_independent_event_counts(self):
        """
        QUESTO TEST FALLISCE con il bug del mutable default.

        Con il fix (events=None e None → [] interno):
          - result1: 1 evento
          - result2: 0 eventi (segnale piatto)

        Con il bug (events=[] shared):
          - result1: 1 evento
          - result2: 1 evento (eredita dall'accumulatore)
        """
        signal_with_event = make_signal_with_event(amplitude=8.0)
        flat_signal = make_flat_signal()

        result1 = detect_events("ETNA01", signal_with_event, SAMPLE_RATE,
                                lta_window_s=LTA_S)
        result2 = detect_events("ETNA02", flat_signal, SAMPLE_RATE,
                                lta_window_s=LTA_S)

        assert result1.event_count >= 1, "La prima chiamata deve rilevare l'evento"
        assert result2.event_count == 0, (
            f"La seconda chiamata su segnale piatto deve dare 0 eventi, "
            f"trovato {result2.event_count}. "
            "Questo è il bug #0: mutable default argument."
        )

    def test_three_flat_calls_all_zero(self):
        """Tre chiamate su segnale piatto: ognuna deve dare 0 eventi."""
        for station in ["ETNA01", "ETNA02", "STRO01"]:
            result = detect_events(station, make_flat_signal(), SAMPLE_RATE,
                                   lta_window_s=LTA_S)
            assert result.event_count == 0, (
                f"Stazione {station}: atteso 0, trovato {result.event_count}"
            )

    def test_batch_detect_independent_per_station(self):
        """
        batch_detect su stazioni con segnali diversi:
        solo ETNA01 deve avere eventi.

        Con il bug: l'evento di ETNA01 compare anche in ETNA02 e STRO01.
        """
        station_data = {
            "ETNA01": (make_signal_with_event(amplitude=8.0), SAMPLE_RATE),
            "ETNA02": (make_flat_signal(), SAMPLE_RATE),
            "STRO01": (make_flat_signal(), SAMPLE_RATE),
        }
        results = batch_detect(station_data, threshold=2.5, lta_window_s=LTA_S)
        assert results["ETNA01"].event_count >= 1
        assert results["ETNA02"].event_count == 0, (
            f"ETNA02: atteso 0, trovato {results['ETNA02'].event_count}"
        )
        assert results["STRO01"].event_count == 0, (
            f"STRO01: atteso 0, trovato {results['STRO01'].event_count}"
        )


# ══════════════════════════════════════════════════════════════════
# compute_sta_lta — verifica dell'algoritmo
# ══════════════════════════════════════════════════════════════════

class TestComputeStaLta:

    def test_ratios_length_equals_samples(self):
        samples = make_flat_signal(500)
        ratios = compute_sta_lta(samples, SAMPLE_RATE)
        assert len(ratios) == len(samples)

    def test_initial_ratios_are_zero(self):
        """I primi lta_window_s secondi hanno ratio 0 (finestra LTA non riempita)."""
        samples = make_flat_signal(1000)
        ratios = compute_sta_lta(samples, SAMPLE_RATE, lta_window_s=10.0)
        # I primi 1000 campioni (10s) devono avere ratio 0
        first_n = int(10 * SAMPLE_RATE)
        assert all(r == 0.0 for r in ratios[:first_n])

    def test_ratio_increases_during_event(self):
        """Il ratio deve aumentare durante un evento."""
        samples = make_signal_with_event(n=3000, event_start=1500, amplitude=10.0)
        ratios = compute_sta_lta(samples, SAMPLE_RATE, lta_window_s=LTA_S)
        max_ratio = max(ratios)
        assert max_ratio > 2.5


# ══════════════════════════════════════════════════════════════════
# Issue #0 parte 2 — ottimizzazione a sliding window (performance)
# ══════════════════════════════════════════════════════════════════
#
# compute_sta_lta ricalcola le somme da zero ad ogni campione: O(n*finestra).
# La correzione mantiene le somme in modo incrementale: O(n).
# Questi test verificano che dopo l'ottimizzazione il RISULTATO NUMERICO
# resti identico (correttezza) e che la funzione regga tracce lunghe.

class TestSlidingWindowOptimization:

    def test_optimized_matches_reference_flat(self):
        """L'ottimizzazione deve dare gli stessi ratL su segnale piatto."""
        samples = make_flat_signal(2000)
        ratios = compute_sta_lta(samples, SAMPLE_RATE, lta_window_s=LTA_S)
        # Confronto con il calcolo di riferimento esplicito
        expected = _reference_sta_lta(samples, SAMPLE_RATE, 1.0, LTA_S)
        assert len(ratios) == len(expected)
        for a, b in zip(ratios, expected):
            assert abs(a - b) < 1e-9, "Il risultato deve restare identico dopo l'ottimizzazione"

    def test_optimized_matches_reference_event(self):
        """L'ottimizzazione deve dare gli stessi ratio su segnale con evento."""
        samples = make_signal_with_event(n=3000, event_start=1500, amplitude=10.0)
        ratios = compute_sta_lta(samples, SAMPLE_RATE, lta_window_s=LTA_S)
        expected = _reference_sta_lta(samples, SAMPLE_RATE, 1.0, LTA_S)
        for a, b in zip(ratios, expected):
            assert abs(a - b) < 1e-9

    def test_long_trace_completes_quickly(self):
        """Su una traccia lunga la funzione deve restare veloce (O(n))."""
        import time
        samples = make_flat_signal(30000)   # 5 min @ 100Hz
        t0 = time.time()
        compute_sta_lta(samples, SAMPLE_RATE, lta_window_s=30.0)
        elapsed = time.time() - t0
        # Con O(n) deve stare ampiamente sotto il secondo.
        # Con il bug O(n*finestra) impiega diversi secondi: il test fallisce.
        assert elapsed < 0.5, (
            f"compute_sta_lta ha impiegato {elapsed:.2f}s su 30k campioni: "
            "il ricalcolo O(n*finestra) va sostituito con somme scorrevoli."
        )


def _reference_sta_lta(samples, sample_rate, sta_window_s, lta_window_s):
    """Calcolo STA/LTA di riferimento, esplicito e lento. Oracolo per i test."""
    sta_n = max(1, int(sta_window_s * sample_rate))
    lta_n = max(sta_n + 1, int(lta_window_s * sample_rate))
    out = []
    for i in range(len(samples)):
        if i < lta_n:
            out.append(0.0)
            continue
        sta = sum(abs(s) for s in samples[i - sta_n:i]) / sta_n
        lta = sum(abs(s) for s in samples[i - lta_n:i]) / lta_n
        out.append(sta / lta if lta > 1e-10 else 0.0)
    return out
