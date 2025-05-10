import streamlit as st
import requests
import json
import os
from notion_client import Client

# Streamlit app title and description
st.title("F1 Drivers Championship Notion Updater")
st.write("This app updates the Formula 1 Drivers Championship data in a Notion database.")

# Notion API Setup
NOTION_TOKEN = "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"
DATABASE_NAME = "Drivers Championship"

# Liste der Rennorte für die Saison 2025 in englischer Sprache und korrekter Reihenfolge
RACE_LOCATIONS = [
    "Australia", "China", "Japan", "Bahrain", "Saudi Arabia", "Miami", "Emilia-Romagna", "Monaco",
    "Spain", "Canada", "Austria", "Great Britain", "Belgium", "Hungary", "Netherlands",
    "Italy", "Azerbaijan", "Singapore", "United States", "Mexico", "Brazil", "Las Vegas", "Qatar", "Abu Dhabi"
]

# Jolpica-API-Link
BASE_URL = "http://api.jolpi.ca/ergast/f1/current/"

# Team Colors Dictionary
TEAM_COLORS = {
    # Red Bull Racing
    "Max Verstappen": "#0600EF",  # Deep Blue
    "Yuki Tsunoda": "#0600EF",    # Deep Blue
    
    # Mercedes
    "George Russell": "#00D2BE",  # Turquoise
    "Andrea Kimi Antonelli": "#00D2BE",  # Turquoise
    
    # Ferrari
    "Charles Leclerc": "#DC0000",  # Ferrari Red
    "Lewis Hamilton": "#DC0000",     # Ferrari Red
    
    # McLaren
    "Lando Norris": "#FF8700",    # Orange
    "Oscar Piastri": "#FF8700",   # Orange
    
    # Aston Martin
    "Fernando Alonso": "#006F62",  # Racing Green
    "Lance Stroll": "#006F62",     # Racing Green
    
    # Williams
    "Alexander Albon": "#005AFF",  # Williams Blue
    "Carlos Sainz": "#005AFF",   # Williams Blue
    
    # Alpine
    "Pierre Gasly": "#0090FF",    # Alpine Blue
    "Jack Doohan": "#0090FF",    # Alpine Blue
    
    # AlphaTauri (now Visa Cash App RB)
    "Liam Lawson": "#2B4562",  # Dark Blue
    "Isack Hadjar": "#2B4562",      # Dark Blue
    
    # Haas
    "Esteban Ocon": "#FFFFFF",  # White
    "Oliver Bearman": "#FFFFFF",  # White
    
    # Kick Sauber (formerly Alfa Romeo)
    "Nico Hülkenberg": "#900000",  # Dark Red
    "Gabriel Bortoletto": "#900000",      # Dark Red
}

def get_sprint_points(round_num):
    """Holt die Sprint-Punkte eines Rennwochenendes."""
    url = f"{BASE_URL}{round_num}/sprint.json"
    response = requests.get(url)
    sprint_points = {}
    
    if response.status_code == 200:
        data = response.json()
        races = data['MRData']['RaceTable']['Races']
        if races:
            race = races[0]
            for result in race['SprintResults']:
                driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                points = float(result['points'])
                sprint_points[driver] = int(points)
    return sprint_points

def get_weekend_points():
    """Berechnet die Punkte für jedes Wochenende separat."""
    weekend_points = {}

    for round_num in range(1, len(RACE_LOCATIONS) + 1):
        url = f"{BASE_URL}{round_num}/results.json"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            races = data['MRData']['RaceTable']['Races']
            
            # Sprint-Punkte abrufen
            sprint_points = get_sprint_points(round_num)

            # Hole Punkte aus dem aktuellen Rennen, falls Daten vorhanden
            if races:
                for result in races[0]['Results']:
                    driver = f"{result['Driver']['givenName']} {result['Driver']['familyName']}"
                    points = float(result['points']) + sprint_points.get(driver, 0)
                    
                    if driver not in weekend_points:
                        weekend_points[driver] = [0] * len(RACE_LOCATIONS)
                    
                    if weekend_points[driver][round_num - 1] == 0:
                        weekend_points[driver][round_num - 1] = int(points)

    return weekend_points

def calculate_total_points(weekend_points):
    """Berechnet die echten Gesamtpunkte durch Aufsummieren der Wochenendpunkte."""
    total_points = {}
    
    for driver, points_list in weekend_points.items():
        total_points[driver] = sum(points_list)
    
    return total_points

