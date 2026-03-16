import requests
import json

# Rennkalender 2026 – Reihenfolge = Rundennummern 1–24
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Farben pro Fahrer – Saison 2026
# Namen MÜSSEN exakt mit der Jolpica API übereinstimmen
TEAM_COLORS = {
    "Max Verstappen":        "#3570c5",
    "Isack Hadjar":          "#3570c5",
    "George Russell":        "#42f4d7",
    "Andrea Kimi Antonelli": "#42f4d7",
    "Charles Leclerc":       "#e8002d",
    "Lewis Hamilton":        "#e8002d",
    "Lando Norris":          "#ff8102",
    "Oscar Piastri":         "#ff8102",
    "Fernando Alonso":       "#20956e",
    "Lance Stroll":          "#20956e",
    "Alexander Albon":       "#1868db",
    "Carlos Sainz":          "#1868db",
    "Pierre Gasly":          "#00a1e8",
    "Franco Colapinto":      "#00a1e8",
    "Liam Lawson":           "#6692ff",
    "Arvid Lindblad":        "#6692ff",
    "Esteban Ocon":          "#dee1e2",
    "Oliver Bearman":        "#dee1e2",
    "Nico Hülkenberg":       "#ff2d00",
    "Gabriel Bortoleto":     "#ff2d00",
    "Sergio Pérez":          "#aaaaad",
    "Valtteri Bottas":       "#aaaaad",
}


def get_sprint_points(round_num):
    """Gibt dict {Fahrername: Sprint-Punkte} für eine Runde zurück."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        races = r.json()["MRData"]["RaceTable"]["Races"]
        if not races:
            return {}
        return {
            f"{res['Driver']['givenName']} {res['Driver']['familyName']}": int(float(res["points"]))
            for res in races[0]["SprintResults"]
        }
    except Exception:
        return {}


def build_cumulative_standings():
    """
    Baut die kumulativen Standings auf.

    Rückgabe:
        per_round_cumulative: {Fahrername: [kumulPunkte_R1, ..., kumulPunkte_R24]}
        total:                {Fahrername: Gesamtpunkte}

    Logik:
    - Alle 22 bekannten Fahrer starten mit 0.
    - Für jede Runde: hole race results + sprint results.
      Wenn keine Ergebnisse (Rennen noch nicht gefahren): alle Fahrer
      behalten ihren bisherigen Gesamtstand (flaches Fortschreiben).
    - Am Ende hat jeder Fahrer exakt 24 Einträge.
    """
    num_races = len(RACE_LOCATIONS)

    # Laufende Gesamtpunkte – wird Runde für Runde akkumuliert
    running_total = {driver: 0 for driver in TEAM_COLORS}

    # Ergebnisliste: pro Fahrer 24 Einträge (kumulativ)
    cumulative = {driver: [] for driver in TEAM_COLORS}

    for round_idx, location in enumerate(RACE_LOCATIONS):
        round_num = round_idx + 1

        # Race results holen
        race_pts_this_round = {}
        try:
            r = requests.get(f"{BASE_URL}{round_num}/results.json", timeout=10)
            if r.status_code == 200:
                races = r.json()["MRData"]["RaceTable"]["Races"]
                if races:
                    sprint_pts = get_sprint_points(round_num)
                    for res in races[0]["Results"]:
                        name = f"{res['Driver']['givenName']} {res['Driver']['familyName']}"
                        pts = int(float(res["points"])) + sprint_pts.get(name, 0)
                        race_pts_this_round[name] = pts

                        # Unbekannter Fahrer (Ersatz) dynamisch ergänzen
                        if name not in running_total:
                            running_total[name] = 0
                            cumulative[name] = [0] * round_idx  # vergangene Runden = 0
        except Exception:
            pass  # Netzwerkfehler → Runde als nicht gefahren behandeln

        # Kumulierten Stand für alle bekannten Fahrer fortschreiben
        for driver in running_total:
            running_total[driver] += race_pts_this_round.get(driver, 0)
            cumulative[driver].append(running_total[driver])

    return cumulative, running_total


def write_json(cumulative, total):
    """Schreibt driver_chart.json im exakt erwarteten Format."""
    # Sortiere nach Gesamtpunkten absteigend
    sorted_drivers = sorted(total.keys(), key=lambda d: total[d], reverse=True)

    chart = {
        "labels": RACE_LOCATIONS,
        "series": [
            {
                "title": driver,
                "data":  cumulative[driver],
                "color": TEAM_COLORS.get(driver, "#888888")
            }
            for driver in sorted_drivers
        ],
        "backgroundColor": "#191919"
    }

    with open("driver_chart.json", "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)

    print(f"✅ driver_chart.json geschrieben – {len(sorted_drivers)} Fahrer, {len(RACE_LOCATIONS)} Runden")

    # Konsolenausgabe zur Kontrolle
    print("\nStandings:")
    print("-" * 45)
    for i, driver in enumerate(sorted_drivers, 1):
        pts = total[driver]
        # Zeige die letzten 3 nicht-null-Einträge als Vorschau
        preview = [str(x) for x in cumulative[driver] if x > 0][-3:]
        preview_str = f"[...{', '.join(preview)}]" if preview else "[0, 0, ...]"
        print(f"{i:2d}. {driver:<30} {pts:4d} Pts  {preview_str}")


def main():
    print("🔄 Lade F1 2026 Fahrerpunkte (kumulativ)...")
    cumulative, total = build_cumulative_standings()
    write_json(cumulative, total)


if __name__ == "__main__":
    main()
