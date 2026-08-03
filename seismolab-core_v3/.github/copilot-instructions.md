# SeismoLab Core — istruzioni per GitHub Copilot

Progetto Python 3.13 per processamento di dati geofisici (sismica, vulcanologia, GPS geodetic).

## Regole obbligatorie

- Type hints per tutte le funzioni pubbliche
- Test con pytest e fixture — mai unittest
- Query SQL con psycopg2 e placeholder %s — mai f-string, mai .format()
- Connessioni DB come parametro alle funzioni, mai aperte internamente
- Nessuna dipendenza esterna oltre a requirements.txt

## Patch chirurgiche

Modifica solo il minimo necessario. Non riscrivere funzioni esistenti.
Non rinominare variabili. I test esistenti devono passare dopo ogni modifica.
