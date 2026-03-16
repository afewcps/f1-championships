import requests
import json
import time
import random
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import defaultdict

# =========================
# CONFIG
# =========================

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Fehler: NOTION_TOKEN environment variable ist nicht gesetzt!")
    exit(1)

PUNKTESTAENDE_DATABASE_ID = "1e46839379ed80369b0ddac32dcd5abd"
TEAMS_DATABASE_ID = "1e46839379ed8014aee4dc3f97d70707"
RENNWOCHENENDEN_DATABASE_ID = "1e46839379ed80519d70c7f9df920fe4"

RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Emilia-Romagna", "Monaco", "Spain", "Canada", "Austria", "Great Britain",
    "Belgium", "Hungary", "Netherlands", "Italy", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# =========================
# SESSION SETUP
# =========================

retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST", "PATCH"]
)

session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# =========================
# CORE LOGIC (FIXED)
# =========================

def get_cumulative_team_points(race_locations):
    print("📊 Berechne kumulative Team-Punkte (FIXED)...")

    cumulative_points = defaultdict(float)
    team_points_by_race = defaultdict(lambda: [0.0] * len(race_locations))
    all_teams = set()

    for idx, race in enumerate(race_locations):
        round_number = idx + 1
        total_points = defaultdict(float)

        try:
            # -------------------------
            # GP RESULTS
            # -------------------------
            url_gp = f"https://api.jolpi.ca/ergast/f1/current/{round_number}/results.json"
            res_gp = session.get(url_gp, timeout=20)
            if res_gp.status_code != 200:
                raise Exception(f"GP request failed ({res_gp.status_code})")

            data_gp = res_gp.json()
            race_entry = data_gp.get("MRData", {}).get("RaceTable", {}).get("Races", [{}])[0]
            race_name = race_entry.get("raceName", race)

            for entry in race_entry.get("Results", []):
                team = entry["Constructor"]["name"]
                points = float(entry.get("points", 0))
                total_points[team] += points
                all_teams.add(team)

            # -------------------------
            # SPRINT RESULTS (ROUND-BASED)
            # -------------------------
            url_sprint = f"https://api.jolpi.ca/ergast/f1/current/{round_number}/sprint.json"
            res_sprint = session.get(url_sprint, timeout=20)

            if res_sprint.status_code == 200:
                data_sprint = res_sprint.json()
                sprint_races = data_sprint.get("MRData", {}).get("RaceTable", {}).get("Races", [])

                if sprint_races:
                    sprint_results = sprint_races[0].get("SprintResults", [])
                    for entry in sprint_results:
                        team = entry["Constructor"]["name"]
                        points = float(entry.get("points", 0))
                        total_points[team] += points
                        all_teams.add(team)

            # -------------------------
            # APPLY CUMULATIVE
            # -------------------------
            for team in all_teams:
                cumulative_points[team] += total_points.get(team, 0)
                team_points_by_race[team][idx] = cumulative_points[team]

            print(f"📈 {race_name}: {len(total_points)} Teams, Round {round_number}")

        except Exception as e:
            print(f"❌ Fehler bei Rennen {race} (Round {round_number}): {e}")
            for team in cumulative_points:
                team_points_by_race[team][idx] = cumulative_points[team]

        time.sleep(0.2)

    print(f"✅ Punkteberechnung abgeschlossen für {len(all_teams)} Teams")
    return team_points_by_race

# =========================
# NOTION HELPERS (UNVERÄNDERT)
# =========================

def find_team_id(team_name):
    url = f"https://api.notion.com/v1/databases/{TEAMS_DATABASE_ID}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": team_name}}}
    response = session.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]["id"]
    return None

def find_race_id(race_name):
    url = f"https://api.notion.com/v1/databases/{RENNWOCHENENDEN_DATABASE_ID}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": race_name}}}
    time.sleep(random.uniform(0.5, 1.5))
    response = session.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code == 200:
        results = response.json().get("results", [])
        if results:
            return results[0]["id"]
    return None

def get_existing_entries():
    existing_entries = {}
    start_cursor = None
    has_more = True

    while has_more:
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = session.post(
            f"https://api.notion.com/v1/databases/{PUNKTESTAENDE_DATABASE_ID}/query",
            headers=headers,
            json=payload,
            timeout=30
        )

        data = response.json()
        for result in data.get("results", []):
            team_rel = result["properties"]["Team"]["relation"]
            race_rel = result["properties"]["Rennwochenende"]["relation"]
            if team_rel and race_rel:
                key = f"{team_rel[0]['id']}:{race_rel[0]['id']}"
                existing_entries[key] = result["id"]

        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return existing_entries

def update_or_create_entry(entry_id, team_id, race_id, team_name, race_name, punkte):
    if entry_id:
        url = f"https://api.notion.com/v1/pages/{entry_id}"
        method = session.patch
        payload_parent = False
    else:
        url = "https://api.notion.com/v1/pages"
        method = session.post
        payload_parent = True

    payload = {
        "parent": {"database_id": PUNKTESTAENDE_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": f"{team_name} - {race_name}"}}]},
            "Team": {"relation": [{"id": team_id}]},
            "Rennwochenende": {"relation": [{"id": race_id}]},
            "Kumulative Punkte": {"number": punkte}
        }
    }

    if not payload_parent:
        del payload["parent"]

    response = method(url, headers=headers, json=payload, timeout=30)
    return response.status_code in [200, 201]

# =========================
# MAIN
# =========================

def run_sync():
    print("🔄 Starte F1 Notion Sync (FIXED)...")

    team_points = get_cumulative_team_points(RACE_LOCATIONS)
    existing_entries = get_existing_entries()

    team_ids = {team: find_team_id(team) for team in team_points}
    race_ids = {race: find_race_id(race) for race in RACE_LOCATIONS}

    for team, points in team_points.items():
        team_id = team_ids.get(team)
        if not team_id:
            continue

        for i, race in enumerate(RACE_LOCATIONS):
            race_id = race_ids.get(race)
            if not race_id:
                continue

            key = f"{team_id}:{race_id}"
            entry_id = existing_entries.get(key)

            update_or_create_entry(
                entry_id,
                team_id,
                race_id,
                team,
                race,
                points[i]
            )

            time.sleep(0.1)

    print("✅ F1 Notion Sync abgeschlossen")

def main():
    run_sync()

if __name__ == "__main__":
    main()
