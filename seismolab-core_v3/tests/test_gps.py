"""
Test per seismolab/data/gps_query.py

Copertura richiesta dall'issue #23:
- fetch_recent_measurements: caso principale, lista vuota, errore connessione
- fetch_displacement_summary: caso principale, trend, nessuna misurazione
- watch_anomalies: callback, nessuna anomalia, errore per singola stazione
- GpsMeasurement: proprietà calcolate, qualità
"""

import pytest
from unittest.mock import MagicMock, call
from datetime import datetime, timezone, timedelta
import psycopg2

from seismolab.data.gps_query import (
    fetch_recent_measurements, fetch_displacement_summary,
    watch_anomalies, GpsMeasurement, DisplacementSummary,
)
from tests.conftest import BASE_TIME


# Timestamp base per le misurazioni di test
T0 = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(hours=1)
T2 = T0 + timedelta(hours=2)


def _gps_row(station="ETNA01", dt=T0,
             lat=37.748, lon=14.994, elev=1500.0,
             dn=1.2, de=0.8, du=-0.3, quality=2):
    """Costruisce una riga raw come restituita da psycopg2."""
    return (station, dt, lat, lon, elev, dn, de, du, quality)


# ══════════════════════════════════════════════════════════════════
# fetch_recent_measurements
# ══════════════════════════════════════════════════════════════════

class TestFetchRecentMeasurements:

    def test_returns_measurements_for_station(self, mock_conn_factory):
        rows = [_gps_row("ETNA01", T0), _gps_row("ETNA01", T1)]
        conn, cursor = mock_conn_factory(rows)
        result = fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        assert len(result) == 2
        assert all(m.station == "ETNA01" for m in result)

    def test_returns_correct_fields(self, mock_conn_factory):
        rows = [_gps_row("STRO02", T0, dn=2.5, de=1.1, du=0.5)]
        conn, cursor = mock_conn_factory(rows)
        result = fetch_recent_measurements("STRO02", hours=12, conn=conn)
        m = result[0]
        assert m.station == "STRO02"
        assert m.recorded_at == T0
        assert pytest.approx(m.delta_n) == 2.5
        assert pytest.approx(m.delta_e) == 1.1

    def test_empty_result_returns_empty_list(self, mock_conn_factory):
        conn, cursor = mock_conn_factory([])
        result = fetch_recent_measurements("ETNA01", hours=1, conn=conn)
        assert result == []

    def test_uses_parametrized_query(self, mock_conn_factory):
        """Verifica che la query usi %s e non f-string."""
        conn, cursor = mock_conn_factory([])
        fetch_recent_measurements("ETNA01", hours=6, conn=conn)
        cursor.execute.assert_called_once()
        query, params = cursor.execute.call_args[0]
        assert "%s" in query, "La query deve usare placeholder %s"
        assert "ETNA01" not in query, "Il valore non deve essere nella stringa SQL"
        assert "ETNA01" in str(params)

    def test_raises_on_connection_error(self, mock_conn_factory):
        conn, cursor = mock_conn_factory([])
        cursor.execute.side_effect = psycopg2.OperationalError("connection refused")
        with pytest.raises(psycopg2.OperationalError):
            fetch_recent_measurements("ETNA01", conn=conn)

    def test_raises_on_invalid_hours(self, mock_conn_factory):
        conn, _ = mock_conn_factory([])
        with pytest.raises(ValueError):
            fetch_recent_measurements("ETNA01", hours=0, conn=conn)


# ══════════════════════════════════════════════════════════════════
# fetch_displacement_summary
# ══════════════════════════════════════════════════════════════════

