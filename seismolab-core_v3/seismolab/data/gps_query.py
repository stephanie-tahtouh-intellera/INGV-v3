"""
Query su dati GPS da database PostGIS.

Il database registra misurazioni GPS di stazioni della rete geodetica INGV.
Le stazioni monitorano la deformazione del suolo su Etna, Stromboli, Campi Flegrei
e altre aree vulcaniche attive.

Issue #23 — FEATURE: implementare le quattro funzioni di query.
Il modulo definisce l'interfaccia e i tipi di ritorno; il corpo delle funzioni
va implementato usando psycopg2 con query parametrizzate.

Schema del database (tabelle rilevanti):

    CREATE TABLE stations (
        code        VARCHAR(10) PRIMARY KEY,
        name        TEXT NOT NULL,
        volcano     VARCHAR(50),
        latitude    DOUBLE PRECISION NOT NULL,
        longitude   DOUBLE PRECISION NOT NULL,
        elevation   DOUBLE PRECISION NOT NULL,
        active      BOOLEAN DEFAULT TRUE
    );

    CREATE TABLE gps_measurements (
        id          BIGSERIAL PRIMARY KEY,
        station     VARCHAR(10) NOT NULL REFERENCES stations(code),
        recorded_at TIMESTAMPTZ NOT NULL,
        latitude    DOUBLE PRECISION NOT NULL,
        longitude   DOUBLE PRECISION NOT NULL,
        elevation   DOUBLE PRECISION NOT NULL,
        delta_n     DOUBLE PRECISION,   -- spostamento Nord (mm)
        delta_e     DOUBLE PRECISION,   -- spostamento Est (mm)
        delta_u     DOUBLE PRECISION,   -- spostamento verticale (mm)
        quality     SMALLINT DEFAULT 1  -- 0=scadente 1=accettabile 2=ottimo
    );

    CREATE INDEX gps_station_time ON gps_measurements(station, recorded_at DESC);

Configurazione connessione via variabili d'ambiente:
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
"""

import os
from dataclasses import dataclass
from typing import Optional, Callable
from datetime import datetime, timedelta, timezone


@dataclass
class GpsMeasurement:
    """Singola misurazione GPS."""
    station: str
    recorded_at: datetime
    latitude: float
    longitude: float
    elevation: float
    delta_n: Optional[float] = None   # spostamento Nord (mm)
    delta_e: Optional[float] = None   # spostamento Est (mm)
    delta_u: Optional[float] = None   # spostamento verticale (mm)
    quality: int = 1

    @property
    def displacement_magnitude(self) -> Optional[float]:
        """Magnitudo del vettore di spostamento orizzontale in mm."""
        if self.delta_n is None or self.delta_e is None:
            return None
        return (self.delta_n ** 2 + self.delta_e ** 2) ** 0.5

    @property
    def is_high_quality(self) -> bool:
        return self.quality >= 2


@dataclass
class DisplacementSummary:
    """Riepilogo degli spostamenti per una stazione in un periodo."""
    station: str
    period_days: int
    measurement_count: int
    max_horizontal_mm: Optional[float]
    max_vertical_mm: Optional[float]
    mean_horizontal_mm: Optional[float]
    trend_n: str     # 'stable' | 'increasing' | 'decreasing'
    trend_e: str
    trend_u: str
    first_measurement: Optional[datetime]
    last_measurement: Optional[datetime]

    @property
    def overall_trend(self) -> str:
        """Trend dominante basato sul componente con variazione maggiore."""
        trends = [self.trend_n, self.trend_e, self.trend_u]
        if "increasing" in trends:
            return "increasing"
        if "decreasing" in trends:
            return "decreasing"
        return "stable"


def get_connection(dsn: Optional[str] = None):
    """
    Restituisce una connessione psycopg2 al database PostGIS.

    Legge le credenziali dalle variabili d'ambiente se dsn è None.
    Solleva EnvironmentError se mancano variabili obbligatorie.
    Solleva psycopg2.OperationalError se la connessione fallisce.

    Args:
        dsn: stringa di connessione opzionale (sovrascrive env vars)
             es. "host=localhost dbname=seismodb user=ingv password=..."

    TODO (Issue #23): implementare questa funzione.
    Requisiti:
    - Usa psycopg2.connect()
    - Se dsn è None, costruisci il dsn da variabili d'ambiente:
      DB_HOST (default: localhost), DB_PORT (default: 5432),
      DB_NAME, DB_USER, DB_PASSWORD (queste ultime tre obbligatorie)
    - Imposta autocommit=False
    - Non aprire connessioni nei test: usa il parametro conn nelle altre funzioni
    """
    raise NotImplementedError("Issue #23 — da implementare")


