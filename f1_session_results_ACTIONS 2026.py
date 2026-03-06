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
WEEKENDS_DB_ID = "3166839379ed8135b474d348837083bb"  # ← aus URL: notion.so/DIESE-ID

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
    "Australian Grand Prix":    "AUS",
    "Chinese Grand Prix":       "CHN",
    "Japanese Grand Prix":      "JPN",
    "Bahrain Grand Prix":       "BHR",
    "Saudi Arabian Grand Prix": "SAU",
    "Miami Grand Prix":         "MIA",
    "Canadian Grand Prix":      "CAN",
    "Monaco Grand Prix":        "MON",
    "Barcelona-Catalunya Grand Prix": "BAR",
    "Austrian Grand Prix":      "AUT",
    "British Grand Prix":       "GBR",
    "Belgian Grand Prix":       "BEL",
    "Hungarian Grand Prix":     "HUN",
    "Dutch Grand Prix":         "NED",
    "Italian Grand Prix":       "ITA",
    "Spanish Grand Prix":       "ESP",
    "Azerbaijan Grand Prix":    "AZE",
    "Singapore Grand Prix":     "SGP",
    "United States Grand Prix": "USA",
    "Mexican Grand Prix":       "MEX",
    "Brazilian Grand Prix":     "BRA",
    "Las Vegas Grand Prix":     "LVG",
    "Qatar Grand Prix":         "QAT",
    "Abu Dhabi Grand Prix":     "UAE",
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
    Erstellt ein Dict: Fahrerkürzel → {"driver_id": page_id, "team_id": team_page_id|None}
    Liest Abbreviation, Name und Team-Relation aus der Drivers-Datenbank.
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

        # Team-Relation: gibt Liste von {"id": page_id} zurück
        team_relations = props.get("Team", {}).get("relation", [])
        team_page_id = team_relations[0]["id"] if team_relations else None

        if abbr:
            driver_map[abbr] = {
                "driver_id": page["id"],
                "team_id":   team_page_id,
            }
            team_info = team_page_id or "kein Team"
            print(f"   ✔ {abbr} → {name} | Team-ID: {team_info}")

    print(f"✅ {len(driver_map)} Fahrer geladen")
    return driver_map


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


def find_existing_entry(results_db_id, eintrag_title):
    """
    Sucht in der Results-DB nach einem Eintrag mit exakt diesem Eintrag-Titel.
    Gibt die Page-ID zurück, wenn gefunden, sonst None.
    """
    payload = {
        "filter": {
            "property": "Eintrag",
            "title": {"equals": eintrag_title}
        }
    }
    result = notion_post(
        f"https://api.notion.com/v1/databases/{results_db_id}/query", payload
    )
    results = result.get("results", [])
    if results:
        return results[0]["id"]
    return None


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

            # DNF: Status ist nicht "Finished" und nicht "+X Lap(s)"
            dnf = False
            if status and status != "Finished" and not status.startswith("+"):
                dnf = True

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

        # Für FP: einfach nach schnellster Runde sortieren
        if session_display_name in ("Practice 1", "Practice 2", "Practice 3"):
            laps = session.laps
            if laps.empty:
                print("   ⚠️ Keine Runden-Daten")
                return None
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
            # Qualifying oder Sprint Qualifying:
            # Verwende session.results – Position ist bereits offiziell gesetzt
            for _, row in results_df.iterrows():
                abbr = str(row.get("Abbreviation", "")).strip()
                pos_raw = row.get("Position", None)
                try:
                    position = int(float(pos_raw))
                except (TypeError, ValueError):
                    position = None

                if abbr and position:
                    driver_results.append({
                        "abbreviation": abbr,
                        "position":     position,
                        "dnf":          False,
                        "fastest_lap":  False,
                        "points":       0,
                        "grid_pos":     None,
                    })

    print(f"   ✅ {len(driver_results)} Fahrer-Ergebnisse geladen")
    return driver_results


# =============================================================================
# NOTION SCHREIBEN
# =============================================================================

def upsert_entry(results_db_id, driver_map, weekend_page_id,
                 gp_name, session_display_name, driver_data):
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
    team_page_id   = driver_entry["team_id"]

    notion_session_type = SESSION_NOTION_TYPE.get(session_display_name, session_display_name)

    # Properties für Notion aufbauen
    properties = {
        "Eintrag": {
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
        "Position": {
            "number": driver_data["position"]
        },
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

    # Prüfen ob Eintrag schon existiert (Upsert)
    existing_id = find_existing_entry(results_db_id, eintrag_title)

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
                    qualifying_positions=None):
    """Verarbeitet eine komplette Session und schreibt alle Fahrer in Notion."""
    print(f"\n   ── {session_display_name} ──")

    driver_results = get_session_results(year, gp_name, session_display_name)
    if not driver_results:
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
            gp_name, session_display_name, driver_data
        )
        if ok:
            success += 1

    print(f"   📊 {session_display_name} fertig: {success}/{len(driver_results)} Einträge")
    return success


def process_race_weekend(year, gp_name, is_sprint_weekend,
                         results_db_id, driver_map, weekend_map):
    """Verarbeitet alle Sessions eines Rennwochenendes."""

    print(f"\n{'='*60}")
    print(f"🏁 {gp_name} {year}")
    print(f"   Sprint-Format: {'Ja' if is_sprint_weekend else 'Nein'}")
    print(f"{'='*60}")

    # Weekend-Seite in Notion suchen
    weekend_page_id = weekend_map.get(gp_name)
    if not weekend_page_id:
        print(f"❌ '{gp_name}' nicht in Weekends-DB gefunden!")
        print(f"   Verfügbare Wochenenden: {list(weekend_map.keys())}")
        return False

    # Qualifying-Positionen vorab laden (für Grid Position beim Race)
    qualifying_positions = get_qualifying_positions(year, gp_name)

    # Sessions des Wochenendes
    sessions = SPRINT_SESSIONS if is_sprint_weekend else NORMAL_SESSIONS
    total_success = 0

    for session_display_name in sessions:
        try:
            n = process_session(
                year, gp_name, session_display_name,
                results_db_id, driver_map, weekend_page_id,
                qualifying_positions=qualifying_positions
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

    # ── Verarbeitung ───────────────────────────────────────────────────────
    success = process_race_weekend(
        year, gp_name, is_sprint,
        RESULTS_DB_ID, driver_map, weekend_map
    )

    if success:
        print("✅ Update erfolgreich abgeschlossen!")
    else:
        print("❌ Update fehlgeschlagen oder keine Daten verfügbar!")
        exit(1)


if __name__ == "__main__":
    main()
