import requests
import json

# Rennkalender 2026 (24 Rennen)
# Runde  9 = Barcelona (Gran Premio de Barcelona-Catalunya)
# Runde 16 = Spain     (Gran Premio de España → Madrid)
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Canada", "Monaco", "Barcelona", "Austria", "Great Britain", "Belgium",
    "Hungary", "Netherlands", "Italy", "Spain", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Jolpica API – "current" folgt automatisch der laufenden Saison
BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Team-Farben für Visualisierungen – Saison 2026
# WICHTIG: Die Namen müssen exakt mit den von der Jolpica API zurückgegebenen
# Fahrernamen übereinstimmen, sonst entstehen Dummy-Einträge mit 0 Punkten.
# Einträge hier dienen *nur* als Farb-Lookup; das standings-Dict wird
# ausschließlich aus API-Daten aufgebaut (kein Vorab-Befüllen).
TEAM_COLORS = {
    # Red Bull
    "Max Verstappen":        "#0600EF",
    "Isack Hadjar":          "#0600EF",
    # Mercedes
    "George Russell":        "#00D2BE",
    "Andrea Kimi Antonelli": "#00D2BE",
    # Ferrari
    "Charles Leclerc":       "#DC0000",
    "Lewis Hamilton":        "#DC0000",
    # McLaren
    "Lando Norris":          "#FF8700",
    "Oscar Piastri":         "#FF8700",
    # Aston Martin
    "Fernando Alonso":       "#006F62",
    "Lance Stroll":          "#006F62",
    # Williams
    "Alexander Albon":       "#005AFF",
    "Carlos Sainz":          "#005AFF",
    # Alpine
    "Pierre Gasly":          "#0090FF",
    "Franco Colapinto":      "#0090FF",
    # Racing Bulls
    "Liam Lawson":           "#0131d1",
    "Arvid Lindblad":        "#0131d1",
    # Haas
    "Esteban Ocon":          "#FFFFFF",
    "Oliver Bearman":        "#FFFFFF",
    # Audi (ex Sauber)
    "Nico Hülkenberg":       "#00e701",
    "Gabriel Bortoleto":     "#00e701",
    # Cadillac (neu)
    "Sergio Perez":          "#B0B0B0",
    "Valtteri Bottas":       "#B0B0B0",
}


def get_sprint_points(round_num):
    """Holt die Sprint-Punkte eines Rennwochenendes."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    response = requests.get(url)
    points = {}
    if response.status_code == 200:
        races = response.json()['MRData']['RaceTable']['Races']
        if races:
            for result in races[0]['SprintResults']:
                driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                points[driver] = int(float(result['points']))
    return points


def get_cumulative_points():
    """
    Berechnet kumulative Punkte pro Fahrer über die Saison.

    standings:    {Fahrername: [kumulierte Punkte nach Runde 1, 2, ...]}
    total_points: {Fahrername: Gesamtpunkte}

    Das standings-Dict wird AUSSCHLIESSLICH aus API-Daten aufgebaut.
    Dadurch entstehen keine Dummy-Einträge für Fahrer, die noch kein
    Rennen gefahren haben oder deren Name in TEAM_COLORS anders
    geschrieben war.
    """
    standings = {}
    total_points = {}

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        url = f"{BASE_URL}{round_num}/results.json"
        response = requests.get(url)
        if response.status_code != 200:
            # Rennen noch nicht gefahren oder API-Fehler → Rundenslot mit 0 auffüllen
            for driver in standings:
                standings[driver].append(total_points[driver])
            continue

        races = response.json()['MRData']['RaceTable']['Races']
        sprint_points = get_sprint_points(round_num)

        if not races:
            # Keine Ergebnisse → Rundenslot mit aktuellem Gesamtstand auffüllen
            for driver in standings:
                standings[driver].append(total_points[driver])
            continue

        current_round_points = {}
        for result in races[0]['Results']:
            driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
            race_pts = int(float(result['points'])) + sprint_points.get(driver, 0)
            current_round_points[driver] = race_pts

            # Fahrer beim ersten Auftreten initialisieren
            if driver not in standings:
                # Vergangene Runden mit 0 auffüllen
                standings[driver] = [0] * (round_num - 1)
                total_points[driver] = 0

        # Für alle bisher bekannten Fahrer den kumulierten Stand nach dieser Runde anhängen
        for driver in standings:
            total_points[driver] += current_round_points.get(driver, 0)
            standings[driver].append(total_points[driver])

    return standings, total_points


def write_driver_chart_json(standings, total_points):
    chart_data = {
        "labels": RACE_LOCATIONS,
        "series": [],
        "backgroundColor": "#191919"
    }

    # Sortiert nach Gesamtpunkten (absteigend) für übersichtlichere Charts
    sorted_drivers = sorted(standings.keys(), key=lambda d: total_points[d], reverse=True)

    for driver in sorted_drivers:
        chart_data["series"].append({
            "title": driver,
            "data": standings[driver],
            "color": TEAM_COLORS.get(driver, "#888888")  # Grau als Fallback für unbekannte Fahrer
        })

    with open("driver_chart.json", "w", encoding="utf-8") as f:
        json.dump(chart_data, f, ensure_ascii=False, indent=2)


def main():
    print("🔄 Lade Fahrerpunkte (Saison 2026)...")
    standings, total_points = get_cumulative_points()
    write_driver_chart_json(standings, total_points)
    print(f"✅ JSON für Diagramm erzeugt: driver_chart.json ({len(standings)} Fahrer)")
    print("\nAktuelle Gesamtwertung:")
    print("-" * 50)
    for i, (driver, pts) in enumerate(
        sorted(total_points.items(), key=lambda x: x[1], reverse=True), 1
    ):
        print(f"{i:2d}. {driver:<30} {pts:3d} Punkte")


if __name__ == "__main__":
    main()
