"""
SUITE DI VERIFICA — Issue #23 (query GPS su PostGIS)

Non modificate questo file. Eseguitelo così:

    pytest tests/hidden/test_hidden_23.py -v

Questa suite non apre nessuna connessione: usa un doppio di test che registra
le query eseguite, i parametri passati e le chiusure. Verifica il requisito
scritto nelle docstring del modulo, compresi i due punti che un test scritto
in fretta non copre: la parametrizzazione dei valori che arrivano dall'esterno
e la chiusura delle risorse.

Testa solo comportamento osservabile al confine con il database: qualsiasi
implementazione corretta la supera.
"""

import pytest
from datetime import datetime, timedelta, timezone

from seismolab.data.gps_query import (
    fetch_recent_measurements, fetch_displacement_summary, DisplacementSummary,
)

T0 = datetime(2023, 11, 14, 22, 0, 0, tzinfo=timezone.utc)

# Stringa ostile: se compare dentro il testo della query, la query è costruita
# per concatenazione e il database la eseguirebbe.
INIEZIONE = "ETNA01'; DROP TABLE gps_measurements; --"


def riga(station="ETNA01", dt=T0, lat=37.748, lon=14.994, elev=1500.0,
         dn=1.2, de=0.8, du=-0.3, quality=2):
    """Riga raw come la restituirebbe psycopg2."""
    return (station, dt, lat, lon, elev, dn, de, du, quality)


class FakeCursor:
    """Cursore di test: registra le execute, i parametri e le chiusure."""

    def __init__(self, rows, solleva=None):
        self._rows = rows
        self._solleva = solleva
        self.chiamate = []          # lista di (sql, params)
        self.chiuso = False

    def execute(self, sql, params=None):
        self.chiamate.append((sql, params))
        if self._solleva is not None:
            raise self._solleva

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def close(self):
        self.chiuso = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.chiuso = True
        return False


class FakeConn:
    """Connessione di test: registra se viene chiusa dal chiamato."""

    def __init__(self, rows=(), solleva=None):
        self.cur = FakeCursor(rows, solleva)
        self.chiusa = False
        self.commit_chiamato = False
        self.rollback_chiamato = False

    def cursor(self):
        return self.cur

    def close(self):
        self.chiusa = True

    def commit(self):
        self.commit_chiamato = True

    def rollback(self):
        self.rollback_chiamato = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def sql_di(conn):
    """Testo della prima query eseguita."""
    assert conn.cur.chiamate, (
        "Nessuna query è stata eseguita sul cursore. La funzione deve "
        "interrogare il database attraverso la connessione ricevuta."
    )
    return conn.cur.chiamate[0][0]


def params_di(conn):
    """Parametri della prima query, normalizzati a lista di valori."""
    assert conn.cur.chiamate, "Nessuna query eseguita."
    p = conn.cur.chiamate[0][1]
    if p is None:
        return None
    if isinstance(p, dict):
        return list(p.values())
    return list(p)


# ══════════════════════════════════════════════════════════════════
# 1. Parametrizzazione: il punto di sicurezza dell'issue
# ══════════════════════════════════════════════════════════════════

class TestQueryParametrizzata:

    def test_i_valori_esterni_passano_come_parametri(self):
        """
        execute deve ricevere due argomenti: il testo della query con i
        segnaposto e i valori separati. Una query costruita con f-string
        chiama execute con un argomento solo.
        """
        conn = FakeConn([riga()])
        fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        p = params_di(conn)
        assert p is not None, (
            "execute è stata chiamata con il solo testo della query. I valori "
            "vanno passati come secondo argomento: cur.execute(sql, (valori,)). "
            "Vedete il requisito nella docstring: query parametrizzata con %s."
        )
        assert "ETNA01" in [str(v) for v in p], (
            f"Il codice stazione non è tra i parametri passati: {p}. "
            "Se è finito dentro il testo della query, la query è costruita "
            "per concatenazione."
        )

    def test_stringa_ostile_non_finisce_nel_testo_della_query(self):
        """
        Il test che distingue una query parametrizzata da una concatenata.
        Con i segnaposto la stringa ostile resta un valore e non viene mai
        interpretata come SQL.
        """
        conn = FakeConn([])
        fetch_recent_measurements(INIEZIONE, hours=24, conn=conn)
        sql = sql_di(conn)
        assert "DROP TABLE" not in sql.upper(), (
            "La stringa ostile è finita dentro il testo della query:\n\n"
            f"    {sql.strip()[:200]}\n\n"
            "Su un database reale questo cancellerebbe la tabella. Il valore "
            "deve essere passato come parametro, non interpolato nella stringa."
        )
        p = params_di(conn)
        assert p is not None and INIEZIONE in [str(v) for v in p], (
            "La stringa ostile non compare tra i parametri: dove è finita?"
        )

    def test_qualita_minima_e_un_parametro(self):
        """
        La docstring richiede il filtro `quality >= %s`: anche min_quality
        va passato come parametro, non scritto nella query.
        """
        conn = FakeConn([riga()])
        fetch_recent_measurements("ETNA01", hours=24, conn=conn, min_quality=2)
        p = params_di(conn)
        assert p is not None and 2 in [
            int(v) for v in p if isinstance(v, (int, float))
        ], (
            f"min_quality non è tra i parametri: {p}. La docstring richiede "
            "il filtro quality >= %s."
        )


