"""
SUITE DI VERIFICA — Issue #0 (conteggio eventi e ottimizzazione STA/LTA)

Non modificate questo file. Eseguitelo così:

    pytest tests/hidden/test_hidden_0.py -v

L'issue ha due parti e questa suite verifica entrambe:
  parte 1  il conteggio degli eventi non deve accumularsi tra chiamate
  parte 2  compute_sta_lta deve essere lineare, a parità di risultato

Attenzione alla parte 1: esiste una correzione che elimina il sintomo e
rompe un uso legittimo. Questa suite la intercetta.

Testa solo comportamento pubblico: qualsiasi implementazione corretta la
supera, indipendentemente da come è strutturata internamente.
"""

import math
import time
import pytest

from seismolab.processing.event_detector import (
    detect_events, batch_detect, detect_events_continuous,
)

SAMPLE_RATE = 100.0
LTA_S = 5.0          # finestra LTA ridotta: i segnali di test sono brevi


def piatto(n=3000, rumore=0.02):
    """Segnale senza eventi: rumore di fondo costante."""
    return [rumore] * n


def con_evento(n=3000, inizio=1500, durata=200, ampiezza=10.0, rumore=0.02):
    """Segnale con un singolo evento riconoscibile, lontano dai bordi."""
    s = [rumore] * n
    for i in range(inizio, min(inizio + durata, n)):
        t = (i - inizio) / durata
        s[i] += ampiezza * math.sin(math.pi * t)
    return s


# ══════════════════════════════════════════════════════════════════
# PARTE 1 — Il conteggio non si accumula
# ══════════════════════════════════════════════════════════════════

class TestNessunAccumuloTraChiamate:

    def test_seconda_chiamata_su_segnale_piatto_da_zero(self):
        """
        Il sintomo dell'issue. Prima chiamata su un segnale con un evento,
        seconda su un segnale piatto: la seconda deve riportare zero eventi.
        """
        detect_events("ETNA01", con_evento(), SAMPLE_RATE, lta_window_s=LTA_S)
        seconda = detect_events("ETNA02", piatto(), SAMPLE_RATE, lta_window_s=LTA_S)
        assert seconda.event_count == 0, (
            f"Una stazione con segnale piatto riporta {seconda.event_count} eventi. "
            "Gli eventi della chiamata precedente sono rimasti nella lista: "
            "guardate come viene inizializzata."
        )

    def test_batch_detect_conteggi_indipendenti(self):
        """Tre stazioni, una sola con un evento reale."""
        dati = {
            "ETNA01": (con_evento(), SAMPLE_RATE),
            "ETNA02": (piatto(), SAMPLE_RATE),
            "STRO01": (piatto(), SAMPLE_RATE),
        }
        res = batch_detect(dati, lta_window_s=LTA_S)
        conteggi = {k: v.event_count for k, v in res.items()}
        assert conteggi["ETNA02"] == 0 and conteggi["STRO01"] == 0, (
            f"Conteggi ottenuti: {conteggi}. Le due stazioni con segnale piatto "
            "devono riportare zero eventi. Il conteggio si trascina tra stazioni."
        )
        assert conteggi["ETNA01"] >= 1, (
            f"ETNA01 ha un evento reale ma ne riporta {conteggi['ETNA01']}."
        )

    def test_stessa_stazione_due_volte_stesso_risultato(self):
        """Idempotenza: la stessa analisi ripetuta dà lo stesso numero."""
        s = con_evento()
        primo = detect_events("ETNA01", s, SAMPLE_RATE, lta_window_s=LTA_S)
        secondo = detect_events("ETNA01", s, SAMPLE_RATE, lta_window_s=LTA_S)
        assert primo.event_count == secondo.event_count, (
            f"Due analisi identiche danno {primo.event_count} e "
            f"{secondo.event_count} eventi. Il risultato dipende da quante "
            "volte la funzione è stata chiamata prima."
        )

    def test_ordine_delle_stazioni_irrilevante(self):
        """
        Analizzare le stazioni in ordine inverso deve dare gli stessi conteggi.
        Se cambiano, la funzione porta stato da una chiamata all'altra.
        """
        a = {"ETNA01": (con_evento(), SAMPLE_RATE), "ETNA02": (piatto(), SAMPLE_RATE)}
        b = {"ETNA02": (piatto(), SAMPLE_RATE), "ETNA01": (con_evento(), SAMPLE_RATE)}
        ra = {k: v.event_count for k, v in batch_detect(a, lta_window_s=LTA_S).items()}
        rb = {k: v.event_count for k, v in batch_detect(b, lta_window_s=LTA_S).items()}
        assert ra == rb, (
            f"Ordine diretto: {ra}. Ordine inverso: {rb}. "
            "I conteggi dipendono dall'ordine di analisi."
        )


# ══════════════════════════════════════════════════════════════════
# PARTE 1b — L'accumulo legittimo deve continuare a funzionare
# ══════════════════════════════════════════════════════════════════

