"""
Report giornaliero delle allerte vulcanologiche.

Raggruppa le allerte della giornata per provenienza delle soglie usate, così
chi legge il report sa quali stazioni sono state valutate con le soglie
standard e quali con soglie ricalibrate.

Il campo Alert.threshold_source è la sola fonte di questa informazione.

Uso:
    python scripts/daily_report.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seismolab.alerts.volcanic import (
    TremorReading, evaluate_alert, AlertLevel,
)

BASE_TIME = 1700000000.0

LETTURE = [
    TremorReading(station="ETNA01", timestamp=BASE_TIME,
                  amplitude_low=0.10, amplitude_mid=0.05,
                  amplitude_high=0.02, displacement=0.3),
    TremorReading(station="ETNA01", timestamp=BASE_TIME + 3600,
                  amplitude_low=0.65, amplitude_mid=0.20,
                  amplitude_high=0.10, displacement=2.5),
    TremorReading(station="ETNA02", timestamp=BASE_TIME + 3600,
                  amplitude_low=0.20, amplitude_mid=0.15,
                  amplitude_high=0.18, displacement=1.0),
    TremorReading(station="STRO01", timestamp=BASE_TIME + 7200,
                  amplitude_low=0.65, amplitude_mid=0.20,
                  amplitude_high=0.10, displacement=2.5),
    TremorReading(station="STRO02", timestamp=BASE_TIME + 7200,
                  amplitude_low=0.70, amplitude_mid=0.30,
                  amplitude_high=0.15, displacement=3.0),
]


def main():
    # Chiamata con un solo argomento: questo script non conosce le soglie,
    # si affida a quelle configurate nel modulo.
    allerte = [evaluate_alert(lettura) for lettura in LETTURE]

    print("=" * 62)
    print("REPORT GIORNALIERO — ALLERTE VULCANOLOGICHE")
    print("=" * 62)

    per_provenienza: dict[str, list] = {}
    for a in allerte:
        per_provenienza.setdefault(a.threshold_source, []).append(a)

    for provenienza in sorted(per_provenienza):
        gruppo = per_provenienza[provenienza]
        print(f"\nSoglie: {provenienza}  ({len(gruppo)} letture)")
        print("-" * 62)
        for a in gruppo:
            print(f"  {a.station:8} t+{int(a.timestamp - BASE_TIME):5d}s  "
                  f"{a.level.value.upper():<7}")

    non_verdi = [a for a in allerte if a.level != AlertLevel.GREEN]
    print()
    print("=" * 62)
    print(f"Letture totali: {len(allerte)}   non-GREEN: {len(non_verdi)}")
    print(f"Provenienze distinte nel report: {sorted(per_provenienza)}")
    print()
    print("Se tutte le letture risultano sotto la stessa provenienza, il report")
    print("perde l'informazione su quali stazioni usano soglie ricalibrate.")


if __name__ == "__main__":
    main()
