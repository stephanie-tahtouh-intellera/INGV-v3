"""
Verifica dei vostri test: il sabotaggio.

Questo strumento prende il *vostro* file, ci introduce una singola alterazione
(un operatore o una costante), e lancia i *vostri* test contro la versione
alterata in una copia temporanea del repository. Il vostro codice non viene
toccato.

    python scripts/check_sabotage.py --issue 17

Se i vostri test passano anche sul file alterato, non stanno verificando il
comportamento che credete. Lo scoprite in trenta secondi invece che in
produzione.

Uso:
    --issue {17,23,0}    quale issue verificare
    --keep               non cancellare la copia temporanea (per ispezionarla)
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent

# Per ogni issue: il modulo da alterare, il file di test del partecipante,
# e le alterazioni candidate in ordine di preferenza.
CONFIGURAZIONE = {
    "17": {
        "modulo": "seismolab/alerts/volcanic.py",
        "test": "tests/test_volcanic.py",
        "candidate": [
            (r">=", ">", "un confronto di soglia da >= a >"),
            (r"<=", "<", "un confronto di soglia da <= a <"),
        ],
    },
    "0": {
        "modulo": "seismolab/processing/event_detector.py",
        "test": "tests/test_event_detector.py",
        "candidate": [
            (r"0\.7", "0.4", "il fattore di isteresi da 0.7 a 0.4"),
            (r">=", ">", "un confronto di soglia da >= a >"),
        ],
    },
    "23": {
        "modulo": "seismolab/data/gps_query.py",
        "test": "tests/test_gps.py",
        "candidate": [
            (r"\bASC\b", "DESC", "l'ordinamento della query da ASC a DESC"),
            (r">=", ">", "un confronto da >= a >"),
        ],
    },
}


def copia_repository(destinazione: Path) -> None:
    ignora = shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", ".git", "*.pyc", ".venv", "venv"
    )
    shutil.copytree(RADICE, destinazione, ignore=ignora, dirs_exist_ok=True)


def esegui_test(radice: Path, file_test: str) -> tuple[bool, str]:
    esito = subprocess.run(
        [sys.executable, "-m", "pytest", file_test, "-q", "--no-header", "-p",
         "no:cacheprovider"],
        cwd=radice, capture_output=True, text=True,
    )
    coda = esito.stdout.strip().splitlines()
    riepilogo = coda[-1] if coda else "(nessun output)"
    return esito.returncode == 0, riepilogo


def applica_alterazione(percorso: Path, candidate) -> str | None:
    """Applica la prima alterazione applicabile. Restituisce la descrizione."""
    sorgente = percorso.read_text()
    for schema, sostituzione, descrizione in candidate:
        nuovo, quante = re.subn(schema, sostituzione, sorgente, count=1)
        if quante:
            percorso.write_text(nuovo)
            return descrizione
    return None


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--issue", required=True, choices=sorted(CONFIGURAZIONE))
    ap.add_argument("--keep", action="store_true")
    argomenti = ap.parse_args()

    conf = CONFIGURAZIONE[argomenti.issue]
    temporanea = Path(tempfile.mkdtemp(prefix=f"m4_sabotaggio_{argomenti.issue}_"))

    try:
        copia_repository(temporanea)

        print("=" * 64)
        print(f"SABOTAGGIO — issue #{argomenti.issue}")
        print("=" * 64)
        print(f"Modulo alterato : {conf['modulo']}")
        print(f"Test eseguiti   : {conf['test']}")
        print()

        # Passo 1: i vostri test devono passare sul vostro codice, altrimenti
        # il confronto non dice niente.
        print("Passo 1 — i vostri test sul vostro codice, non alterato")
        verde, riepilogo = esegui_test(temporanea, conf["test"])
        print(f"  {riepilogo}")
        if not verde:
            print()
            print("I vostri test non passano già adesso. Il sabotaggio non ha")
            print("senso in questa condizione: sistemate prima la suite, poi")
            print("rilanciate questo comando.")
            return 2

        # Passo 2: alterazione singola
        percorso_modulo = temporanea / conf["modulo"]
        descrizione = applica_alterazione(percorso_modulo, conf["candidate"])
        if descrizione is None:
            print()
            print("Nessuna delle alterazioni previste è applicabile al vostro")
            print("codice. Segnalatelo al docente: serve una variante.")
            return 3

        print()
        print("Passo 2 — gli stessi test sul file alterato")
        verde_alterato, riepilogo_alterato = esegui_test(temporanea, conf["test"])
        print(f"  {riepilogo_alterato}")
        print()
        print("=" * 64)

        if verde_alterato:
            print("I VOSTRI TEST NON HANNO INTERCETTATO IL SABOTAGGIO")
            print("=" * 64)
            print()
            print(f"È stato alterato: {descrizione}.")
            print()
            print("Il codice si comporta in modo diverso e la vostra suite non")
            print("se ne accorge. Questo è il criterio del fallimento applicato")
            print("dall'esterno: un test che non può fallire non verifica nulla.")
            print()
            print("Cosa fare adesso: aggiungete o riscrivete i test in modo che")
            print("questa alterazione li faccia diventare rossi. Poi rilanciate.")
            return 1

        print("SABOTAGGIO INTERCETTATO")
        print("=" * 64)
        print()
        print(f"È stato alterato: {descrizione}.")
        print("La vostra suite lo ha rilevato. I test verificano il")
        print("comportamento, non solo la sua assenza di errori.")
        return 0

    finally:
        if argomenti.keep:
            print(f"\nCopia temporanea conservata in: {temporanea}")
        else:
            shutil.rmtree(temporanea, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
