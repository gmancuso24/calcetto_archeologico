# Calcetto Archeologico

Weekly five-a-side football data: raw CSV tables, a script that derives
results and standings, and (later) a GitHub Pages dashboard.

## Structure

```
data/
  giocatori.csv        players (one row per person)
  partite.csv          matches (one row per match)
  presenze.csv         who played which match, in which team/role, with stats
  regole.csv           scoring rules (points for win/draw/loss)
  derived/             GENERATED - do not edit by hand
    risultati_partite.csv   final score of each match
    dettaglio_presenze.csv  appearances joined with result
    classifica.csv          season standings per player
    stats.json              everything in one file, for the dashboard
scripts/
  build_stats.py       regenerates data/derived/ (stdlib only)
```

## Data model

```
giocatori (1) ──< presenze >── (1) partite
```

**giocatori.csv** — `id_giocatore` (slug, primary key), `nome`, `cognome`,
`soprannome`, `ruolo_abituale` (optional, same codes as below), `attivo` (1/0),
`foto` (optional path).

**partite.csv** — `id_partita` (`<season>-<progressive>`, e.g. `2026-27-001`),
`data` (ISO `YYYY-MM-DD`), `stagione`, `luogo`, `squadra_A`, `colore_A`,
`squadra_B`, `colore_B`, `note`. Team names are free text; colours are one of
`rosso, blu, azzurro, verde, giallo, arancio, viola, bianco, nero, grigio`
(empty = default blue/orange).
The score is *not* stored here: it is computed from the players' goals.
Teams change every week: line-ups are defined match by match in `presenze.csv`.

**presenze.csv** — one row per player per match. Key: (`id_partita`, `id_giocatore`).
`squadra` (`A`/`B`), `ruolo` (see role codes),
`gol`, `assist`, `autogol`, `parate_miracolose`, `pali_traverse`.
Empty cell = stat not recorded (counted as 0).

Team score = own players' goals + opponents' own goals (`autogol`).
`risultati_partite.csv` reports `autogol_A` / `autogol_B` = own goals
committed by each side (i.e. goals gifted to the opponent).

## Standings

Ranking: points → goal difference → goals scored → fewer appearances.
Points are set in `regole.csv` (currently win = 1, draw = 0, loss = 0).
`gol_subiti` is the goals conceded by the player's team; `gol_subiti_in_porta`
counts only matches where the player was in goal.

## Adding a match

1. Add a row to `partite.csv`.
2. Add one row per player to `presenze.csv` (new players go in `giocatori.csv` first).
3. Run `python3 scripts/build_stats.py` (it validates IDs and duplicates).

## Dashboard

Static site, no build tools: `index.html` + `assets/` + `data/derived/data.js`.
Open `index.html` directly in a browser (works from disk) or publish the repo
with GitHub Pages (branch root). After editing the CSVs, run
`python3 scripts/build_stats.py` and reload.

Pages (hash routing): `#/` home, `#/classifiche/<board>`, `#/partite`,
`#/partita/<id_partita>`, `#/giocatori`, `#/giocatore/<id_giocatore>`.

**Player photos:** put square images in `assets/foto/` and set the `foto`
column of `giocatori.csv` (e.g. `assets/foto/luigi-poggi.jpg`). Without a
photo the initials are shown.

**Role codes** (`presenze.ruolo`, drive the pitch layout):

| Code | Role |
|---|---|
| `P` | Portiere (goalkeeper) |
| `D` | Difensore (defender) |
| `MS` | Mediano sinistro (left midfielder) |
| `MD` | Mediano destro (right midfielder) |
| `A` | Attaccante (forward) |
