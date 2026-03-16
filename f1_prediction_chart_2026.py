import requests
import math
import json
import os

# Notion API Config
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = "3166839379ed81d7bd2de7ed38537d08"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Schritt 1: Datenbank-Einträge aus Notion abrufen
def get_notion_predictions():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    predictions = []
    has_more = True
    next_cursor = None

    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()

        for page in data.get("results", []):
            
           # print(json.dumps(page["properties"], indent=2))

            prediction_val = page["properties"]["Prediction"].get("number")
            if prediction_val is not None:  # nur gefahrene Rennen zählen
                predictions.append(prediction_val)

        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return predictions

# Schritt 2: Accuracy berechnen
def calculate_accuracy(predictions):
    if not predictions:
        return 0
    sum_predictions = sum(predictions)
    count_races = len(predictions)
    accuracy = sum_predictions / (3 * count_races)
    return accuracy

# Schritt 3: HTML mit Chart.js generieren
def generate_html(accuracy, correct_count, incorrect_count):
    percent = round(accuracy * 100, 1)
    ring_color = "#ffffff"
    background_ring = "rgba(255,255,255,0.1)"
    text_color = "#ffffff"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Prediction Accuracy</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {{
      margin: 0;
      background-color: #191919;
    }}
    #chartContainer {{
      width: 300px;
      height: 300px;
      display: flex;
      justify-content: center;
      align-items: center;
    }}
    canvas {{
      background-color: #191919;
    }}
  </style>
</head>
<body>
  <div id="chartContainer">
    <canvas id="accuracyChart"></canvas>
  </div>
  <script>
    const accuracy = {percent};
    const correct = {correct_count};
    const incorrect = {incorrect_count};
    const ctx = document.getElementById('accuracyChart').getContext('2d');

    new Chart(ctx, {{
      type: 'doughnut',
      data: {{
        labels: ['Correct', 'Incorrect'],
        datasets: [{{
          data: [correct, incorrect],
          backgroundColor: ['{ring_color}', '{background_ring}'],
          borderWidth: 0
        }}]
      }},
      options: {{
        cutout: '75%',
        responsive: false,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            enabled: true,
            callbacks: {{
              label: function(context) {{
                let label = context.label || '';
                let value = context.parsed;
                return label + ': ' + value;
              }}
            }}
          }}
        }}
      }},
      plugins: [{{
        id: 'centerText',
        beforeDraw: (chart) => {{
          const {{ ctx, chartArea: {{ width, height }} }} = chart;
          ctx.save();
          // "Predictions" oben
          ctx.font = '16px Arial';
          ctx.fillStyle = '{text_color}';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText('Predictions', width / 2, height / 2 - 20);

          // Prozentzahl darunter
          ctx.font = 'bold 32px Arial';
          ctx.fillStyle = '{text_color}';
          ctx.fillText(accuracy + '%', width / 2, height / 2 + 10);
        }}
      }}]
    }});
  </script>
</body>
</html>
"""
    with open("f1_prediction_chart_2026.html", "w", encoding="utf-8") as f:
        f.write(html_content)


# Hauptlogik
if __name__ == "__main__":
    predictions = get_notion_predictions()
    accuracy = calculate_accuracy(predictions)

    correct_count = int(sum(predictions))
    incorrect_count = int(len(predictions) * 3 - correct_count)

    generate_html(accuracy, correct_count, incorrect_count)
    print(f"✅ Prediction Accuracy Chart erstellt ({round(accuracy*100, 1)}%) → index.html")