# ══════════════════════════════════════════════════════════════════
# 2. Gestione delle risorse
# ══════════════════════════════════════════════════════════════════

class TestGestioneRisorse:

    def test_il_cursore_viene_chiuso(self):
        """La docstring richiede il context manager per il cursore."""
        conn = FakeConn([riga()])
        fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        assert conn.cur.chiuso, (
            "Il cursore non è stato chiuso. Usate `with conn.cursor() as cur:` "
            "oppure un try/finally: un cursore lasciato aperto trattiene "
            "risorse sul server."
        )

    def test_il_cursore_viene_chiuso_anche_se_la_query_falla(self):
        """
        Il caso che un test scritto in fretta non copre: se execute solleva,
        il cursore va chiuso comunque. Senza context manager o finally,
        l'eccezione salta la chiusura.
        """
        import psycopg2
        conn = FakeConn([], solleva=psycopg2.OperationalError("connessione persa"))
        with pytest.raises(Exception):
            fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        assert conn.cur.chiuso, (
            "La query ha sollevato un'eccezione e il cursore è rimasto aperto. "
            "La chiusura deve avvenire anche sul percorso di errore: "
            "context manager o try/finally."
        )

    def test_la_connessione_del_chiamante_non_viene_chiusa(self):
        """
        Chi apre la connessione la chiude. La docstring dice: se conn è None
        la funzione la apre e la chiude; se conn arriva dall'esterno, no.
        Chiuderla romperebbe il chiamante alla query successiva.
        """
        conn = FakeConn([riga()])
        fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        assert not conn.chiusa, (
            "La funzione ha chiuso una connessione che non ha aperto. "
            "Il chiamante la riusa: chiudetela solo se l'avete creata voi."
        )


# ══════════════════════════════════════════════════════════════════
# 3. Contratto di ritorno
# ══════════════════════════════════════════════════════════════════

class TestContrattoRitorno:

    def test_nessun_risultato_da_lista_vuota(self):
        conn = FakeConn([])
        res = fetch_recent_measurements("ETNA01", hours=24, conn=conn)
        assert res == [], (
            f"Senza misurazioni la funzione deve restituire una lista vuota, "
            f"ottenuto {res!r}. Non None, non un'eccezione."
        )

    def test_hours_non_positivo_solleva_value_error(self):
        conn = FakeConn([riga()])
        with pytest.raises(ValueError):
            fetch_recent_measurements("ETNA01", hours=0, conn=conn)

    def test_riepilogo_senza_misurazioni(self):
        """Contratto dichiarato: count a zero e valori a None, non eccezione."""
        conn = FakeConn([])
        s = fetch_displacement_summary("ETNA01", days=7, conn=conn)
        assert isinstance(s, DisplacementSummary), (
            f"Atteso un DisplacementSummary, ottenuto {type(s).__name__}."
        )
        assert s.measurement_count == 0, (
            f"measurement_count atteso 0, ottenuto {s.measurement_count}."
        )
        assert s.max_horizontal_mm is None, (
            "Senza misurazioni le statistiche devono essere None, come dice "
            "la docstring."
        )

    def test_riepilogo_con_misurazioni(self):
        righe = [
            riga(dt=T0 + timedelta(days=0), dn=1.0, de=0.0, du=0.1),
            riga(dt=T0 + timedelta(days=1), dn=1.1, de=0.0, du=0.1),
            riga(dt=T0 + timedelta(days=4), dn=3.0, de=0.0, du=0.5),
            riga(dt=T0 + timedelta(days=5), dn=3.4, de=0.0, du=0.6),
        ]
        conn = FakeConn(righe)
        s = fetch_displacement_summary("ETNA01", days=7, conn=conn)
        assert s.measurement_count == 4, (
            f"Quattro misurazioni in ingresso, measurement_count è "
            f"{s.measurement_count}."
        )
        assert s.max_horizontal_mm is not None and s.max_horizontal_mm > 0, (
            "max_horizontal_mm deve essere calcolato dalle misurazioni."
        )
        assert s.trend_n in ("stable", "increasing", "decreasing"), (
            f"trend_n deve essere uno dei tre valori documentati, "
            f"ottenuto {s.trend_n!r}."
        )
