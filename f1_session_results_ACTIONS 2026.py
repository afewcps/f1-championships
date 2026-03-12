import fastf1
import pandas as pd
import requests
import json
import traceback
import os
from datetime import datetime

# =============================================================================
# F1 Session Results → Notion (Long Format) für GitHub Actions
# Saison 2026 – schreibt in zentrale "Session Results (Long Format)" Datenbank
# =============================================================================

# ─────────────────────────────────────────────
# KONFIGURATION – diese IDs musst du ersetzen!
# ─────────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Fehler: NOTION_TOKEN environment variable ist nicht gesetzt!")
    exit(1)

# ID der zentralen "📊 Session Results (Long Format)" Datenbank
# → Öffne die DB in Notion, kopiere die ID aus der URL
RESULTS_DB_ID = "4c7a3557b9174b0d9cb21f7d9aff25d2"  # ← aus URL: notion.so/DIESE-ID

# ID der "👤 Drivers 2026" Datenbank (enthält alle Fahrer-Objekte)
DRIVERS_DB_ID = "3166839379ed8077ac10d568e95178c0"  # Drivers 2026

# ID der "Weekends" Datenbank (enthält alle GP-Wochenenden)
WEEKENDS_DB_ID = "3166839379ed8135b474d348837083bb"

# ID der "👥 Constructors Championship 2026" (Session Results → Team zeigt hierauf)
CONSTRUCTORS_DB_ID = "3166839379ed81a18ff9c93850213783"

# ─────────────────────────────────────────────
# FastF1 Cache
# ─────────────────────────────────────────────
fastf1.Cache.enable_cache("./fastf1_cache/")

# ─────────────────────────────────────────────
# Notion API Headers
# ─────────────────────────────────────────────
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# ─────────────────────────────────────────────
# 2026 F1 Kalender
# Sprint-Wochenenden sind mit sprint=True markiert
# WICHTIG: Datumsangaben bitte vor der Saison gegen den offiziellen
# FIA-Kalender verifizieren – hier steht das jeweilige Renndatum (Sonntag)
# ─────────────────────────────────────────────
F1_2026_CALENDAR = [
    {"name": "Australian Grand Prix",    "date": "2026-03-08", "sprint": False},
    {"name": "Chinese Grand Prix",       "date": "2026-03-15", "sprint": True},
    {"name": "Japanese Grand Prix",      "date": "2026-03-29", "sprint": False},
    {"name": "Bahrain Grand Prix",       "date": "2026-04-12", "sprint": False},
    {"name": "Saudi Arabian Grand Prix", "date": "2026-04-19", "sprint": False},
    {"name": "Miami Grand Prix",         "date": "2026-05-03", "sprint": True},
    {"name": "Canadian Grand Prix",      "date": "2026-05-25", "sprint": True},
    {"name": "Monaco Grand Prix",        "date": "2026-06-07", "sprint": False},
    {"name": "Barcelona-Catalunya Grand Prix",       "date": "2026-06-14", "sprint": False},
    {"name": "Austrian Grand Prix",      "date": "2026-06-28", "sprint": False},
    {"name": "British Grand Prix",       "date": "2026-07-05", "sprint": True},
    {"name": "Belgian Grand Prix",       "date": "2026-07-19", "sprint": False},
    {"name": "Hungarian Grand Prix",     "date": "2026-07-26", "sprint": False},
    {"name": "Dutch Grand Prix",         "date": "2026-08-23", "sprint": True},
    {"name": "Italian Grand Prix",       "date": "2026-09-06", "sprint": False},
    {"name": "Spanish Grand Prix",       "date": "2026-09-13", "sprint": False},
    {"name": "Azerbaijan Grand Prix",    "date": "2026-09-26", "sprint": False},
    {"name": "Singapore Grand Prix",     "date": "2026-10-11", "sprint": True},
    {"name": "United States Grand Prix", "date": "2026-10-25", "sprint": False},
    {"name": "Mexican Grand Prix",       "date": "2026-11-01", "sprint": False},
    {"name": "Brazilian Grand Prix",     "date": "2026-11-08", "sprint": False},
    {"name": "Las Vegas Grand Prix",     "date": "2026-11-21", "sprint": False},
    {"name": "Qatar Grand Prix",         "date": "2026-11-29", "sprint": False},
    {"name": "Abu Dhabi Grand Prix",     "date": "2026-12-06", "sprint": False},
  
]