def get_cumulative_points():
    """Lädt die Fahrerwertung aus der API mit kumulativen Punkten."""
    # Initialize standings with all known drivers
    standings = {team: [0] * len(RACE_LOCATIONS) for team in TEAM_COLORS.keys()}
    
    # Holen wir die Wochenendpunkte und summieren sie korrekt
    weekend_points = get_weekend_points()
    
    # Aktualisiere für jeden Fahrer die kumulativen Punktestände
    for driver, points_list in weekend_points.items():
        if driver not in standings:
            standings[driver] = [0] * len(RACE_LOCATIONS)
        
        # Berechne den kumulativen Punktestand für jeden GP
        cumulative = 0
        for i, points in enumerate(points_list):
            cumulative += points
            standings[driver][i] = cumulative
    
    # Berechne die korrekten Gesamtpunkte
    total_points = calculate_total_points(weekend_points)
    
    return standings, total_points

def create_notion_database(weekend_points, total_points):
    """Erstellt oder aktualisiert die Notion-Datenbank mit den F1-Fahrerwertungen"""
    notion = Client(auth=NOTION_TOKEN)
    
    # Sortiere Fahrer nach Gesamtpunkten (absteigend)
    sorted_drivers = sorted(
        [driver for driver in weekend_points.keys() if driver in total_points], 
        key=lambda x: total_points[x], 
        reverse=True
    )
    
    # Prüfe, ob die Datenbank bereits existiert
    existing_db = None
    parent_page_id = get_or_create_parent_page(notion)
    results = notion.search(query=DATABASE_NAME).get("results", [])
    for result in results:
        if result["object"] == "database" and result["title"][0]["plain_text"] == DATABASE_NAME:
            existing_db = result["id"]
            break
    
    # Erstelle die Datenbank-Eigenschaften
    properties = {
        "Driver": {"title": {}},
        "Total": {"number": {}}
    }
    
    # Füge für jeden Rennort eine Spalte hinzu
    for location in RACE_LOCATIONS:
        properties[location] = {"number": {}}
    
    # Wenn die Datenbank nicht existiert, erstelle sie
    if not existing_db:
        
        response = notion.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": DATABASE_NAME}}],
            properties=properties
        )
        database_id = response["id"]
    else:
        database_id = existing_db
        # Aktualisiere die Datenbank-Eigenschaften
        notion.databases.update(database_id=database_id, properties=properties)
        
        # Lösche alle existierenden Einträge
        existing_entries = notion.databases.query(database_id=database_id).get("results", [])
        for entry in existing_entries:
            notion.pages.update(page_id=entry["id"], archived=True)
    
    # Füge die Fahrer hinzu
    for driver in sorted_drivers:
        driver_properties = {
            "Driver": {"title": [{"text": {"content": driver}}]},
            "Total": {"number": total_points[driver]}
        }
        
        # Füge Punkte für jedes Rennen hinzu
        points = weekend_points.get(driver, [0] * len(RACE_LOCATIONS))
        for i, location in enumerate(RACE_LOCATIONS):
            driver_properties[location] = {"number": points[i] if points[i] > 0 else None}
        
        # Erstelle den Eintrag
        notion.pages.create(
            parent={"database_id": database_id},
            properties=driver_properties
        )
    
    return database_id

def get_or_create_parent_page(notion):
    """Gibt die fest definierte Parent-Page-ID zurück"""
    return "1e26839379ed80edbd00df2aaf120777"

def update_f1_data():
    """Hauptfunktion zum Aktualisieren der F1-Daten"""
    with st.spinner("🔄 Aktualisiere die Fahrer-Meisterschaft in Notion..."):
        weekend_points = get_weekend_points()
        total_points = calculate_total_points(weekend_points)
        database_id = create_notion_database(weekend_points, total_points)
        st.success(f"✅ Fertig! Die Fahrer-Meisterschaft wurde in Notion aktualisiert (Database ID: {database_id}).")
        
        # Show some data in Streamlit
        st.subheader("Aktualisierte Fahrerwertung:")
        
        # Create a DataFrame for display
        import pandas as pd
        driver_data = []
        
        sorted_drivers = sorted(
            [driver for driver in weekend_points.keys() if driver in total_points], 
            key=lambda x: total_points[x], 
            reverse=True
        )
        
        for driver in sorted_drivers:
            driver_data.append({
                "Fahrer": driver,
                "Gesamtpunkte": total_points[driver]
            })
        
        if driver_data:
            df = pd.DataFrame(driver_data)
            st.dataframe(df)

# Create an update button
if st.button("Fahrerwertung aktualisieren"):
    update_f1_data()
