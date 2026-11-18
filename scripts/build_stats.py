#!/usr/bin/env python3
"""Build derived tables (match results, player standings) from the raw CSVs.

Raw data (edited by hand):   data/giocatori.csv, data/partite.csv,
                             data/presenze.csv, data/regole.csv
Derived data (regenerated):  data/derived/*.csv, data/derived/stats.json

Usage: python3 scripts/build_stats.py   (stdlib only, no dependencies)
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "derived"


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    """Empty cells count as 0 (stat not recorded)."""
    return int(v) if str(v).strip() else 0


def write(name, rows, fields):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    players = {p["id_giocatore"]: p for p in read("giocatori.csv")}
    matches = {m["id_partita"]: m for m in read("partite.csv")}
    apps = read("presenze.csv")
    rules = {r["chiave"]: int(r["valore"]) for r in read("regole.csv")}

    # --- validation -------------------------------------------------------
    errors = []
    seen = set()
    for a in apps:
        if a["id_partita"] not in matches:
            errors.append(f"unknown match {a['id_partita']}")
        if a["id_giocatore"] not in players:
            errors.append(f"unknown player {a['id_giocatore']}")
        if a["squadra"] not in ("A", "B"):
            errors.append(f"bad team '{a['squadra']}' for {a['id_giocatore']}")
        key = (a["id_partita"], a["id_giocatore"])
        if key in seen:
            errors.append(f"duplicate appearance {key}")
        seen.add(key)
    if errors:
        sys.exit("Validation errors:\n  " + "\n  ".join(errors))

    # --- match results ----------------------------------------------------
    # Team goals = own players' goals + opponents' own goals.
    goals = defaultdict(lambda: {"A": 0, "B": 0})
    own_goals = defaultdict(lambda: {"A": 0, "B": 0})  # own goals committed BY team
    for a in apps:
        t, other = a["squadra"], "B" if a["squadra"] == "A" else "A"
        goals[a["id_partita"]][t] += num(a["gol"])
        goals[a["id_partita"]][other] += num(a["autogol"])
        own_goals[a["id_partita"]][t] += num(a["autogol"])

    results = []
    for mid, m in sorted(matches.items(), key=lambda x: (x[1]["data"], x[0])):
        g = goals[mid]
        winner = "A" if g["A"] > g["B"] else "B" if g["B"] > g["A"] else "X"
        og = own_goals[mid]
        results.append({**{k: m[k] for k in ("id_partita", "data", "stagione")},
                        "squadra_A": m.get("squadra_A") or "A",
                        "squadra_B": m.get("squadra_B") or "B",
                        "colore_A": m.get("colore_A", ""),
                        "colore_B": m.get("colore_B", ""),
                        "gol_A": g["A"], "gol_B": g["B"],
                        "autogol_A": og["A"], "autogol_B": og["B"],
                        "vincitore": winner})
    res_by_id = {r["id_partita"]: r for r in results}

    # --- per-appearance detail -------------------------------------------
    detail = []
    for a in apps:
        r = res_by_id[a["id_partita"]]
        t = a["squadra"]
        fatti, subiti = r[f"gol_{t}"], r["gol_B" if t == "A" else "gol_A"]
        esito = "X" if r["vincitore"] == "X" else ("V" if r["vincitore"] == t else "S")
        detail.append({**a, "data": r["data"], "stagione": r["stagione"],
                       "nome_squadra": r[f"squadra_{t}"],
                       "gol_squadra": fatti, "gol_subiti": subiti, "esito": esito})

    # --- standings per season ---------------------------------------------
    pts = {"V": rules["punti_vittoria"], "X": rules["punti_pareggio"],
           "S": rules["punti_sconfitta"]}
    agg = defaultdict(lambda: defaultdict(int))
    for d in detail:
        s = agg[(d["stagione"], d["id_giocatore"])]
        s["presenze"] += 1
        s["presenze_porta"] += d["ruolo"] == "P"
        s[{"V": "vittorie", "X": "pareggi", "S": "sconfitte"}[d["esito"]]] += 1
        s["punti"] += pts[d["esito"]]
        for k in ("gol", "assist", "autogol", "parate_miracolose", "pali_traverse"):
            s[k] += num(d[k])
        s["gol_squadra"] += d["gol_squadra"]
        s["gol_subiti"] += d["gol_subiti"]
        s["gol_subiti_in_porta"] += d["gol_subiti"] if d["ruolo"] == "P" else 0

    seasons = sorted({m["stagione"] for m in matches.values()})
    standings = []
    for season in seasons:
        for pid, p in players.items():
            s = agg.get((season, pid), defaultdict(int))
            n = s["presenze"]
            standings.append({
                "stagione": season, "id_giocatore": pid,
                "giocatore": f"{p['nome']} {p['cognome']}",
                "soprannome": p["soprannome"],
                "presenze": n, "presenze_porta": s["presenze_porta"],
                "vittorie": s["vittorie"], "pareggi": s["pareggi"],
                "sconfitte": s["sconfitte"], "punti": s["punti"],
                "gol": s["gol"], "assist": s["assist"], "autogol": s["autogol"],
                "parate_miracolose": s["parate_miracolose"],
                "pali_traverse": s["pali_traverse"],
                "gol_squadra": s["gol_squadra"], "gol_subiti": s["gol_subiti"],
                "differenza_reti": s["gol_squadra"] - s["gol_subiti"],
                "gol_subiti_in_porta": s["gol_subiti_in_porta"],
                "perc_vittorie": round(100 * s["vittorie"] / n, 1) if n else "",
                "gol_per_partita": round(s["gol"] / n, 2) if n else "",
            })
    # Ranking: points, then goal difference, then goals, then fewer appearances.
    standings.sort(key=lambda r: (r["stagione"], r["presenze"] == 0, -r["punti"],
                                  -r["differenza_reti"], -r["gol"], r["presenze"],
                                  r["giocatore"]))
    for season in seasons:
        rows = [r for r in standings if r["stagione"] == season]
        for i, r in enumerate([r for r in rows if r["presenze"]], 1):
            r["posizione"] = i
        for r in rows:
            r.setdefault("posizione", "")

    OUT.mkdir(exist_ok=True)
    write("risultati_partite.csv", results, list(results[0].keys()))
    write("dettaglio_presenze.csv", detail, list(detail[0].keys()))
    fields = ["stagione", "posizione"] + [k for k in standings[0] if k not in ("stagione", "posizione")]
    write("classifica.csv", standings, fields)
    bundle = {"giocatori": list(players.values()), "partite": results,
              "presenze": detail, "classifica": standings, "regole": rules}
    with open(OUT / "stats.json", "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=1)
    # Same data as a JS file, so the dashboard also works when opened from
    # disk (file://), where fetch() of a local JSON is blocked by browsers.
    with open(OUT / "data.js", "w", encoding="utf-8") as f:
        f.write("window.CALCETTO = ")
        json.dump(bundle, f, ensure_ascii=False)
        f.write(";\n")
    print(f"OK: {len(matches)} matches, {len(apps)} appearances, {len(players)} players")


if __name__ == "__main__":
    main()