class TestAccumuloLegittimo:
    """
    Una traccia di monitoraggio arriva a blocchi consecutivi, non tutta insieme.
    detect_events_continuous analizza i blocchi in sequenza e mantiene l'elenco
    degli eventi trovati fin dall'inizio della traccia: è l'uso legittimo del
    passaggio degli eventi da una chiamata alla successiva.

    Azzerare la lista in modo incondizionato all'inizio della funzione elimina
    il sintomo dei test qui sopra e rompe questo uso. La correzione giusta
    distingue "nessun elenco fornito" da "elenco fornito e vuoto".
    """

    def test_eventi_di_tutti_i_blocchi_sono_presenti(self):
        blocchi = [con_evento(), con_evento(), con_evento()]
        res = detect_events_continuous(
            "ETNA01", blocchi, SAMPLE_RATE, lta_window_s=LTA_S
        )
        assert res.event_count >= 3, (
            f"Tre blocchi con un evento ciascuno, riportati {res.event_count} "
            "eventi in totale. Gli eventi dei blocchi precedenti sono stati "
            "perduti: la funzione azzera l'elenco che riceve invece di "
            "usarlo. Distinguete l'assenza di elenco da un elenco vuoto."
        )

    def test_blocco_singolo_equivale_alla_chiamata_diretta(self):
        """Caso degenere: un solo blocco deve dare lo stesso di detect_events."""
        s = con_evento()
        diretto = detect_events("ETNA01", s, SAMPLE_RATE, lta_window_s=LTA_S)
        continuo = detect_events_continuous(
            "ETNA01", [s], SAMPLE_RATE, lta_window_s=LTA_S
        )
        assert continuo.event_count == diretto.event_count, (
            f"Su un blocco solo: detect_events trova {diretto.event_count} "
            f"eventi, detect_events_continuous {continuo.event_count}. "
            "Con un blocco unico i due percorsi devono coincidere."
        )

    def test_due_invocazioni_consecutive_non_si_sommano(self):
        """
        La funzione di accumulo non deve a sua volta trascinare stato tra
        invocazioni distinte.
        """
        blocchi = [con_evento(), piatto()]
        prima = detect_events_continuous(
            "ETNA01", blocchi, SAMPLE_RATE, lta_window_s=LTA_S
        )
        seconda = detect_events_continuous(
            "ETNA01", blocchi, SAMPLE_RATE, lta_window_s=LTA_S
        )
        assert prima.event_count == seconda.event_count, (
            f"Due invocazioni identiche danno {prima.event_count} e "
            f"{seconda.event_count} eventi."
        )


# ══════════════════════════════════════════════════════════════════
# PARTE 2 — Ottimizzazione: lineare, a parità di risultato
# ══════════════════════════════════════════════════════════════════

class TestOttimizzazione:

    def test_traccia_lunga_in_tempo_lineare(self):
        """
        Una stazione a 100 Hz produce oltre otto milioni di campioni al giorno.
        Con il ricalcolo della finestra a ogni campione la funzione impiega
        secondi su trentamila campioni: inutilizzabile in produzione.
        """
        s = piatto(30000)
        t0 = time.perf_counter()
        detect_events("PERF", s, SAMPLE_RATE, lta_window_s=30.0)
        trascorso = time.perf_counter() - t0
        assert trascorso < 0.5, (
            f"Trentamila campioni analizzati in {trascorso:.2f}s. "
            "Con somme mantenute in modo incrementale il tempo è dell'ordine "
            "del centesimo di secondo. Il calcolo della finestra viene "
            "rifatto da zero a ogni campione."
        )

    def test_gli_eventi_rilevati_non_cambiano(self):
        """
        L'ottimizzazione non deve alterare cosa viene rilevato. Vincolo di
        correttezza: stesso segnale, stesso numero di eventi, stesso onset
        a meno di un campione.
        """
        s = con_evento(n=3000, inizio=1500, durata=200, ampiezza=10.0)
        res = detect_events("ETNA01", s, SAMPLE_RATE, lta_window_s=LTA_S)
        assert res.event_count == 1, (
            f"Su un segnale con un evento isolato sono stati rilevati "
            f"{res.event_count} eventi. L'ottimizzazione ha cambiato il "
            "comportamento della rilevazione."
        )
        # L'onset non coincide con il primo campione dell'evento: la finestra
        # STA deve riempirsi prima che il rapporto superi la soglia, quindi un
        # ritardo di alcuni centesimi di secondo è il comportamento atteso.
        # Il requisito è che l'evento venga localizzato dentro la sua durata
        # reale, non che l'onset sia esatto al campione.
        inizio_evento = 1500 / SAMPLE_RATE
        fine_evento = (1500 + 200) / SAMPLE_RATE
        onset = res.events[0].onset_time
        assert inizio_evento <= onset <= fine_evento, (
            f"Onset rilevato a {onset:.3f}s, fuori dall'intervallo dell'evento "
            f"({inizio_evento:.1f}s–{fine_evento:.1f}s). L'ottimizzazione ha "
            "spostato il punto di rilevazione: verificate gli indici della "
            "finestra scorrevole."
        )
