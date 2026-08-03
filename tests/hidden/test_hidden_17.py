"""
SUITE DI VERIFICA — Issue #17 (soglie di allerta configurabili)

Non modificate questo file. Eseguitelo così:

    pytest tests/hidden/test_hidden_17.py -v

Questa suite codifica il requisito completo dell'issue, compresi i casi che
l'implementazione più ovvia non copre. Testa solo il comportamento pubblico:
qualsiasi implementazione corretta la supera, indipendentemente da come è
strutturata internamente.

Se un test falla, il messaggio dice cosa manca. Leggetelo prima di toccare
il codice.
"""

import copy
import pytest

from seismolab.alerts.volcanic import (
    evaluate_alert, batch_evaluate, summarize_alerts,
    AlertLevel, TremorReading,
)

T = 1700000000.0

# Le dodici soglie di default documentate nell'issue.
DEFAULTS = {
    "LOW_YELLOW": 0.3, "LOW_ORANGE": 0.6, "LOW_RED": 0.9,
    "MID_YELLOW": 0.4, "MID_ORANGE": 0.7, "MID_RED": 1.1,
    "HIGH_YELLOW": 0.2, "HIGH_ORANGE": 0.5, "HIGH_RED": 0.85,
    "DISP_YELLOW": 2.0, "DISP_ORANGE": 5.0, "DISP_RED": 10.0,
}


def reading(station="ETNA01", low=0.0, mid=0.0, high=0.0, disp=0.0, ts=T):
    return TremorReading(
        station=station, timestamp=ts,
        amplitude_low=low, amplitude_mid=mid,
        amplitude_high=high, displacement=disp,
    )


# ══════════════════════════════════════════════════════════════════
# 1. Il comportamento di prima non deve cambiare
# ══════════════════════════════════════════════════════════════════

class TestRetrocompatibilita:

    @pytest.mark.parametrize("kwargs,atteso", [
        (dict(low=0.0, mid=0.0, high=0.0, disp=0.0), AlertLevel.GREEN),
        (dict(low=0.35), AlertLevel.YELLOW),
        (dict(mid=0.45), AlertLevel.YELLOW),
        (dict(high=0.25), AlertLevel.YELLOW),
        (dict(disp=2.5), AlertLevel.YELLOW),
        (dict(low=0.65), AlertLevel.ORANGE),
        (dict(high=0.55), AlertLevel.ORANGE),
        (dict(disp=6.0), AlertLevel.ORANGE),
        (dict(low=0.95), AlertLevel.RED),
        (dict(mid=1.2), AlertLevel.RED),
        (dict(disp=12.0), AlertLevel.RED),
    ])
    def test_livelli_default_invariati(self, kwargs, atteso):
        """
        Chiamata senza argomenti aggiuntivi: i livelli devono essere identici
        a quelli di prima del refactoring. È il requisito di retrocompatibilità.
        """
        alert = evaluate_alert(reading(**kwargs))
        assert alert.level == atteso, (
            f"Con {kwargs} il livello atteso è {atteso.value.upper()}, "
            f"ottenuto {alert.level.value.upper()}. Le dodici soglie di default "
            "devono restare quelle documentate nell'issue."
        )

    def test_batch_evaluate_ancora_chiamabile_con_un_argomento(self):
        """
        batch_evaluate è un chiamante che esiste già nel codebase e passa una
        sola lista. Deve continuare a funzionare senza modifiche al chiamante:
        i parametri nuovi vanno aggiunti come opzionali, non come obbligatori.
        """
        letture = [reading(low=0.0), reading(low=0.35), reading(low=0.95)]
        alerts = batch_evaluate(letture)
        livelli = [a.level for a in alerts]
        assert livelli == [AlertLevel.GREEN, AlertLevel.YELLOW, AlertLevel.RED], (
            "batch_evaluate(letture) deve restituire gli stessi livelli di prima. "
            f"Ottenuto: {[l.value for l in livelli]}. Se avete reso obbligatorio "
            "un parametro nuovo, questo chiamante è rotto."
        )


# ══════════════════════════════════════════════════════════════════
# 2. Soglie personalizzate
# ══════════════════════════════════════════════════════════════════

class TestSogliePersonalizzate:

    def test_soglie_custom_cambiano_il_livello(self):
        """Con soglie abbassate, la stessa lettura sale di livello."""
        r = reading(low=0.5)
        assert evaluate_alert(r).level == AlertLevel.YELLOW
        custom = dict(DEFAULTS, LOW_ORANGE=0.4)
        assert evaluate_alert(r, thresholds=custom).level == AlertLevel.ORANGE, (
            "Con LOW_ORANGE=0.4 una lettura low=0.5 deve dare ORANGE. "
            "Il dizionario passato non viene usato."
        )

    def test_dizionario_parziale_completato_dai_default(self):
        """
        Un dizionario che contiene solo alcune chiavi deve funzionare: le
        chiavi mancanti ricadono sui default. Un'implementazione che accede
        direttamente a thresholds["MID_RED"] solleva KeyError qui.
        """
        parziale = {"LOW_ORANGE": 0.4}
        try:
            alert = evaluate_alert(reading(low=0.5), thresholds=parziale)
        except KeyError as e:
            pytest.fail(
                f"KeyError su {e} con un dizionario parziale. Le soglie non "
                "presenti nel dizionario devono ricadere sui default, non "
                "essere lette direttamente dal dizionario del chiamante."
            )
        assert alert.level == AlertLevel.ORANGE, (
            "Con {'LOW_ORANGE': 0.4} e low=0.5 il livello atteso è ORANGE."
        )

    def test_le_soglie_del_chiamante_non_vengono_modificate(self):
        """
        La funzione non deve mutare il dizionario che riceve. Un'implementazione
        che fa thresholds.update(DEFAULTS) o setdefault sul dizionario passato
        modifica dati del chiamante: effetto collaterale non richiesto.
        """
        passato = {"LOW_ORANGE": 0.4}
        prima = copy.deepcopy(passato)
        evaluate_alert(reading(low=0.5), thresholds=passato)
        assert passato == prima, (
            f"Il dizionario passato è stato modificato: prima {prima}, "
            f"dopo {passato}. Lavorate su una copia, non sull'originale."
        )

    def test_soglie_custom_riutilizzabili_su_piu_chiamate(self):
        """
        Lo stesso dizionario usato per due letture deve dare risultati
        coerenti. Se la prima chiamata lo altera, la seconda cambia esito.
        """
        custom = dict(DEFAULTS, LOW_ORANGE=0.4)
        primo = evaluate_alert(reading(low=0.5), thresholds=custom).level
        secondo = evaluate_alert(reading(low=0.5), thresholds=custom).level
        assert primo == secondo == AlertLevel.ORANGE, (
            f"Due chiamate identiche hanno dato {primo.value} e {secondo.value}. "
            "Il dizionario di soglie viene alterato tra le chiamate."
        )


