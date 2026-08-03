"""
Test per seismolab/alerts/volcanic.py

Copertura richiesta dall'issue #17:
- evaluate_alert: tutti i livelli con soglie default
- evaluate_alert: retrocompatibilità (chiamata senza thresholds)
- evaluate_alert: soglie custom tramite parametro
- evaluate_alert: override per stazione (STRO01, ETNA02)
- batch_evaluate: liste miste, filtro GREEN
- highest_alert: ordinamento corretto
- summarize_alerts: statistiche aggregate
"""

import pytest
from seismolab.alerts.volcanic import (
    evaluate_alert, batch_evaluate, highest_alert, summarize_alerts,
    AlertLevel, TremorReading, Alert,
)
from tests.conftest import BASE_TIME


# ══════════════════════════════════════════════════════════════════
# evaluate_alert — soglie default (retrocompatibilità)
# ══════════════════════════════════════════════════════════════════

class TestEvaluateAlertDefault:

    def test_green_below_all_thresholds(self, reading_green):
        alert = evaluate_alert(reading_green)
        assert alert.level == AlertLevel.GREEN

    def test_yellow_triggered_by_low_amplitude(self, reading_yellow_low):
        alert = evaluate_alert(reading_yellow_low)
        assert alert.level == AlertLevel.YELLOW

    def test_orange_triggered(self, reading_orange):
        alert = evaluate_alert(reading_orange)
        assert alert.level == AlertLevel.ORANGE

    def test_red_triggered(self, reading_red):
        alert = evaluate_alert(reading_red)
        assert alert.level == AlertLevel.RED

    def test_alert_station_preserved(self, reading_green):
        alert = evaluate_alert(reading_green)
        assert alert.station == reading_green.station

    def test_alert_timestamp_preserved(self, reading_green):
        alert = evaluate_alert(reading_green)
        assert alert.timestamp == BASE_TIME

    def test_threshold_boundary_yellow_exact(self):
        """Un valore esattamente sulla soglia YELLOW deve dare YELLOW."""
        reading = TremorReading(
            station="ETNA01", timestamp=BASE_TIME,
            amplitude_low=0.3,    # esattamente LOW_YELLOW
            amplitude_mid=0.0,
            amplitude_high=0.0,
            displacement=0.0,
        )
        assert evaluate_alert(reading).level == AlertLevel.YELLOW

    def test_threshold_just_below_yellow(self):
        """Un valore appena sotto la soglia YELLOW deve dare GREEN."""
        reading = TremorReading(
            station="ETNA01", timestamp=BASE_TIME,
            amplitude_low=0.299,  # appena sotto LOW_YELLOW=0.3
            amplitude_mid=0.0,
            amplitude_high=0.0,
            displacement=0.0,
        )
        assert evaluate_alert(reading).level == AlertLevel.GREEN

    def test_displacement_alone_triggers_yellow(self):
        """Il solo spostamento GPS sopra la soglia deve dare YELLOW."""
        reading = TremorReading(
            station="ETNA01", timestamp=BASE_TIME,
            amplitude_low=0.0, amplitude_mid=0.0, amplitude_high=0.0,
            displacement=2.5,   # > DISP_YELLOW=2.0
        )
        assert evaluate_alert(reading).level == AlertLevel.YELLOW


# ══════════════════════════════════════════════════════════════════
# evaluate_alert — soglie custom e override stazione
# ══════════════════════════════════════════════════════════════════

class TestEvaluateAlertCustomThresholds:

    def test_custom_thresholds_override_defaults(self):
        """Con soglie personalizzate, i livelli cambiano di conseguenza."""
        reading = TremorReading(
            station="TEST", timestamp=BASE_TIME,
            amplitude_low=0.5, amplitude_mid=0.0,
            amplitude_high=0.0, displacement=0.0,
        )
        # Con default: 0.5 >= LOW_ORANGE=0.6? No → YELLOW
        default_alert = evaluate_alert(reading)
        assert default_alert.level == AlertLevel.YELLOW

        # Con soglie custom abbassate: 0.5 >= LOW_ORANGE=0.4? Sì → ORANGE
        custom = {"LOW_YELLOW": 0.2, "LOW_ORANGE": 0.4, "LOW_RED": 0.8,
                  "MID_YELLOW": 0.4, "MID_ORANGE": 0.7, "MID_RED": 1.1,
                  "HIGH_YELLOW": 0.2, "HIGH_ORANGE": 0.5, "HIGH_RED": 0.85,
                  "DISP_YELLOW": 2.0, "DISP_ORANGE": 5.0, "DISP_RED": 10.0}
        custom_alert = evaluate_alert(reading, thresholds=custom)
        assert custom_alert.level == AlertLevel.ORANGE

    def test_stro01_override_raises_threshold(self, reading_stro_yellow):
        """STRO01 ha soglie alzate: reading_orange deve dare YELLOW, non ORANGE."""
        alert = evaluate_alert(reading_stro_yellow)
        assert alert.level == AlertLevel.YELLOW
        assert alert.threshold_source == "station_override"

    def test_etna01_no_override_uses_default(self, reading_orange):
        alert = evaluate_alert(reading_orange)
        assert alert.threshold_source == "default"

    def test_custom_thresholds_source_label(self, reading_green):
        custom = {k: 99.0 for k in [
            "LOW_YELLOW","LOW_ORANGE","LOW_RED",
            "MID_YELLOW","MID_ORANGE","MID_RED",
            "HIGH_YELLOW","HIGH_ORANGE","HIGH_RED",
            "DISP_YELLOW","DISP_ORANGE","DISP_RED",
        ]}
        alert = evaluate_alert(reading_green, thresholds=custom)
        assert alert.threshold_source == "custom"


# ══════════════════════════════════════════════════════════════════
# batch_evaluate
# ══════════════════════════════════════════════════════════════════

class TestBatchEvaluate:

    def test_batch_returns_one_per_reading(
        self, reading_green, reading_yellow_low, reading_orange
    ):
        alerts = batch_evaluate([reading_green, reading_yellow_low, reading_orange])
        assert len(alerts) == 3

    def test_batch_filters_green(self, reading_green, reading_yellow_low):
        alerts = batch_evaluate(
            [reading_green, reading_yellow_low], include_green=False
        )
        assert len(alerts) == 1
        assert alerts[0].level == AlertLevel.YELLOW

    def test_batch_empty_input(self):
        assert batch_evaluate([]) == []


# ══════════════════════════════════════════════════════════════════
# highest_alert e summarize_alerts
# ══════════════════════════════════════════════════════════════════

class TestAlertAggregation:

    def test_highest_alert_selects_red(
        self, reading_green, reading_yellow_low, reading_red
    ):
        alerts = batch_evaluate([reading_green, reading_yellow_low, reading_red])
        peak = highest_alert(alerts)
        assert peak.level == AlertLevel.RED

    def test_highest_alert_empty_list(self):
        assert highest_alert([]) is None

    def test_summarize_counts_by_level(
        self, reading_green, reading_yellow_low, reading_orange
    ):
        alerts = batch_evaluate([reading_green, reading_yellow_low, reading_orange])
        summary = summarize_alerts(alerts)
        assert summary["by_level"]["green"] == 1
        assert summary["by_level"]["yellow"] == 1
        assert summary["by_level"]["orange"] == 1
        assert summary["total"] == 3

    def test_summarize_empty(self):
        summary = summarize_alerts([])
        assert summary["total"] == 0
