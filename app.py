import subprocess

# Define the input query for the news search
input_query = "Philadelphia Plane Crash"



# Step 1: Run `scrape.py` with the input query
print("\nRunning Web Scraping...\n")
scrape_process = subprocess.run(["python", "scrape.py", input_query], capture_output=True, text=True)

# Print the output of the scraper (for debugging)
print(scrape_process.stdout)

if scrape_process.returncode != 0:
    print("Scraping failed. Check `scrape.py` for errors.")
    print(scrape_process.stderr)
    exit(1)

# Step 2: Run `LLM.py` to analyze the scraped news
print("\nRunning LLM Analysis...\n")
llm_process = subprocess.run(["python", "LLM.py"], capture_output=True, text=True)

# Print the output of the LLM (for debugging)
print(llm_process.stdout)

if llm_process.returncode != 0:
    print("LLM analysis failed. Check `LLM.py` for errors.")
    print(llm_process.stderr)
    exit(1)

print("\nPipeline execution completed successfully.\n")