from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import subprocess
import json
import os
import sys

app = Flask(__name__)
CORS(app)  # Allow all domains to access the API

SCRAPED_FILE = "scraped_news.json"
ANALYZED_FILE = "news_analysis.json"

python_executable = sys.executable

def run_scraping(query):
    """Runs the scrape.py script with the given query."""
    process = subprocess.run([python_executable, "scrape.py", query], capture_output=True, text=True)
    if process.returncode != 0:
        return {"error": "Scraping failed", "details": process.stderr}
    return None

def run_analysis():
    """Runs the llm.py script to analyze scraped data."""
    process = subprocess.run(
        [python_executable, "llm.py"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    if process.returncode != 0:
        return {"error": "Analysis failed", "details": process.stderr}
    return None

@app.route("/process", methods=["GET"])
def process_news():
    """
    Flask endpoint to scrape news and analyze bias/reliability.
    - Example: /process?query=California
    - Returns JSON response or downloadable JSON file.
    """
    
    query = request.args.get("query", "").strip()
    
    print(f"Processing news for query: {query}")
    
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    # Step 1: Run scraping
    scrape_error = run_scraping(query)
    if scrape_error:
        return jsonify(scrape_error), 500

    # Step 2: Run analysis
    analyze_error = run_analysis()
    if analyze_error:
        return jsonify(analyze_error), 500

    # Load the final analyzed data
    if os.path.exists(ANALYZED_FILE):
        with open(ANALYZED_FILE, "r", encoding="utf-8") as file:
            try:
                analyzed_data = json.load(file)
            except json.JSONDecodeError:
                return jsonify({"error": "Failed to read analyzed data"}), 500
            except Exception as e:
                return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Analyzed data file not found"}), 500


    return jsonify(analyzed_data)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