class TestFetchDisplacementSummary:

    def test_returns_summary_with_correct_station(self, mock_conn_factory):
        rows = [_gps_row("ETNA01", T0, dn=1.0, de=0.5, du=0.2)]
        conn, _ = mock_conn_factory(rows)
        summary = fetch_displacement_summary("ETNA01", days=7, conn=conn)
        assert summary.station == "ETNA01"
        assert summary.period_days == 7

    def test_measurement_count_correct(self, mock_conn_factory):
        rows = [_gps_row(dt=T0), _gps_row(dt=T1), _gps_row(dt=T2)]
        conn, _ = mock_conn_factory(rows)
        summary = fetch_displacement_summary("ETNA01", conn=conn)
        assert summary.measurement_count == 3

    def test_empty_data_returns_zero_count(self, mock_conn_factory):
        conn, _ = mock_conn_factory([])
        summary = fetch_displacement_summary("ETNA01", conn=conn)
        assert summary.measurement_count == 0
        assert summary.max_horizontal_mm is None

    def test_increasing_trend_detected(self, mock_conn_factory):
        """Prima metà con spostamenti bassi, seconda metà con spostamenti alti."""
        rows = [
            _gps_row(dt=T0, dn=0.5, de=0.3),          # prima metà
            _gps_row(dt=T0 + timedelta(days=1), dn=0.5, de=0.3),
            _gps_row(dt=T0 + timedelta(days=4), dn=2.0, de=1.5),  # seconda metà
            _gps_row(dt=T0 + timedelta(days=5), dn=2.0, de=1.5),
        ]
        conn, _ = mock_conn_factory(rows)
        summary = fetch_displacement_summary("ETNA01", days=7, conn=conn)
        assert summary.overall_trend == "increasing"

    def test_raises_on_invalid_days(self, mock_conn_factory):
        conn, _ = mock_conn_factory([])
        with pytest.raises(ValueError):
            fetch_displacement_summary("ETNA01", days=-1, conn=conn)


# ══════════════════════════════════════════════════════════════════
# watch_anomalies
# ══════════════════════════════════════════════════════════════════

class TestWatchAnomalies:

    def _make_conn_for_station(self, station, rows):
        """Mock connection che restituisce rows diverse per ogni stazione."""
        from unittest.mock import patch, MagicMock
        # Usiamo side_effect su fetch_recent_measurements direttamente
        return rows

    def test_callback_called_for_anomaly(self, mock_conn_factory):
        """Un spostamento > soglia deve invocare il callback."""
        row = _gps_row("ETNA01", T0, dn=5.0, de=5.0)  # magnitude ~7.07mm
        conn, _ = mock_conn_factory([row])
        callback = MagicMock()
        count = watch_anomalies(
            stations=["ETNA01"],
            threshold_mm=5.0,
            callback=callback,
            hours=1,
            conn=conn,
        )
        assert count == 1
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "ETNA01"

    def test_no_callback_below_threshold(self, mock_conn_factory):
        row = _gps_row("ETNA01", T0, dn=1.0, de=0.5)  # magnitude ~1.12mm
        conn, _ = mock_conn_factory([row])
        callback = MagicMock()
        count = watch_anomalies(
            stations=["ETNA01"],
            threshold_mm=5.0,
            callback=callback,
            conn=conn,
        )
        assert count == 0
        callback.assert_not_called()

    def test_raises_on_invalid_threshold(self, mock_conn_factory):
        conn, _ = mock_conn_factory([])
        with pytest.raises(ValueError):
            watch_anomalies(["ETNA01"], threshold_mm=0, callback=lambda s, m: None,
                            conn=conn)


# ══════════════════════════════════════════════════════════════════
# GpsMeasurement — proprietà calcolate
# ══════════════════════════════════════════════════════════════════

class TestGpsMeasurement:

    def test_displacement_magnitude_correct(self):
        m = GpsMeasurement(
            station="TEST", recorded_at=T0,
            latitude=0, longitude=0, elevation=0,
            delta_n=3.0, delta_e=4.0,
        )
        assert pytest.approx(m.displacement_magnitude) == 5.0  # 3-4-5

    def test_displacement_magnitude_none_when_missing(self):
        m = GpsMeasurement(
            station="TEST", recorded_at=T0,
            latitude=0, longitude=0, elevation=0,
        )
        assert m.displacement_magnitude is None

    def test_high_quality_flag(self):
        m_high = GpsMeasurement(station="T", recorded_at=T0,
                                latitude=0, longitude=0, elevation=0, quality=2)
        m_low = GpsMeasurement(station="T", recorded_at=T0,
                               latitude=0, longitude=0, elevation=0, quality=1)
        assert m_high.is_high_quality is True
        assert m_low.is_high_quality is False
