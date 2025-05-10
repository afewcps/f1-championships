import streamlit as st
import requests
import json
import time
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import defaultdict

NOTION_TOKEN = "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"
PUNKTESTAENDE_DATABASE_ID = "1e46839379ed80369b0ddac32dcd5abd"
TEAMS_DATABASE_ID = "1e46839379ed8014aee4dc3f97d70707"
RENNWOCHENENDEN_DATABASE_ID = "1e46839379ed80519d70c7f9df920fe4"

retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "POST", "PATCH"])
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami",
    "Emilia-Romagna", "Monaco", "Spain", "Canada", "Austria", "Great Britain",
    "Belgium", "Hungary", "Netherlands", "Italy", "Azerbaijan", "Singapore",
    "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

def get_cumulative_team_points(race_locations):
    cumulative_points = defaultdict(float)
    team_points_by_race = defaultdict(lambda: [0.0] * len(race_locations))
    all_teams = set()

    # Sprint-Daten einmalig laden
    sprint_data = {}
    try:
        url_sprint = "https://api.jolpi.ca/ergast/f1/current/sprint.json"
        res_sprint = session.get(url_sprint, timeout=20)
        if res_sprint.status_code == 200:
            data_sprint = res_sprint.json()
            races = data_sprint.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            for race in races:
                name = race.get("raceName")
                sprint_data[name] = race.get("SprintResults", [])
    except Exception as e:
        st.error(f"Fehler beim Laden der Sprintdaten: {e}")

    for idx, race in enumerate(race_locations):
        total_points = defaultdict(float)
        try:
            url_gp = f"https://api.jolpi.ca/ergast/f1/current/{idx+1}/results.json"
            res_gp = session.get(url_gp, timeout=20)
            if res_gp.status_code == 200:
                data_gp = res_gp.json()
                race_entry = data_gp.get("MRData", {}).get("RaceTable", {}).get("Races", [{}])[0]
                results = race_entry.get("Results", [])
                race_name = race_entry.get("raceName", race)

                for entry in results:
                    team = entry["Constructor"]["name"]
                    points = float(entry.get("points", 0))
                    total_points[team] += points
                    all_teams.add(team)

                # Sprintpunkte ergänzen
                if race_name in sprint_data:
                    for entry in sprint_data[race_name]:
                        team = entry["Constructor"]["name"]
                        points = float(entry.get("points", 0))
                        total_points[team] += points
                        all_teams.add(team)

            if not total_points:
                for team in cumulative_points:
                    team_points_by_race[team][idx] = cumulative_points[team]
                continue

            for team in all_teams:
                cumulative_points[team] += total_points.get(team, 0)
                team_points_by_race[team][idx] = cumulative_points[team]

        except Exception as e:
            st.error(f"❌ Fehler bei Rennen {race}: {e}")
            for team in cumulative_points:
                team_points_by_race[team][idx] = cumulative_points[team]

    return team_points_by_race

def find_team_id(team_name):
    url = f"https://api.notion.com/v1/databases/{TEAMS_DATABASE_ID}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": team_name}}}
    try:
        response = session.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                return results[0]["id"]
    except Exception as e:
        st.error(f"⚠️ Fehler bei Anfrage für Team {team_name}: {e}")
    return None

def find_race_id(race_name):
    url = f"https://api.notion.com/v1/databases/{RENNWOCHENENDEN_DATABASE_ID}/query"
    payload = {"filter": {"property": "Name", "title": {"equals": race_name}}}
    try:
        time.sleep(random.uniform(0.5, 1.5))
        response = session.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                return results[0]["id"]
    except Exception as e:
        st.error(f"⚠️ Fehler bei Anfrage für Rennen {race_name}: {e}")
    return None

def get_existing_entries():
    existing_entries = {}
    start_cursor = None
    has_more = True
    while has_more:
        url = f"https://api.notion.com/v1/databases/{PUNKTESTAENDE_DATABASE_ID}/query"
        payload = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor
        response = session.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            break
        data = response.json()
        for result in data.get("results", []):
            entry_id = result["id"]
            team_rel = result["properties"]["Team"]["relation"]
            race_rel = result["properties"]["Rennwochenende"]["relation"]
            if team_rel and race_rel:
                key = f"{team_rel[0]['id']}:{race_rel[0]['id']}"
                existing_entries[key] = entry_id
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return existing_entries

def update_or_create_entry(entry_id, team_id, race_id, team_name, race_name, punkte):
    if entry_id:
        url = f"https://api.notion.com/v1/pages/{entry_id}"
        method = session.patch
    else:
        url = "https://api.notion.com/v1/pages"
        method = session.post

    payload = {
        "parent": {"database_id": PUNKTESTAENDE_DATABASE_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": f"{team_name} - {race_name}"}}]},
            "Team": {"relation": [{"id": team_id}]},
            "Rennwochenende": {"relation": [{"id": race_id}]},
            "Kumulative Punkte": {"number": punkte}
        }
    }
    if entry_id:
        del payload["parent"]
    response = method(url, headers=headers, json=payload, timeout=30)
    if response.status_code in [200, 201]:
        st.success(f"✅ {team_name} @ {race_name}: {punkte} Punkte")
    else:
        st.error(f"❌ Fehler ({response.status_code}) für {team_name} @ {race_name}")

def run_sync():
    st.info("🔄 Berechne Jolpica-Punktestände...")
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
            update_or_create_entry(entry_id, team_id, race_id, team, race, points[i])

# Streamlit UI
st.title("F1 Notion Sync")
if st.button("🔄 Punkte mit Notion synchronisieren"):
    run_sync()
