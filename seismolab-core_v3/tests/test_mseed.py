"""
Test per seismolab/parsers/mseed.py

Copertura richiesta dall'issue #12:
- parse_mseed: caso principale, gap, jitter, multi-stazione, canali multipli
- validate_trace: trace valide, trace con gap, trace vuote
- GapInfo: calcolo corretto durata e campioni persi
- ParseResult: aggregazioni e accesso per stazione/canale
"""

import pytest
from seismolab.parsers.mseed import (
    parse_mseed, validate_trace,
    SeismicRecord, SeismicTrace, GapInfo, ParseResult,
)
from tests.conftest import make_record, BASE_TIME, SAMPLE_RATE


# ══════════════════════════════════════════════════════════════════
# parse_mseed — casi principali
# ══════════════════════════════════════════════════════════════════

class TestParseMseedMainCases:

    def test_single_record_returns_one_trace(self, raw_data_no_gap):
        result = parse_mseed(raw_data_no_gap[:1])
        assert len(result.traces) == 1

    def test_two_contiguous_records_merged(self, raw_data_no_gap):
        result = parse_mseed(raw_data_no_gap)
        assert result.traces[0].total_samples == 300   # 100 + 200
        assert result.total_records_skipped == 0

    def test_empty_input_returns_empty_result(self):
        result = parse_mseed([])
        assert result.traces == []
        assert result.total_records_parsed == 0


# ══════════════════════════════════════════════════════════════════
# parse_mseed — gestione gap (il cuore dell'issue #12)
# ══════════════════════════════════════════════════════════════════

class TestParseMseedGapHandling:

    def test_gap_record_not_silently_dropped(self, raw_data_with_gap):
        """Dopo il fix: entrambi i record devono essere nella traccia."""
        result = parse_mseed(raw_data_with_gap)
        trace = result.traces[0]
        # Con il fix: total_samples = 100 + 200 = 300
        # Con il bug: total_samples = 100 (il secondo record è scartato)
        assert trace.total_samples == 300, (
            f"Atteso 300 campioni, trovato {trace.total_samples}. "
            "Il bug #12 scarta i record con gap."
        )

    def test_gap_is_recorded_in_trace(self, raw_data_with_gap):
        """Dopo il fix: il gap deve essere registrato in trace.gaps."""
        result = parse_mseed(raw_data_with_gap)
        trace = result.traces[0]
        assert len(trace.gaps) == 1

    def test_gap_duration_correct(self, raw_data_with_gap):
        """Il gap è di 3 secondi tra i due record."""
        result = parse_mseed(raw_data_with_gap)
        gap = result.traces[0].gaps[0]
        assert pytest.approx(gap.gap_seconds, abs=0.01) == 3.0

    def test_gap_samples_lost_estimated(self, raw_data_with_gap):
        """I campioni persi devono essere stimati (3s × 100Hz = 300)."""
        result = parse_mseed(raw_data_with_gap)
        gap = result.traces[0].gaps[0]
        assert gap.samples_lost == pytest.approx(300, abs=5)

    def test_jitter_within_tolerance_not_counted_as_gap(self):
        """Un jitter di 4ms a 100Hz è entro tolleranza: non deve creare gap."""
        r1 = make_record(start_time=BASE_TIME, sample_count=100)
        r2_jitter = make_record(
            start_time=BASE_TIME + 1.0 + 0.004,  # 4ms di jitter
            sample_count=100
        )
        raw = [
            {"station": r1.station, "channel": r1.channel, "location": r1.location,
             "start_time": r1.start_time, "sample_rate": r1.sample_rate, "samples": r1.samples},
            {"station": r2_jitter.station, "channel": r2_jitter.channel,
             "location": r2_jitter.location,
             "start_time": r2_jitter.start_time, "sample_rate": r2_jitter.sample_rate,
             "samples": r2_jitter.samples},
        ]
        result = parse_mseed(raw)
        assert result.traces[0].total_samples == 200
        assert len(result.traces[0].gaps) == 0

    def test_gap_above_tolerance_creates_gap_entry(self):
        """Un gap di 100ms a 100Hz supera la tolleranza (5ms): deve creare gap."""
        r1 = make_record(start_time=BASE_TIME, sample_count=100)
        r2 = make_record(start_time=BASE_TIME + 1.1, sample_count=100)
        raw = [
            {"station": r1.station, "channel": r1.channel, "location": r1.location,
             "start_time": r1.start_time, "sample_rate": r1.sample_rate, "samples": r1.samples},
            {"station": r2.station, "channel": r2.channel, "location": r2.location,
             "start_time": r2.start_time, "sample_rate": r2.sample_rate, "samples": r2.samples},
        ]
        result = parse_mseed(raw)
        assert len(result.traces[0].gaps) == 1


# ══════════════════════════════════════════════════════════════════
# parse_mseed — multi-stazione
# ══════════════════════════════════════════════════════════════════

class TestParseMseedMultiStation:

    def test_multi_station_creates_separate_traces(self, raw_data_multi_station):
        result = parse_mseed(raw_data_multi_station)
        stations = {t.station for t in result.traces}
        assert "ETNA01" in stations
        assert "STRO01" in stations
        assert "ETNA02" in stations

    def test_etna01_trace_has_correct_samples(self, raw_data_multi_station):
        result = parse_mseed(raw_data_multi_station)
        etna = result.get_trace("ETNA01", "HHZ", "00")
        assert etna is not None
        assert etna.total_samples == 300  # 100 + 200

    def test_stro01_trace_independent(self, raw_data_multi_station):
        result = parse_mseed(raw_data_multi_station)
        stro = result.get_trace("STRO01", "HHZ", "00")
        assert stro is not None
        assert stro.total_samples == 150

    def test_stations_property_returns_all(self, raw_data_multi_station):
        result = parse_mseed(raw_data_multi_station)
        assert result.stations == {"ETNA01", "STRO01", "ETNA02"}


# ══════════════════════════════════════════════════════════════════
# validate_trace
# ══════════════════════════════════════════════════════════════════

class TestValidateTrace:

    def test_valid_trace_no_warnings(self, raw_data_no_gap):
        result = parse_mseed(raw_data_no_gap)
        report = validate_trace(result.traces[0])
        assert report["valid"] is True
        assert report["stats"]["total_samples"] == 300

    def test_empty_trace_invalid(self):
        trace = SeismicTrace(station="TEST", channel="HHZ", location="")
        report = validate_trace(trace)
        assert report["valid"] is False

    def test_trace_with_gap_warns(self, raw_data_with_gap):
        """Dopo il fix: la traccia ha un gap e validate_trace deve segnalarlo."""
        result = parse_mseed(raw_data_with_gap)
        report = validate_trace(result.traces[0])
        assert any("gap" in w.lower() for w in report["warnings"])

    def test_anomalous_amplitude_warns(self):
        r = make_record(amplitude=2e6)
        trace = SeismicTrace(station="TEST", channel="HHZ", location="")
        trace.add_record(r)
        report = validate_trace(trace)
        assert any("ampiezza" in w.lower() for w in report["warnings"])

    def test_coverage_percent_no_gap(self, raw_data_no_gap):
        result = parse_mseed(raw_data_no_gap)
        assert result.traces[0].coverage_percent == pytest.approx(100.0, abs=0.1)
