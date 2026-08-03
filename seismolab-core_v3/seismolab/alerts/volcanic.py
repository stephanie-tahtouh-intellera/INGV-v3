"""
Sistema di alerting per attività vulcanologica.

Monitora il tremore vulcanico e genera allerte in base all'ampiezza
del segnale su diverse bande di frequenza e agli spostamenti GPS.

Issue #17 — PROBLEMA DI DESIGN: le 12 soglie di allerta sono hardcoded
nel corpo di evaluate_alert come letterali numerici. Questo impedisce:
1. La calibrazione per stazione senza modificare il sorgente
2. Il testing con soglie controllate
3. L'aggiornamento operativo senza rilascio del codice

Il refactoring deve:
- Estrarre le soglie in un dizionario opzionale `thresholds: dict | None = None`
- Se None, usare i valori attuali come default (retrocompatibilità obbligatoria)
- Supportare override per singola stazione via `station_overrides: dict | None = None`
- Aggiungere `summarize_alerts()` per statistiche aggregate
- Garantire che tutti i test attuali in TestEvaluateAlertDefault passino invariati
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AlertLevel(Enum):
    GREEN  = "green"
    YELLOW = "yellow"
    ORANGE = "orange"
    RED    = "red"


@dataclass
class TremorReading:
    """Lettura di tremore vulcanico da una stazione."""
    station: str
    timestamp: float
    amplitude_low: float
    amplitude_mid: float
    amplitude_high: float
    displacement: float
    quality_factor: float = 1.0


@dataclass
class Alert:
    """Allerta generata dal sistema."""
    station: str
    timestamp: float
    level: AlertLevel
    reason: str
    reading: TremorReading
    threshold_source: str = "default"


def evaluate_alert(reading: TremorReading) -> Alert:
    """
    Valuta una lettura di tremore e restituisce il livello di allerta.

    Issue #17 — soglie hardcoded da estrarre:
        LOW_YELLOW=0.3, LOW_ORANGE=0.6, LOW_RED=0.9
        MID_YELLOW=0.4, MID_ORANGE=0.7, MID_RED=1.1
        HIGH_YELLOW=0.2, HIGH_ORANGE=0.5, HIGH_RED=0.85
        DISP_YELLOW=2.0, DISP_ORANGE=5.0, DISP_RED=10.0
    """
    if (reading.amplitude_low  >= 0.9 or
        reading.amplitude_mid  >= 1.1 or
        reading.amplitude_high >= 0.85 or
        reading.displacement   >= 10.0):
        return Alert(station=reading.station, timestamp=reading.timestamp,
                     level=AlertLevel.RED,
                     reason=_build_reason(reading, "RED"),
                     reading=reading)

    if (reading.amplitude_low  >= 0.6 or
        reading.amplitude_mid  >= 0.7 or
        reading.amplitude_high >= 0.5 or
        reading.displacement   >= 5.0):
        return Alert(station=reading.station, timestamp=reading.timestamp,
                     level=AlertLevel.ORANGE,
                     reason=_build_reason(reading, "ORANGE"),
                     reading=reading)

    if (reading.amplitude_low  >= 0.3 or
        reading.amplitude_mid  >= 0.4 or
        reading.amplitude_high >= 0.2 or
        reading.displacement   >= 2.0):
        return Alert(station=reading.station, timestamp=reading.timestamp,
                     level=AlertLevel.YELLOW,
                     reason=_build_reason(reading, "YELLOW"),
                     reading=reading)

    return Alert(station=reading.station, timestamp=reading.timestamp,
                 level=AlertLevel.GREEN,
                 reason="Nessuna anomalia rilevata",
                 reading=reading)


def batch_evaluate(readings: list[TremorReading]) -> list[Alert]:
    """Valuta una lista di letture. Issue #17: aggiungere parametri thresholds e include_green."""
    return [evaluate_alert(r) for r in readings]


def highest_alert(alerts: list[Alert]) -> Optional[Alert]:
    """Restituisce l'allerta con livello più alto dalla lista."""
    if not alerts:
        return None
    order = [AlertLevel.GREEN, AlertLevel.YELLOW, AlertLevel.ORANGE, AlertLevel.RED]
    return max(alerts, key=lambda a: order.index(a.level))


def summarize_alerts(alerts: list[Alert]) -> dict:
    """
    Produce un riepilogo delle allerte per una sessione di monitoraggio.

    Issue #17: da implementare durante il refactoring.
    Returns:
        Dizionario con conteggi per livello, stazione più attiva,
        e timestamp della prima e ultima allerta non-GREEN.
    """
    raise NotImplementedError("Issue #17 — da implementare")


def _build_reason(reading: TremorReading, level: str) -> str:
    parts = []
    if reading.amplitude_high >= 0.2:
        parts.append(f"tremore HF={reading.amplitude_high:.2f}")
    if reading.amplitude_mid >= 0.4:
        parts.append(f"tremore MF={reading.amplitude_mid:.2f}")
    if reading.amplitude_low >= 0.3:
        parts.append(f"tremore LF={reading.amplitude_low:.2f}")
    if reading.displacement >= 2.0:
        parts.append(f"spostamento={reading.displacement:.1f}mm")
    return f"Livello {level}: " + ", ".join(parts) if parts else f"Livello {level}"
