import requests
import json

# Liste der Rennorte für die Saison 2025
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Emilia-Romagna", "Monaco", "Spain", "Canada", "Austria", "Great Britain",
    "Belgium", "Hungary", "Netherlands", "Italy", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Jolpica API
BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Teamfarben
TEAM_COLORS = {
    "Max Verstappen": "#0600EF", "Yuki Tsunoda": "#0600EF",
    "George Russell": "#00D2BE", "Andrea Kimi Antonelli": "#00D2BE",
    "Charles Leclerc": "#DC0000", "Lewis Hamilton": "#DC0000",
    "Lando Norris": "#FF8700", "Oscar Piastri": "#FF8700",
    "Fernando Alonso": "#006F62", "Lance Stroll": "#006F62",
    "Alexander Albon": "#005AFF", "Carlos Sainz": "#005AFF",
    "Pierre Gasly": "#0090FF", "Jack Doohan": "#0090FF",
    "Liam Lawson": "#2B4562", "Isack Hadjar": "#2B4562",
    "Esteban Ocon": "#FFFFFF", "Oliver Bearman": "#FFFFFF",
    "Nico Hülkenberg": "#900000", "Gabriel Bortoletto": "#900000"
}

def get_sprint_points(round_num):
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
    standings = {driver: [0] * len(RACE_LOCATIONS) for driver in TEAM_COLORS}
    total_points = {driver: 0 for driver in TEAM_COLORS}

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        url = f"{BASE_URL}{round_num}/results.json"
        response = requests.get(url)
        if response.status_code != 200:
            continue

        races = response.json()['MRData']['RaceTable']['Races']
        sprint_points = get_sprint_points(round_num)
        current_points = {d: 0 for d in standings}

        if races:
            for result in races[0]['Results']:
                driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                if driver not in standings:
                    standings[driver] = [0] * len(RACE_LOCATIONS)
                    total_points[driver] = 0
                    TEAM_COLORS[driver] = "#000000"
                current_points[driver] = int(float(result['points'])) + sprint_points.get(driver, 0)

        for driver in standings:
            total_points[driver] += current_points.get(driver, 0)
            standings[driver][round_num - 1] = total_points[driver]

    return standings

def write_driver_chart_json(standings):
    chart_data = {
        "labels": RACE_LOCATIONS,
        "series": []
    }

    for driver, points in standings.items():
        chart_data["series"].append({
            "title": driver,
            "data": points,
            "color": TEAM_COLORS.get(driver, "#000000")
        })

    with open("driver_chart.json", "w", encoding="utf-8") as f:
        json.dump(chart_data, f, ensure_ascii=False, indent=2)

def main():
    print("🔄 Lade Fahrerpunkte...")
    standings = get_cumulative_points()
    write_driver_chart_json(standings)
    print("✅ JSON für Diagramm erzeugt: driver_chart.json")

if __name__ == "__main__":
    main()