def fetch_recent_measurements(
    station: str,
    hours: int = 24,
    conn=None,
    min_quality: int = 0,
) -> list[GpsMeasurement]:
    """
    Recupera le misurazioni GPS delle ultime N ore per una stazione.

    Args:
        station:     codice stazione (es. 'ETNA01', 'STRO02')
        hours:       finestra temporale in ore (default: 24)
        conn:        connessione psycopg2 (se None, ne crea una con get_connection)
        min_quality: qualità minima dei record da includere [0, 1, 2]

    Returns:
        Lista di GpsMeasurement ordinata per recorded_at crescente.
        Lista vuota se non ci sono misurazioni nel periodo.

    Raises:
        psycopg2.OperationalError: se la connessione fallisce
        ValueError: se hours <= 0

    TODO (Issue #23): implementare questa funzione.
    Requisiti:
    - Query parametrizzata con %s (mai f-string, mai format())
    - Filtro temporale: recorded_at >= NOW() - (%s * INTERVAL '1 hour')
      (un segnaposto dentro una stringa quotata non viene sostituito)
    - Filtro qualità: quality >= %s
    - Ordina per recorded_at ASC
    - Usa context manager per il cursore
    - Se conn è None, apri e chiudi la connessione internamente
    """
    raise NotImplementedError("Issue #23 — da implementare")


def fetch_displacement_summary(
    station: str,
    days: int = 7,
    conn=None,
) -> DisplacementSummary:
    """
    Calcola un riepilogo degli spostamenti degli ultimi N giorni.

    Il trend è calcolato confrontando la media della prima e seconda metà
    del periodo: se la seconda metà supera la prima di più del 20%,
    il trend è 'increasing'; se è inferiore del 20%, 'decreasing';
    altrimenti 'stable'.

    Args:
        station: codice stazione
        days:    finestra temporale in giorni (default: 7)
        conn:    connessione psycopg2 opzionale

    Returns:
        DisplacementSummary con statistiche e trend per componente.
        Se non ci sono misurazioni, restituisce un summary con
        measurement_count=0 e tutti i valori None.

    Raises:
        psycopg2.OperationalError: se la connessione fallisce
        ValueError: se days <= 0

    TODO (Issue #23): implementare questa funzione.
    Requisiti:
    - Una singola query SQL che recupera le misurazioni del periodo
    - Calcola max/mean di displacement_magnitude in Python (non in SQL)
    - Calcola trend confrontando prima e seconda metà del periodo
    - Usa query parametrizzata con %s
    """
    raise NotImplementedError("Issue #23 — da implementare")


def watch_anomalies(
    stations: list[str],
    threshold_mm: float,
    callback: Callable[[str, GpsMeasurement], None],
    hours: int = 1,
    conn=None,
) -> int:
    """
    Controlla le misurazioni recenti e chiama callback per ogni anomalia.

    Una misurazione è anomala se displacement_magnitude > threshold_mm.

    Args:
        stations:      lista di codici stazione da monitorare
        threshold_mm:  soglia di spostamento orizzontale in mm
        callback:      funzione chiamata con (station, measurement) per ogni anomalia
        hours:         finestra temporale in ore (default: 1)
        conn:          connessione psycopg2 opzionale

    Returns:
        Numero di anomalie rilevate (quante volte callback è stato chiamato).

    Raises:
        psycopg2.OperationalError: se la connessione fallisce
        ValueError: se threshold_mm <= 0

    TODO (Issue #23): implementare questa funzione.
    Requisiti:
    - Chiama fetch_recent_measurements per ogni stazione
    - Filtra le misurazioni dove displacement_magnitude > threshold_mm
    - Chiama callback per ogni misurazione anomala
    - Gestisce le eccezioni per singola stazione senza interrompere il loop
    - Non eseguire N query separate: considera un'unica query con IN (%s, %s, ...)
    """
    raise NotImplementedError("Issue #23 — da implementare")