# Länderkürzel für das Eintrag-Muster (z.B. "AUS Race – NOR")
GP_COUNTRY_CODE = {
    "Australian Grand Prix":         "AUS",
    "Chinese Grand Prix":            "CHN",
    "Japanese Grand Prix":           "JPN",
    "Bahrain Grand Prix":            "BHR",
    "Saudi Arabian Grand Prix":      "SAU",
    "Miami Grand Prix":              "MIA",
    "Canadian Grand Prix":           "CAN",
    "Monaco Grand Prix":             "MON",
    "Barcelona-Catalunya Grand Prix":"BAR",
    "Austrian Grand Prix":           "AUT",
    "British Grand Prix":            "GBR",
    "Belgian Grand Prix":            "BEL",
    "Hungarian Grand Prix":          "HUN",
    "Dutch Grand Prix":              "NED",
    "Italian Grand Prix":            "ITA",
    "Spanish Grand Prix":            "ESP",
    "Azerbaijan Grand Prix":         "AZE",
    "Singapore Grand Prix":          "SGP",
    "United States Grand Prix":      "USA",
    "Mexican Grand Prix":            "MEX",
    "Brazilian Grand Prix":          "BRA",
    "Las Vegas Grand Prix":          "LVG",
    "Qatar Grand Prix":              "QAT",
    "Abu Dhabi Grand Prix":          "UAE",
}

# Mapping FastF1-Name → Name in der Weekends-Datenbank
# FastF1 nutzt "Australian Grand Prix", die Weekends-DB speichert nur "Australia" etc.
# Ausnahmen: Miami, Barcelona, Las Vegas, Abu Dhabi (Stadtname statt Land)
GP_WEEKEND_NAME = {
    "Australian Grand Prix":         "Australia",
    "Chinese Grand Prix":            "China",
    "Japanese Grand Prix":           "Japan",
    "Bahrain Grand Prix":            "Bahrain",
    "Saudi Arabian Grand Prix":      "Saudi Arabia",
    "Miami Grand Prix":              "Miami",
    "Canadian Grand Prix":           "Canada",
    "Monaco Grand Prix":             "Monaco",
    "Barcelona-Catalunya Grand Prix":"Barcelona",
    "Austrian Grand Prix":           "Austria",
    "British Grand Prix":            "Great Britain",
    "Belgian Grand Prix":            "Belgium",
    "Hungarian Grand Prix":          "Hungary",
    "Dutch Grand Prix":              "Netherlands",
    "Italian Grand Prix":            "Italy",
    "Spanish Grand Prix":            "Spain",
    "Azerbaijan Grand Prix":         "Azerbaijan",
    "Singapore Grand Prix":          "Singapore",
    "United States Grand Prix":      "United States",
    "Mexican Grand Prix":            "Mexico",
    "Brazilian Grand Prix":          "Brazil",
    "Las Vegas Grand Prix":          "Las Vegas",
    "Qatar Grand Prix":              "Qatar",
    "Abu Dhabi Grand Prix":          "Abu Dhabi",
}

# Kurzname des Session-Typs für den Eintrag-Titel
SESSION_SHORT_NAME = {
    "Race":              "Race",
    "Qualifying":        "Qualifying",
    "Sprint":            "Sprint",
    "Sprint Qualifying": "SQ",
    "Practice 1":        "FP1",
    "Practice 2":        "FP2",
    "Practice 3":        "FP3",
}

# Session-Typ wie er in der Notion Select-Property steht
SESSION_NOTION_TYPE = {
    "Race":              "Race",
    "Qualifying":        "Qualifying",
    "Sprint":            "Sprint",
    "Sprint Qualifying": "Sprint Qualifying",
    "Practice 1":        "FP1",
    "Practice 2":        "FP2",
    "Practice 3":        "FP3",
}

# 2026 F1 Punktesystem
# KEIN Bonus-Punkt für schnellste Runde ab 2026!
RACE_POINTS = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10,
               6: 8,  7: 6,  8: 4,  9: 2,  10: 1}
SPRINT_POINTS = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4,
                 6: 3, 7: 2, 8: 1}

# Session-Typen pro Wochenendformat
NORMAL_SESSIONS = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]
SPRINT_SESSIONS = ["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"]

# FastF1 session identifier
FASTF1_SESSION_ID = {
    "Practice 1":        "FP1",
    "Practice 2":        "FP2",
    "Practice 3":        "FP3",
    "Qualifying":        "Q",
    "Sprint Qualifying": "SQ",
    "Sprint":            "S",
    "Race":              "R",
}


# =============================================================================
# NOTION HILFSFUNKTIONEN
# =============================================================================

