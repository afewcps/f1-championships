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

# Mapping: API-Name → Anzeigename
# Deckt alle bekannten Varianten ab (inkl. "Cadillac F1 Team" → "Cadillac")
API_TO_DISPLAY_NAME = {
    "Alpine F1 Team":  "Alpine",
    "RB F1 Team":      "Racing Bulls",
    "Haas F1 Team":    "Haas",
    "Cadillac F1 Team": "Cadillac",
}

# Teamfarben – Saison 2026
TEAM_COLORS = {
    "Red Bull":      "#3570c5",
    "Mercedes":      "#3570c5",
    "Ferrari":       "#e8002d",
    "McLaren":       "#ff8102",
    "Aston Martin":  "#20956e",
    "Williams":      "#1868db",
    "Alpine":        "#00a1e8",
    "Racing Bulls":  "#6692ff",
    "Haas":          "#dee1e2",
    "Audi":          "#ff2d00",
    "Cadillac":      "#aaaaad",
}

ALL_TEAMS = list(TEAM_COLORS.keys())


def get_sprint_points(round_num):
    """Gibt dict {Anzeigename: Sprint-Punkte} für eine Runde zurück."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    points = {}
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            races = r.json()["MRData"]["RaceTable"]["Races"]
            if races:
                for res in races[0]["SprintResults"]:
                    api_name     = res["Constructor"]["name"]
                    display_name = API_TO_DISPLAY_NAME.get(api_name, api_name)
                    points[display_name] = points.get(display_name, 0) + int(float(res["points"]))
    except Exception:
        pass
    return points


def build_cumulative_standings():
    """
    Baut kumulative Konstrukteurs-Standings auf.
    Alle 11 Teams starten als Seed mit 0 – die JSON enthält immer alle Teams.
    Noch nicht gefahrene Runden werden mit dem letzten Stand fortgeschrieben.
    """
    running_total = {team: 0 for team in ALL_TEAMS}
    cumulative    = {team: [] for team in ALL_TEAMS}

    for round_idx, _ in enumerate(RACE_LOCATIONS):
        round_num  = round_idx + 1
        round_pts  = {}

        try:
            r = requests.get(f"{BASE_URL}{round_num}/results.json", timeout=10)
            if r.status_code == 200:
                races = r.json()["MRData"]["RaceTable"]["Races"]
                if races:
                    sprint_pts = get_sprint_points(round_num)
                    for res in races[0]["Results"]:
                        api_name     = res["Constructor"]["name"]
                        display_name = API_TO_DISPLAY_NAME.get(api_name, api_name)
                        round_pts[display_name] = round_pts.get(display_name, 0) + int(float(res["points"]))

                    for team, pts in sprint_pts.items():
                        round_pts[team] = round_pts.get(team, 0) + pts

                    # Unbekannte Teams dynamisch ergänzen
                    for team in round_pts:
                        if team not in running_total:
                            running_total[team] = 0
                            cumulative[team]    = [0] * round_idx
        except Exception:
            pass

        for team in running_total:
            running_total[team] += round_pts.get(team, 0)
            cumulative[team].append(running_total[team])

    return cumulative, running_total


def write_json(cumulative, total):
    sorted_teams = sorted(total.keys(), key=lambda t: total[t], reverse=True)

    chart = {
        "labels": RACE_LOCATIONS,
        "series": [
            {
                "title": team,
                "data":  cumulative[team],
                "color": TEAM_COLORS.get(team, "#888888")
            }
            for team in sorted_teams
        ],
        "backgroundColor": "#191919"
    }

    with open("constructor_chart.json", "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)

    print(f"✅ constructor_chart.json geschrieben – {len(sorted_teams)} Teams, {len(RACE_LOCATIONS)} Runden")
    print("\nStandings:")
    print("-" * 45)
    for i, team in enumerate(sorted_teams, 1):
        pts     = total[team]
        preview = [str(x) for x in cumulative[team] if x > 0][-3:]
        preview_str = f"[...{', '.join(preview)}]" if preview else "[0, 0, ...]"
        print(f"{i:2d}. {team:<25} {pts:4d} Pts  {preview_str}")


def main():
    print("🔄 Lade F1 2026 Konstrukteurspunkte (kumulativ)...")
    cumulative, total = build_cumulative_standings()
    write_json(cumulative, total)


if __name__ == "__main__":
    main()
