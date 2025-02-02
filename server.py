from flask import Flask, request, jsonify, send_file
import subprocess
import json
import os

app = Flask(__name__)

SCRAPED_FILE = "scraped_news.json"
ANALYZED_FILE = "news_analysis.json"

def run_scraping(query):
    """Runs the scrape.py script with the given query."""
    process = subprocess.run(["python", "scrape.py", query], capture_output=True, text=True)
    if process.returncode != 0:
        return {"error": "Scraping failed", "details": process.stderr}
    return None

def run_analysis():
    """Runs the llm.py script to analyze scraped data."""
    process = subprocess.run(["python", "llm.py"], capture_output=True, text=True)
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
    download = request.args.get("download", "false").lower() == "true"

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
    else:
        return jsonify({"error": "Analyzed data file not found"}), 500

    # Step 3: Filter results based on query
    filtered_results = [
        entry for entry in analyzed_data if query.lower() in entry["headline"].lower()
    ]

    if not filtered_results:
        return jsonify({"message": "No matching results found", "query": query})

    # Step 4: Provide either JSON response or downloadable file
    if download:
        temp_file = "filtered_results.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(filtered_results, f, indent=4, ensure_ascii=False)

        return send_file(temp_file, as_attachment=True, download_name="filtered_results.json", mimetype="application/json")

    return jsonify(filtered_results)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
