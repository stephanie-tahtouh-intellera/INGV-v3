"""
Fixtures condivise per i test di SeismoLab Core.

Fornisce dati di test realistici per tutte le suite di test.
I timestamp usano valori fissi (epoch 1700000000 ~= 14/11/2023 22:13 UTC)
per garantire riproducibilità indipendente dall'ora di esecuzione.
"""

import pytest
from seismolab.parsers.mseed import SeismicRecord, SeismicTrace, ParseResult
from seismolab.alerts.volcanic import TremorReading
from seismolab.data.gps_query import GpsMeasurement
from datetime import datetime, timezone


BASE_TIME = 1_700_000_000.0   # timestamp fisso per tutti i test
SAMPLE_RATE = 100.0            # Hz standard per sismometri HH*


# ── MiniSEED fixtures ──────────────────────────────────────────────

def make_record(
    station: str = "ETNA01",
    channel: str = "HHZ",
    start_time: float = BASE_TIME,
    sample_count: int = 100,
    sample_rate: float = SAMPLE_RATE,
    amplitude: float = 1.0,
    location: str = "00",
) -> SeismicRecord:
    """Costruisce un SeismicRecord con campioni sinusoidali."""
    import math
    samples = [amplitude * math.sin(2 * math.pi * i / sample_count)
               for i in range(sample_count)]
    return SeismicRecord(
        station=station,
        channel=channel,
        location=location,
        start_time=start_time,
        sample_rate=sample_rate,
        samples=samples,
    )


@pytest.fixture
def record_etna_100():
    """Record ETNA01 con 100 campioni a 100 Hz."""
    return make_record()


@pytest.fixture
def record_etna_200():
    """Record ETNA01 contiguo con 200 campioni, parte da t+1s."""
    return make_record(start_time=BASE_TIME + 1.0, sample_count=200)


@pytest.fixture
def record_etna_gap():
    """Record ETNA01 con gap di 3 secondi rispetto alla baseline."""
    return make_record(start_time=BASE_TIME + 1.0 + 3.0, sample_count=100)


@pytest.fixture
def record_etna_jitter():
    """Record ETNA01 con jitter minimo (4ms a 100 Hz, entro tolleranza)."""
    return make_record(start_time=BASE_TIME + 1.0 + 0.004, sample_count=100)


@pytest.fixture
def raw_data_no_gap():
    """Due record ETNA01 contigui senza gap."""
    r1 = make_record(start_time=BASE_TIME, sample_count=100)
    r2 = make_record(start_time=BASE_TIME + 1.0, sample_count=200)
    return [
        {"station": r1.station, "channel": r1.channel, "location": r1.location,
         "start_time": r1.start_time, "sample_rate": r1.sample_rate,
         "samples": r1.samples},
        {"station": r2.station, "channel": r2.channel, "location": r2.location,
         "start_time": r2.start_time, "sample_rate": r2.sample_rate,
         "samples": r2.samples},
    ]


@pytest.fixture
def raw_data_with_gap():
    """Due record ETNA01 con gap di 3 secondi (100 + 200 campioni)."""
    r1 = make_record(start_time=BASE_TIME, sample_count=100)
    r2 = make_record(start_time=BASE_TIME + 1.0 + 3.0, sample_count=200)
    return [
        {"station": r1.station, "channel": r1.channel, "location": r1.location,
         "start_time": r1.start_time, "sample_rate": r1.sample_rate,
         "samples": r1.samples},
        {"station": r2.station, "channel": r2.channel, "location": r2.location,
         "start_time": r2.start_time, "sample_rate": r2.sample_rate,
         "samples": r2.samples},
    ]


@pytest.fixture
def raw_data_multi_station():
    """Record da tre stazioni: ETNA01 (2 record), STRO01 (1 record), ETNA02 (1 record)."""
    records = []
    for station, count, t_start in [
        ("ETNA01", 100, BASE_TIME),
        ("ETNA01", 200, BASE_TIME + 1.0),
        ("STRO01", 150, BASE_TIME),
        ("ETNA02", 100, BASE_TIME),
    ]:
        r = make_record(station=station, start_time=t_start, sample_count=count)
        records.append({
            "station": r.station, "channel": r.channel, "location": r.location,
            "start_time": r.start_time, "sample_rate": r.sample_rate,
            "samples": r.samples,
        })
    return records


# ── Volcanic alert fixtures ────────────────────────────────────────

@pytest.fixture
def reading_green():
    return TremorReading(
        station="ETNA01", timestamp=BASE_TIME,
        amplitude_low=0.1, amplitude_mid=0.1, amplitude_high=0.05,
        displacement=0.5,
    )


@pytest.fixture
def reading_yellow_low():
    return TremorReading(
        station="ETNA01", timestamp=BASE_TIME,
        amplitude_low=0.35, amplitude_mid=0.1, amplitude_high=0.05,
        displacement=0.5,
    )


@pytest.fixture
def reading_orange():
    return TremorReading(
        station="ETNA01", timestamp=BASE_TIME,
        amplitude_low=0.65, amplitude_mid=0.2, amplitude_high=0.1,
        displacement=3.0,
    )


@pytest.fixture
def reading_red():
    return TremorReading(
        station="ETNA01", timestamp=BASE_TIME,
        amplitude_low=1.0, amplitude_mid=1.2, amplitude_high=0.9,
        displacement=12.0,
    )


@pytest.fixture
def reading_stro_yellow():
    """Lettura STRO01: con soglie default sarebbe ORANGE, con override è YELLOW."""
    return TremorReading(
        station="STRO01", timestamp=BASE_TIME,
        amplitude_low=0.65, amplitude_mid=0.2, amplitude_high=0.1,
        displacement=2.5,
    )


# ── GPS fixtures ───────────────────────────────────────────────────

@pytest.fixture
def gps_measurement_etna():
    return GpsMeasurement(
        station="ETNA01",
        recorded_at=datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc),
        latitude=37.748,
        longitude=14.994,
        elevation=1500.0,
        delta_n=1.2,
        delta_e=0.8,
        delta_u=-0.3,
        quality=2,
    )


@pytest.fixture
def mock_cursor_factory():
    """Factory per creare mock psycopg2 cursor con dati configurabili."""
    from unittest.mock import MagicMock

    def _make(rows: list[tuple]) -> MagicMock:
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        return cursor

    return _make


@pytest.fixture
def mock_conn_factory(mock_cursor_factory):
    """Factory per creare mock psycopg2 connection con cursor configurabile."""
    from unittest.mock import MagicMock

    def _make(rows: list[tuple]) -> MagicMock:
        conn = MagicMock()
        cursor = mock_cursor_factory(rows)
        conn.cursor.return_value = cursor
        return conn, cursor

    return _make
