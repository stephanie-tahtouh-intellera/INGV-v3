"""
Parser per tracce sismiche in formato MiniSEED (semplificato).

Formato MiniSEED: sequenza di record a lunghezza fissa.
Ogni record contiene header + dati campionati. Un file reale può contenere
record di stazioni multiple, canali multipli (Z/N/E), e gap temporali
dovuti a interruzioni della trasmissione o riavvii dello strumento.

Nota: questo modulo usa una rappresentazione semplificata del formato
MiniSEED per scopi didattici. Non dipende da ObsPy o librerie esterne.

Issue #12 — BUG: i record con gap temporale vengono silenziosamente scartati.
La funzione parse_mseed usa il confronto esatto tra start_time del record
successivo e end_time del record precedente. In presenza di qualsiasi jitter
nei timestamp (inevitabile su hardware reale), tutti i record dopo il primo
gap vengono persi — senza errore, senza avviso.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SeismicRecord:
    """Singolo record di una traccia sismica."""
    station: str
    channel: str               # es. 'HHZ', 'HHN', 'HHE'
    location: str              # es. '00', '10', ''
    start_time: float          # timestamp UNIX
    sample_rate: float         # campioni/secondo
    samples: list[float]       # valori di ampiezza

    @property
    def end_time(self) -> float:
        if not self.samples:
            return self.start_time
        return self.start_time + len(self.samples) / self.sample_rate

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def network_station_channel(self) -> str:
        return f"{self.station}.{self.location}.{self.channel}"


@dataclass
class GapInfo:
    """Informazioni su un gap temporale tra due record contigui."""
    station: str
    channel: str
    gap_start: float     # end_time del record precedente
    gap_end: float       # start_time del record successivo
    gap_seconds: float   # durata del gap in secondi
    samples_lost: int    # campioni stimati persi

    @property
    def is_overlap(self) -> bool:
        """True se il gap è negativo (sovrapposizione temporale)."""
        return self.gap_seconds < 0


@dataclass
class SeismicTrace:
    """Traccia sismica completa, composta da uno o più record contigui."""
    station: str
    channel: str
    location: str
    records: list[SeismicRecord] = field(default_factory=list)
    gaps: list[GapInfo] = field(default_factory=list)

    def add_record(self, record: SeismicRecord) -> None:
        self.records.append(record)

    def add_gap(self, gap: GapInfo) -> None:
        self.gaps.append(gap)

    @property
    def total_samples(self) -> int:
        return sum(len(r.samples) for r in self.records)

    @property
    def has_gaps(self) -> bool:
        return len(self.gaps) > 0

    @property
    def coverage_percent(self) -> float:
        """Percentuale di copertura temporale rispetto alla durata totale."""
        if not self.records:
            return 0.0
        total_duration = self.records[-1].end_time - self.records[0].start_time
        if total_duration <= 0:
            return 100.0
        data_duration = sum(r.duration for r in self.records)
        return min(100.0, data_duration / total_duration * 100)

    def all_samples(self) -> list[float]:
        """Restituisce tutti i campioni della traccia come lista unica."""
        result = []
        for record in self.records:
            result.extend(record.samples)
        return result


@dataclass
class ParseResult:
    """Risultato completo del parsing di un file MiniSEED."""
    traces: list[SeismicTrace]
    total_records_parsed: int
    total_records_skipped: int
    warnings: list[str] = field(default_factory=list)

    @property
    def stations(self) -> set[str]:
        return {t.station for t in self.traces}

    def get_trace(self, station: str, channel: str,
                  location: str = "") -> Optional["SeismicTrace"]:
        """Recupera una traccia specifica per stazione/canale."""
        for t in self.traces:
            if t.station == station and t.channel == channel and t.location == location:
                return t
        return None


def parse_mseed(raw_data: list[dict]) -> ParseResult:
    """
    Analizza una sequenza di record MiniSEED e restituisce le tracce.

    Args:
        raw_data: lista di dizionari con chiavi:
                  'station', 'channel', 'location' (opt.), 'start_time',
                  'sample_rate', 'samples'

    Returns:
        ParseResult con traces, statistiche di parsing, e gap per traccia.

    BUG (#12): il controllo di continuità usa il confronto esatto
        record.start_time == last.end_time
    I timestamp MiniSEED reali hanno jitter nell'ordine di
    microsecondi dovuto all'hardware degli acquisitori. Qualsiasi
    gap minimo (inclusi gap di 0.001s a 100 Hz) causa lo scarto
    silenzioso di tutti i record successivi per quella traccia.

    FIX: sostituire il confronto esatto con una tolleranza:
        abs(record.start_time - last.end_time) <= 0.5 / record.sample_rate
    """
    traces: dict[str, SeismicTrace] = {}
    skipped = 0
    warnings = []

    for entry in raw_data:
        location = entry.get("location", "")
        key = f"{entry['station']}.{location}.{entry['channel']}"

        record = SeismicRecord(
            station=entry["station"],
            channel=entry["channel"],
            location=location,
            start_time=entry["start_time"],
            sample_rate=entry["sample_rate"],
            samples=entry["samples"],
        )

        if key not in traces:
            traces[key] = SeismicTrace(
                station=entry["station"],
                channel=entry["channel"],
                location=location,
            )
            traces[key].add_record(record)
        else:
            last = traces[key].records[-1]

            # BUG (#12): confronto esatto invece di confronto con tolleranza.
            # Con jitter realistico (±5ms a 100 Hz), questa condizione
            # è quasi sempre False per record successivi al primo.
            if record.start_time == last.end_time:
                traces[key].add_record(record)
            else:
                # I record con gap vengono silenziosamente scartati.
                # Con il fix, andrebbero aggiunti registrando il gap.
                skipped += 1
                warnings.append(
                    f"{key}: record skipped at t={record.start_time:.3f} "
                    f"(expected {last.end_time:.3f}, "
                    f"gap={record.start_time - last.end_time:.4f}s)"
                )

    return ParseResult(
        traces=list(traces.values()),
        total_records_parsed=len(raw_data) - skipped,
        total_records_skipped=skipped,
        warnings=warnings,
    )


def validate_trace(trace: SeismicTrace) -> dict:
    """
    Valida una traccia sismica e restituisce un report di qualità.

    Controlla ampiezza anomala, segmentazione, copertura temporale,
    e consistenza del sample rate tra record consecutivi.
    """
    warnings = []
    samples = trace.all_samples()

    if not samples:
        return {"valid": False, "warnings": ["Traccia vuota"], "stats": {}}

    max_amp = max(abs(s) for s in samples)
    mean_amp = sum(samples) / len(samples)

    if max_amp > 1e6:
        warnings.append(f"Ampiezza massima anomala: {max_amp:.2e}")

    if len(trace.records) > 1:
        # Verifica consistenza del sample rate
        rates = {r.sample_rate for r in trace.records}
        if len(rates) > 1:
            warnings.append(f"Sample rate non uniforme: {rates}")

    if trace.has_gaps:
        total_gap = sum(g.gap_seconds for g in trace.gaps if not g.is_overlap)
        warnings.append(
            f"{len(trace.gaps)} gap rilevati, totale {total_gap:.2f}s persi"
        )

    if trace.coverage_percent < 90:
        warnings.append(
            f"Copertura temporale bassa: {trace.coverage_percent:.1f}%"
        )

    return {
        "valid": True,
        "warnings": warnings,
        "stats": {
            "total_samples": len(samples),
            "max_amplitude": max_amp,
            "mean_amplitude": mean_amp,
            "record_count": len(trace.records),
            "gap_count": len(trace.gaps),
            "coverage_percent": trace.coverage_percent,
        }
    }