# ══════════════════════════════════════════════════════════════════
# 3. Provenienza delle soglie — il campo threshold_source
# ══════════════════════════════════════════════════════════════════

class TestProvenienzaSoglie:
    """
    Alert.threshold_source dice da dove vengono le soglie usate. È consumato
    da scripts/ingest_sample.py per annotare l'output. Un refactoring che
    fonde i dizionari e dimentica di aggiornare questo campo rompe quel
    consumatore senza che nessun test esistente lo segnali.
    """

    def test_default_e_etichettato_default(self):
        alert = evaluate_alert(reading(station="ETNA01", low=0.65))
        assert alert.threshold_source == "default", (
            f"threshold_source è '{alert.threshold_source}', atteso 'default' "
            "per una stazione senza override e senza soglie custom."
        )

    def test_override_stazione_e_etichettato_station_override(self):
        """
        STRO01 ha soglie alzate: una lettura che con i default sarebbe ORANGE
        deve dare YELLOW, e la provenienza deve dirlo.
        """
        r = reading(station="STRO01", low=0.65, mid=0.2, high=0.1, disp=2.5)
        alert = evaluate_alert(r)
        assert alert.level == AlertLevel.YELLOW, (
            f"STRO01 con low=0.65 deve dare YELLOW per effetto dell'override, "
            f"ottenuto {alert.level.value.upper()}."
        )
        assert alert.threshold_source == "station_override", (
            f"threshold_source è '{alert.threshold_source}', atteso "
            "'station_override'. La provenienza va impostata quando le soglie "
            "vengono da un override di stazione: ingest_sample.py la stampa."
        )

    def test_custom_e_etichettato_custom(self):
        custom = {k: 99.0 for k in DEFAULTS}
        alert = evaluate_alert(reading(low=0.5), thresholds=custom)
        assert alert.threshold_source == "custom", (
            f"threshold_source è '{alert.threshold_source}', atteso 'custom' "
            "quando il chiamante passa un dizionario di soglie."
        )


# ══════════════════════════════════════════════════════════════════
# 4. summarize_alerts — contratto completo
# ══════════════════════════════════════════════════════════════════

class TestSummarizeAlerts:

    def test_conteggi_e_totale(self):
        alerts = batch_evaluate([
            reading(low=0.0), reading(low=0.35),
            reading(low=0.65), reading(low=0.95),
        ])
        s = summarize_alerts(alerts)
        assert s["total"] == 4, f"total atteso 4, ottenuto {s.get('total')}"
        assert s["by_level"]["green"] == 1
        assert s["by_level"]["yellow"] == 1
        assert s["by_level"]["orange"] == 1
        assert s["by_level"]["red"] == 1, (
            f"by_level atteso un'allerta per livello, ottenuto {s.get('by_level')}"
        )

    def test_lista_vuota_non_solleva(self):
        s = summarize_alerts([])
        assert s["total"] == 0, (
            "summarize_alerts([]) deve restituire un riepilogo con total=0, "
            "non sollevare un'eccezione e non restituire None."
        )
        assert isinstance(s.get("by_level"), dict), (
            "by_level deve esserci anche con la lista vuota."
        )

    def test_stazione_piu_attiva(self):
        """
        Il riepilogo dichiara nella docstring la stazione più attiva: quella
        con più allerte non-GREEN. Va calcolata, non lasciata fuori.
        """
        alerts = batch_evaluate([
            reading(station="ETNA01", low=0.35),
            reading(station="ETNA01", low=0.65),
            reading(station="STRO02", low=0.35),
            reading(station="ETNA02", low=0.0),
        ])
        s = summarize_alerts(alerts)
        chiave = next(
            (k for k in s if "station" in k.lower() or "stazione" in k.lower()),
            None,
        )
        assert chiave is not None, (
            "Il riepilogo non contiene nessuna chiave sulla stazione più attiva. "
            f"Chiavi presenti: {sorted(s.keys())}. La docstring di "
            "summarize_alerts la richiede."
        )
        assert s[chiave] == "ETNA01", (
            f"La stazione più attiva è ETNA01 (due allerte non-GREEN), "
            f"il riepilogo dice {s[chiave]!r}."
        )