def notion_get(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()

def notion_post(url, payload):
    r = requests.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()

def notion_patch(url, payload):
    r = requests.patch(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


def load_all_pages_from_db(db_id):
    """Lädt alle Seiten aus einer Notion-Datenbank (paginiert)."""
    pages = []
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        result = notion_post(f"https://api.notion.com/v1/databases/{db_id}/query", payload)
        pages.extend(result.get("results", []))
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")
    return pages


def build_driver_map(drivers_db_id):
    """
    Erstellt ein Dict: Fahrerkürzel → {"driver_id": page_id, "team_name": str|None}
    team_name wird später gegen constructors_map aufgelöst um die korrekte
    Constructors Championship 2026 Page-ID zu ermitteln.
    """
    print("📋 Lade Fahrer-Datenbank...")
    pages = load_all_pages_from_db(drivers_db_id)
    driver_map = {}
    for page in pages:
        props = page.get("properties", {})

        # Kürzel aus der "Abbreviation"-Property (Rich Text)
        abbr_list = props.get("Abbreviation", {}).get("rich_text", [])
        abbr = abbr_list[0]["text"]["content"].strip() if abbr_list else ""

        # Name aus der Title-Property
        name_list = props.get("Name", {}).get("title", [])
        name = name_list[0]["text"]["content"].strip() if name_list else ""

        # Team-Relation zeigt auf die separate Teams-DB (nicht Constructors Championship).
        # Wir speichern die Teams-DB Page-ID hier NICHT – stattdessen wird der
        # Teamname über build_teams_name_map() aufgelöst und dann gegen
        # constructors_map gematcht. Die Teams-DB hat eine "Name"-Title-Property.
        team_relations = props.get("Team", {}).get("relation", [])
        teams_db_page_id = team_relations[0]["id"] if team_relations else None

        # Startnummer (für Sortierung no-time-Fahrer im Qualifying)
        car_number_raw = props.get("Number", {}).get("number", None)
        car_number = int(car_number_raw) if car_number_raw is not None else 99

        if abbr:
            driver_map[abbr] = {
                "driver_id":      page["id"],
                "teams_db_id":    teams_db_page_id,
                "number":         car_number,
            }
            print(f"   ✔ {abbr} → {name} (#{car_number})")

    print(f"✅ {len(driver_map)} Fahrer geladen")
    return driver_map


def build_teams_name_map(teams_db_page_ids):
    """
    Lädt Teamnamen aus der Teams-DB für eine Liste von Page-IDs.
    Gibt Dict zurück: teams_db_page_id → team_name (z.B. "McLaren")
    """
    teams_name_map = {}
    for page_id in teams_db_page_ids:
        if not page_id:
            continue
        try:
            r = requests.get(
                f"https://api.notion.com/v1/pages/{page_id}",
                headers=HEADERS
            )
            r.raise_for_status()
            page = r.json()
            props = page.get("properties", {})
            # Title-Property der Teams-DB heißt "Name"
            name_list = props.get("Name", {}).get("title", [])
            name = name_list[0]["text"]["content"].strip() if name_list else ""
            if name:
                teams_name_map[page_id] = name
        except Exception as e:
            print(f"   ⚠️ Konnte Team-Namen für {page_id} nicht laden: {e}")
    return teams_name_map


def build_constructors_map(constructors_db_id):
    """
    Erstellt ein Dict: Konstrukteurs-Name → Notion Page ID
    aus der Constructors Championship 2026 Datenbank.
    Die Title-Property heißt dort "Constructor".
    """
    print("📋 Lade Constructors Championship 2026 Datenbank...")
    pages = load_all_pages_from_db(constructors_db_id)
    constructors_map = {}
    for page in pages:
        props = page.get("properties", {})
        name_list = props.get("Constructor", {}).get("title", [])
        name = name_list[0]["text"]["content"].strip() if name_list else ""
        if name:
            constructors_map[name] = page["id"]
            print(f"   ✔ {name} ({page['id']})")
    print(f"✅ {len(constructors_map)} Konstrukteure geladen")
    return constructors_map


def build_weekend_map(weekends_db_id):
    """
    Erstellt ein Dict: GP-Name (z.B. 'Australian Grand Prix') → Notion Page ID
    """
    print("📋 Lade Weekends-Datenbank...")
    pages = load_all_pages_from_db(weekends_db_id)
    weekend_map = {}
    for page in pages:
        props = page.get("properties", {})
        name_list = props.get("Name", {}).get("title", [])
        name = name_list[0]["text"]["content"].strip() if name_list else ""
        if name:
            weekend_map[name] = page["id"]
            print(f"   ✔ {name} ({page['id']})")
    print(f"✅ {len(weekend_map)} Wochenenden geladen")
    return weekend_map


def load_existing_entries_for_weekend(results_db_id, weekend_page_id):
    """
    Lädt ALLE existierenden Einträge für ein Weekend in einer einzigen
    paginierten Abfrage. Gibt Dict zurück: eintrag_title → page_id.
    Ersetzt die alte find_existing_entry()-Einzelabfrage pro Fahrer.
    """
    print("   📋 Lade existierende Einträge für dieses Weekend (Cache)...")
    payload = {
        "filter": {
            "property": "Weekend",
            "relation": {"contains": weekend_page_id}
        },
        "page_size": 100
    }
    pages = []
    cursor = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        result = notion_post(
            f"https://api.notion.com/v1/databases/{results_db_id}/query", payload
        )
        pages.extend(result.get("results", []))
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")
        payload.pop("start_cursor", None)

    cache = {}
    for page in pages:
        title_list = page.get("properties", {}).get("Entry", {}).get("title", [])
        title = title_list[0]["text"]["content"] if title_list else ""
        if title:
            cache[title] = page["id"]

    print(f"   ✅ {len(cache)} existierende Einträge gecacht")
    return cache


# =============================================================================
# FASTF1 DATEN ABRUFEN
# =============================================================================

def get_qualifying_positions(year, gp_name):
    """
    Gibt ein Dict zurück: Fahrerkürzel → Grid-Position (aus dem Qualifying).
    Wird verwendet um Grid Position beim Race-Eintrag zu setzen.
    """
    print("   📡 Lade Qualifying-Positionen für Grid Position...")
    try:
        session = fastf1.get_session(year, gp_name, "Q")
        session.load(telemetry=False, weather=False, messages=False)
        quali_map = {}
        for _, row in session.results.iterrows():
            abbr = row.get("Abbreviation", "")
            pos  = row.get("Position", None)
            if abbr and pos and not pd.isna(pos):
                quali_map[abbr] = int(pos)
        print(f"   ✅ {len(quali_map)} Qualifying-Positionen geladen")
        return quali_map
    except Exception as e:
        print(f"   ⚠️ Qualifying-Positionen konnten nicht geladen werden: {e}")
        return {}


def get_session_results(year, gp_name, session_display_name):
    """
    Lädt FastF1-Daten für eine Session und gibt eine Liste von Dicts zurück.
    Jedes Dict representiert einen Fahrer:
    {
        "abbreviation": "NOR",
        "full_name":    "Lando Norris",    # nur als Fallback/Logging
        "position":     1,
        "dnf":          False,
        "fastest_lap":  True,
        "points":       25,                # 0 für nicht-Rennen-Sessions
        "grid_pos":     None,              # wird für Race extern gesetzt
    }
    """
    ff1_id = FASTF1_SESSION_ID.get(session_display_name)
    if not ff1_id:
        print(f"   ⚠️ Unbekannter Session-Typ: {session_display_name}")
        return None

    print(f"   📡 Lade FastF1: {gp_name} {year} – {session_display_name}...")

    try:
        session = fastf1.get_session(year, gp_name, ff1_id)
    except ValueError as e:
        print(f"   ⚠️ Session existiert nicht: {e}")
        return None

    try:
        session.load(telemetry=False, weather=False, messages=False)
    except Exception as e:
        print(f"   ⚠️ Konnte Session nicht laden: {e}")
        return None

    # ── Prüfen ob Session bereits stattgefunden hat ────────────────────────
    # session.date kann tz-aware oder tz-naive sein – wir normalisieren auf UTC.
    try:
        session_date = pd.Timestamp(session.date)
        if session_date.tzinfo is not None:
            session_date_utc = session_date.tz_convert("UTC")
        else:
            session_date_utc = session_date.tz_localize("UTC")
        now_utc = pd.Timestamp.now(tz="UTC")
        if session_date_utc > now_utc:
            print(f"   ⏳ Session liegt in der Zukunft ({session_date.date()}) → übersprungen")
            return None
    except Exception as e:
        print(f"   ⚠️ Konnte Session-Datum nicht prüfen: {e} – fahre fort")

    # Für Qualifying/Sprint Qualifying zusätzlich prüfen ob echte Zeiten vorliegen
    if session_display_name in ("Qualifying", "Sprint Qualifying"):
        try:
            q1_col = session.results.get("Q1", None)
            if q1_col is not None and pd.isna(q1_col).all():
                print(f"   ⏳ Qualifying hat noch keine Zeitdaten → übersprungen")
                return None
        except Exception:
            pass

    results_df = session.results.copy()

    if results_df is None or results_df.empty:
        print("   ⚠️ Keine Ergebnis-Daten vorhanden")
        return None

    is_race_type = session_display_name in ("Race", "Sprint")

    # Positionen ermitteln
    driver_results = []

    if is_race_type:
        # ── Race & Sprint: Positionen direkt aus session.results ──────────────
        # Fastest Lap: Fahrer mit dem kürzesten LapTime über alle Runden
        fastest_lap_abbr = None
        try:
            laps = session.laps
            if not laps.empty:
                fl_row = laps.loc[laps["LapTime"].idxmin()]
                fastest_lap_abbr = fl_row["Driver"]  # Kürzel
        except Exception:
            pass

        for _, row in results_df.iterrows():
            abbr   = str(row.get("Abbreviation", "")).strip()
            status = str(row.get("Status", "")).strip()

            # Position: FastF1 gibt hier die finale Rennposition
            pos_raw = row.get("Position", None)
            try:
                position = int(float(pos_raw))
            except (TypeError, ValueError):
                position = None

            # DNF: ClassifiedPosition ist die zuverlässigste Quelle.
            # "R" (Retired) = DNF; jeder numerische Wert = klassifiziert = kein DNF.
            # Fallback auf Status-String falls ClassifiedPosition fehlt.
            classified_pos = str(row.get("ClassifiedPosition", "")).strip()
            if classified_pos and classified_pos.lower() not in ("nan", "", "r"):
                # Numerische ClassifiedPosition → Fahrer ist klassifiziert
                dnf = False
            elif status and status != "Finished" and not status.startswith("+"):
                dnf = True
            else:
                dnf = False

            # Punkte
            if session_display_name == "Race":
                pts = RACE_POINTS.get(position, 0) if position else 0
            else:  # Sprint
                pts = SPRINT_POINTS.get(position, 0) if position else 0

            # DNF → keine Punkte
            if dnf:
                pts = 0

            fastest_lap = (abbr == fastest_lap_abbr)

            driver_results.append({
                "abbreviation": abbr,
                "position":     position,
                "dnf":          dnf,
                "fastest_lap":  fastest_lap,
                "points":       pts,
                "grid_pos":     None,  # wird für Race extern gesetzt
            })

    else:
        # ── Qualifying, Sprint Qualifying, FP ─────────────────────────────────
        # Positions-Ermittlung: session.results hat Q1/Q2/Q3-Zeiten
        # Wir sortieren nach der besten erzielten Zeit (Q3 → Q2 → Q1)
        # und respektieren damit die offizielle Qualifying-Klassifikation.
        #
        # Bug-Fix: Fahrer, die sich in einem späteren Segment nicht verbessern,
        # werden anhand ihrer besten Zeit aus dem jeweils letzten Segment eingeordnet.
        # FastF1's session.results hat dafür die Spalten Q1Time, Q2Time, Q3Time.

        # Für FP: nach schnellster Runde sortieren
        # Fahrer ohne Runde werden in process_session() ergänzt (driver_map dort verfügbar)
        if session_display_name in ("Practice 1", "Practice 2", "Practice 3"):
            laps = session.laps
            if laps.empty:
                print("   ⚠️ Keine Runden-Daten")
                return driver_results  # leere Liste → process_session ergänzt alle aus driver_map
            fastest = (
                laps.groupby("Driver")["LapTime"]
                .min()
                .dropna()
                .reset_index()
                .sort_values("LapTime")
                .reset_index(drop=True)
            )
            for rank, row in enumerate(fastest.itertuples(), 1):
                driver_results.append({
                    "abbreviation": row.Driver,
                    "position":     rank,
                    "dnf":          False,
                    "fastest_lap":  False,
                    "points":       0,
                    "grid_pos":     None,
                })

        else:
            # ── Qualifying / Sprint Qualifying ────────────────────────────────
            # session.results enthält alle Fahrer, auch solche ohne Zeit (NaN).
            # Fahrer MIT Zeit → offizielle Position aus session.results
            # Fahrer OHNE Zeit → werden nach Startnummer aufsteigend angehängt
            #                    (wie FIA-Klassifikation bei Zeitstrafen/kein Versuch)

            timed_drivers   = []
            no_time_drivers = []

            for _, row in results_df.iterrows():
                abbr = str(row.get("Abbreviation", "")).strip()
                if not abbr:
                    continue
                pos_raw = row.get("Position", None)
                try:
                    position = int(float(pos_raw))
                    has_position = True
                except (TypeError, ValueError):
                    position = None
                    has_position = False

                # Startnummer aus FastF1 als Fallback falls Fahrer nicht in driver_map
                ff1_number_raw = row.get("DriverNumber", None)
                try:
                    ff1_number = int(float(ff1_number_raw)) if ff1_number_raw is not None else 99
                except (TypeError, ValueError):
                    ff1_number = 99

                entry = {
                    "abbreviation": abbr,
                    "position":     position,
                    "dnf":          False,
                    "fastest_lap":  False,
                    "points":       0,
                    "grid_pos":     None,
                    "_ff1_number":  ff1_number,  # intern für Sortierung, wird nicht nach Notion geschrieben
                }

                if has_position:
                    timed_drivers.append(entry)
                else:
                    no_time_drivers.append(entry)

            # Timed: nach offizieller Position sortieren
            timed_drivers.sort(key=lambda d: d["position"])

            # No-time: nach FastF1 DriverNumber sortieren (driver_map hier nicht verfügbar)
            # process_session() überschreibt diese Positionen später mit driver_map-Nummern
            no_time_drivers.sort(key=lambda d: d["_ff1_number"])

            # Positionen der no-time-Fahrer: fortlaufend nach den timed-Fahrern
            last_timed_pos = timed_drivers[-1]["position"] if timed_drivers else 0
            for i, d in enumerate(no_time_drivers, 1):
                d["position"] = last_timed_pos + i

            driver_results = timed_drivers + no_time_drivers
            print(f"   📊 {len(timed_drivers)} mit Zeit, {len(no_time_drivers)} ohne Zeit (hinten eingereiht)")

    print(f"   ✅ {len(driver_results)} Fahrer-Ergebnisse geladen")
    return driver_results


# =============================================================================
# NOTION SCHREIBEN
# =============================================================================

def upsert_entry(results_db_id, driver_map, weekend_page_id,
                 gp_name, session_display_name, driver_data,
                 constructors_map=None, teams_name_map=None, existing_cache=None):
    if constructors_map is None: constructors_map = {}
    if teams_name_map is None: teams_name_map = {}
    if existing_cache is None: existing_cache = {}
    """
    Erstellt oder aktualisiert einen einzelnen Fahrer-Eintrag in der Results-DB.
    Gibt True bei Erfolg zurück.
    """
    abbr         = driver_data["abbreviation"]
    country_code = GP_COUNTRY_CODE.get(gp_name, gp_name[:3].upper())
    session_short = SESSION_SHORT_NAME.get(session_display_name, session_display_name)
    eintrag_title = f"{country_code} {session_short} – {abbr}"

    driver_entry = driver_map.get(abbr)
    if not driver_entry:
        print(f"      ⚠️ Fahrer '{abbr}' nicht in Drivers-DB gefunden → Eintrag übersprungen")
        return False

    driver_page_id = driver_entry["driver_id"]
    # team_page_id muss die ID aus Constructors Championship 2026 sein,
    # weil Session Results → Team auf diese DB zeigt.
    teams_db_id   = driver_entry.get("teams_db_id")
    team_page_id  = constructors_map.get(teams_name_map.get(teams_db_id, ""), None)

    notion_session_type = SESSION_NOTION_TYPE.get(session_display_name, session_display_name)

    # Properties für Notion aufbauen
    properties = {
        "Entry": {
            "title": [{"text": {"content": eintrag_title}}]
        },
        "Driver": {
            "relation": [{"id": driver_page_id}]
        },
        "Weekend": {
            "relation": [{"id": weekend_page_id}]
        },
        "Session Type": {
            "select": {"name": notion_session_type}
        },
        # Race + Sprint → Classification (für Rollup-Durchschnitt), alle anderen → Position
        **({"Classification": {"number": driver_data["position"]}}
           if session_display_name in ("Race", "Sprint")
           else {"Position": {"number": driver_data["position"]}}),
        "Points": {
            "number": driver_data["points"]
        },
        "DNF": {
            "checkbox": driver_data["dnf"]
        },
        "Fastest Lap": {
            "checkbox": driver_data["fastest_lap"]
        },
    }

    # Team-Relation setzen wenn vorhanden
    if team_page_id:
        properties["Team"] = {"relation": [{"id": team_page_id}]}
    else:
        print(f"      ⚠️ Kein Team für Fahrer '{abbr}' in Drivers-DB hinterlegt")

    # Grid Position nur setzen wenn vorhanden
    if driver_data.get("grid_pos") is not None:
        properties["Grid Position"] = {"number": driver_data["grid_pos"]}

    # Upsert: Cache-Lookup statt einzelner API-Abfrage
    existing_id = existing_cache.get(eintrag_title)

    try:
        if existing_id:
            notion_patch(
                f"https://api.notion.com/v1/pages/{existing_id}",
                {"properties": properties}
            )
            print(f"      🔄 Aktualisiert: {eintrag_title}")
        else:
            notion_post(
                "https://api.notion.com/v1/pages",
                {"parent": {"database_id": results_db_id}, "properties": properties}
            )
            print(f"      ✅ Erstellt:     {eintrag_title}")
        return True
    except requests.HTTPError as e:
        print(f"      ❌ API-Fehler für {eintrag_title}: {e.response.status_code} – {e.response.text}")
        return False


def process_session(year, gp_name, session_display_name,
                    results_db_id, driver_map, weekend_page_id,
                    qualifying_positions=None, constructors_map=None, teams_name_map=None,
                    existing_cache=None):
    if constructors_map is None: constructors_map = {}
    if teams_name_map is None: teams_name_map = {}
    if existing_cache is None: existing_cache = {}
    """Verarbeitet eine komplette Session und schreibt alle Fahrer in Notion."""
    print(f"\n   ── {session_display_name} ──")

    driver_results = get_session_results(year, gp_name, session_display_name)

    # FP: Fahrer die keine Runde gefahren sind aus driver_map ergänzen (nach Startnummer)
    if session_display_name in ("Practice 1", "Practice 2", "Practice 3"):
        if driver_results is None:
            print(f"   ⏭️  Keine Daten verfügbar, Session übersprungen")
            return 0
        timed_abbrs = {d["abbreviation"] for d in driver_results}
        no_lap = sorted(
            [(abbr, info["number"]) for abbr, info in driver_map.items() if abbr not in timed_abbrs],
            key=lambda x: x[1]
        )
        last_pos = len(timed_abbrs)
        for i, (abbr, _) in enumerate(no_lap, 1):
            driver_results.append({
                "abbreviation": abbr,
                "position":     last_pos + i,
                "dnf":          False,
                "fastest_lap":  False,
                "points":       0,
                "grid_pos":     None,
            })
        if no_lap:
            print(f"   📋 {len(no_lap)} Fahrer ohne Runde hinten: {[a for a, _ in no_lap]}")
    elif not driver_results:
        print(f"   ⏭️  Keine Daten verfügbar, Session übersprungen")
        return 0

    # Grid Position für Race aus Qualifying setzen
    if session_display_name == "Race" and qualifying_positions:
        for d in driver_results:
            d["grid_pos"] = qualifying_positions.get(d["abbreviation"])

    success = 0
    for driver_data in driver_results:
        ok = upsert_entry(
            results_db_id, driver_map, weekend_page_id,
            gp_name, session_display_name, driver_data,
            constructors_map=constructors_map,
            teams_name_map=teams_name_map,
            existing_cache=existing_cache
        )
        if ok:
            success += 1

    print(f"   📊 {session_display_name} fertig: {success}/{len(driver_results)} Einträge")
    return success


def process_race_weekend(year, gp_name, is_sprint_weekend,
                         results_db_id, driver_map, weekend_map,
                         constructors_map=None, teams_name_map=None):
    if constructors_map is None: constructors_map = {}
    if teams_name_map is None: teams_name_map = {}
    """Verarbeitet alle Sessions eines Rennwochenendes."""

    print(f"\n{'='*60}")
    print(f"🏁 {gp_name} {year}")
    print(f"   Sprint-Format: {'Ja' if is_sprint_weekend else 'Nein'}")
    print(f"{'='*60}")

    # Weekend-Seite in Notion suchen
    # Weekends-DB nutzt Ländernamen (z.B. "Australia"), nicht FastF1-Namen ("Australian Grand Prix")
    weekend_db_name = GP_WEEKEND_NAME.get(gp_name, gp_name)
    weekend_page_id = weekend_map.get(weekend_db_name)
    if not weekend_page_id:
        print(f"❌ '{weekend_db_name}' nicht in Weekends-DB gefunden!")
        print(f"   FastF1-Name: '{gp_name}'")
        print(f"   Verfügbare Wochenenden: {list(weekend_map.keys())}")
        return False

    # Qualifying-Positionen vorab laden (für Grid Position beim Race)
    qualifying_positions = get_qualifying_positions(year, gp_name)

    # Existierende Einträge einmal vorladen (Fix 1: ersetzt 110 Einzelabfragen)
    existing_cache = load_existing_entries_for_weekend(results_db_id, weekend_page_id)

    # Sessions des Wochenendes
    sessions = SPRINT_SESSIONS if is_sprint_weekend else NORMAL_SESSIONS
    total_success = 0

    for session_display_name in sessions:
        try:
            n = process_session(
                year, gp_name, session_display_name,
                results_db_id, driver_map, weekend_page_id,
                qualifying_positions=qualifying_positions,
                constructors_map=constructors_map,
                teams_name_map=teams_name_map,
                existing_cache=existing_cache
            )
            total_success += n
        except Exception as e:
            print(f"   ❌ Unerwarteter Fehler bei {session_display_name}:")
            traceback.print_exc()

    expected = len(sessions) * 22  # 22 Fahrer pro Session
    print(f"\n{'='*60}")
    print(f"✅ {gp_name} abgeschlossen")
    print(f"   {total_success} Einträge geschrieben (erwartet ~{expected})")
    print(f"{'='*60}\n")
    return total_success > 0


# =============================================================================
# RENNWOCHENENDE AUTOMATISCH ERKENNEN
# =============================================================================

def get_current_race_weekend():
    """
    Erkennt automatisch das aktuelle/letzte Rennwochenende anhand des Datums.
    Sucht im Fenster von -7 bis +3 Tagen um das Renndatum.
    """
    print("🔍 Suche aktuelles Rennwochenende...")
    current_date = datetime.now().date()
    print(f"📅 Heute: {current_date}")

    best_event = None
    best_diff  = float('inf')

    for event in F1_2026_CALENDAR:
        race_date = datetime.strptime(event["date"], "%Y-%m-%d").date()
        diff = (current_date - race_date).days
        if -7 <= diff <= 3:
            if abs(diff) < abs(best_diff):
                best_event = event
                best_diff  = diff

    if best_event:
        print(f"🏁 Erkannt: {best_event['name']} (Diff: {best_diff:+d} Tage)")
        return 2026, best_event["name"], best_event["sprint"]

    print("❌ Kein Rennwochenende im aktuellen Zeitfenster gefunden")
    print("   Tipp: RACE_NAME manuell als Umgebungsvariable setzen")
    return None, None, False


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("🚀 Starte F1 Session Results Update (2026 – Long Format)")
    print(f"   Timestamp: {datetime.now().isoformat()}\n")

    # ── Fahrer- und Weekend-Maps einmal laden ──────────────────────────────
    driver_map  = build_driver_map(DRIVERS_DB_ID)
    weekend_map = build_weekend_map(WEEKENDS_DB_ID)

    if not driver_map:
        print("❌ Keine Fahrer in Drivers-DB gefunden. Abbruch.")
        exit(1)
    if not weekend_map:
        print("❌ Keine Wochenenden in Weekends-DB gefunden. Abbruch.")
        exit(1)

    # ── Manuelles Override über Env-Variablen (optional) ──────────────────
    # Setze RACE_NAME z.B. auf "Australian Grand Prix" um ein spezifisches
    # Rennen zu erzwingen, unabhängig vom aktuellen Datum.
    override_name = os.getenv("RACE_NAME", "").strip()

    if override_name:
        print(f"⚙️  Manuelles Override: RACE_NAME='{override_name}'")
        match = next((e for e in F1_2026_CALENDAR if e["name"] == override_name), None)
        if not match:
            print(f"❌ '{override_name}' nicht im Kalender gefunden. Abbruch.")
            exit(1)
        year, gp_name, is_sprint = 2026, match["name"], match["sprint"]
    else:
        year, gp_name, is_sprint = get_current_race_weekend()

    if not gp_name:
        print("❌ Kein Rennwochenende ermittelt. Abbruch.")
        exit(1)

    # ── Constructors Championship Map laden ───────────────────────────────
    constructors_map = build_constructors_map(CONSTRUCTORS_DB_ID)
    if not constructors_map:
        print("⚠️  Constructors Championship 2026 ist leer – Team-Relation wird nicht gesetzt.")

    # Teams-Namen aus der Teams-DB auflösen (einmalig für alle Fahrer) ──────
    all_teams_db_ids = [v["teams_db_id"] for v in driver_map.values() if v.get("teams_db_id")]
    teams_name_map = build_teams_name_map(all_teams_db_ids)
    print(f"✅ {len(teams_name_map)} Team-Namen aufgelöst")
    for tid, tname in teams_name_map.items():
        constructor_id = constructors_map.get(tname, "❌ NICHT in Constructors Championship")
        print(f"   {tname} → {constructor_id}")

    # ── Verarbeitung ───────────────────────────────────────────────────────
    success = process_race_weekend(
        year, gp_name, is_sprint,
        RESULTS_DB_ID, driver_map, weekend_map,
        constructors_map=constructors_map,
        teams_name_map=teams_name_map
    )

    if success:
        print("✅ Update erfolgreich abgeschlossen!")
    else:
        print("❌ Update fehlgeschlagen oder keine Daten verfügbar!")
        exit(1)


if __name__ == "__main__":
    main()
