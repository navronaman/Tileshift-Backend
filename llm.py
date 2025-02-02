# -*- coding: utf-8 -*-
import os
import json
import re
import time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langchain_community.tools import ArxivQueryRun, WikipediaQueryRun

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
LANGSMITH_API_KEY = os.getenv('LANGSMITH_API_KEY')

if LANGSMITH_API_KEY is None:
    raise ValueError("LANGSMITH_API_KEY is not set. Please check your environment variables.")

LANGSMITH_API_KEY = LANGSMITH_API_KEY.strip()

# Set up environment variables
os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "CourseLanggraph"

# Initialize LLM
llm = ChatGroq(model_name="deepseek-r1-distill-llama-70b", groq_api_key=GROQ_API_KEY)

# Load Arxiv and Wikipedia tools
arxiv_wrapper = ArxivAPIWrapper(top_k_results=3, doc_content_chars_max=400)
arxiv_tool = ArxivQueryRun(api_wrapper=arxiv_wrapper)

api_wrapper = WikipediaAPIWrapper(top_k_results=3, doc_content_chars_max=400)
wiki_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

tools = [arxiv_tool, wiki_tool]
llm_with_tools = llm.bind_tools(tools=tools)

# Langgraph state
class State(TypedDict):
    messages: Annotated[list, add_messages]

graph_builder = StateGraph(State)

def chatbot(state: State):
    return {"messages": llm_with_tools.invoke(state["messages"])}

graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)

graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge("chatbot", END)

graph = graph_builder.compile()

# Load user inputs from scraped JSON file
SCRAPED_JSON_FILE = "scraped_news.json"
OUTPUT_JSON_FILE = "news_analysis.json"

if not os.path.exists(SCRAPED_JSON_FILE):
    raise FileNotFoundError(f"Scraped data file '{SCRAPED_JSON_FILE}' not found!")

with open(SCRAPED_JSON_FILE, "r", encoding="utf-8") as json_file:
    user_inputs = json.load(json_file)

if not user_inputs:
    raise ValueError("No articles found in the scraped news JSON file!")

# Load existing results if the file exists
if os.path.exists(OUTPUT_JSON_FILE):
    with open(OUTPUT_JSON_FILE, "r", encoding="utf-8") as json_file:
        try:
            all_results = json.load(json_file)
        except json.JSONDecodeError:
            all_results = []
else:
    all_results = []

processed_links = {entry["link"] for entry in all_results}

for user_input in user_inputs:
    if user_input["link"] in processed_links:
        print(f"\nSkipping already processed article: {user_input['link']}")
        continue

    print("\nProcessing Input...\n")
    print(json.dumps(user_input, indent=4))  # Debugging: Shows the user input being processed

    system_input = r"""
    Input: You will receive a JSON object of the following format:
    {{
        "link":
        "Provider":
        "headline":
        "content":
    }}

    Task:
    Design and implement a JSON object that quantitatively evaluates a news article by calculating 2 metrics and generating a summary of "content" of length 100-250 characters.
    
    The output should capture biasFactor (which is basically the political ideology/tone of the article, such as right-wing, left-wing, center etc.) and reliabilityFactor, ultimately combining them into a JSON format.
    The bias factor is a number between -38 to 38, where -38 is extreme left-wing bias, -19 is left wing bias, 0 is neutral, 19 is right wing bias, and 38 is extreme right-wing bias.
    Make sure to consider the provider as well to determine the bias factor, as it is very rare for an article to be completely neutral.
    The reliability factor is a number between 0 to 64, where 0 means contains inaccurate information, 24 means selective or incomplete coverage, 40 means mix of fact reporting and analysis or simple reporting, and 62 means original fact reporting.
    Remember, the summary should be a concise representation of the content, not a direct excerpt.
    Also remember that the two metrics need to be numbers. 
    
    REMEMBER, you must think and reason about the 2 metrics with yourself, but you shall not be allowed to output or show that reasoning in any form.
    
    Final Output: 
    You must output a JSON object of the below-mentioned format. You need to strictly follow the exact format:
    {{
        "link":
        "Provider":
        "headline":
        "summary":
        "biasFactor":
        "reliabilityFactor":
    }}
    """

    # Run LLM with user input
    events = graph.stream(
        {"messages": [("system", system_input), ("user", json.dumps(user_input))]},
        stream_mode="values"
    )

    # Collect all streamed messages
    responses = []
    for event in events:
        responses.append(event["messages"][-1].content)

    # Join all streamed responses
    final_response = "".join(responses)

    # Extract JSON objects
    json_matches = re.findall(r'\{[\s\S]*?\}', final_response)

    # Ensure we get the second JSON object
    if len(json_matches) >= 2:
        extracted_json = json_matches[1]  # Get the second JSON object
    else:
        print(f" Skipping article due to missing second JSON object.")
        with open("error_log.txt", "a", encoding="utf-8") as error_file:
            error_file.write(f"Failed processing input: {json.dumps(user_input, indent=4)}\n")
            error_file.write(f"Response: {final_response[:500]}\n\n")
        continue

    # Convert to Python dictionary
    try:
        json_data = json.loads(extracted_json)
    except json.JSONDecodeError as e:
        print(f" Skipping article due to JSON decode error: {e}")
        with open("error_log.txt", "a", encoding="utf-8") as error_file:
            error_file.write(f"Failed processing input: {json.dumps(user_input, indent=4)}\n")
            error_file.write(f"Response: {final_response[:500]}\n\n")
        continue

    # **Only write the extracted JSON output**
    all_results.append(json_data)
    processed_links.add(json_data["link"])  # Mark as processed

    # Save each processed entry immediately
    with open(OUTPUT_JSON_FILE, "w", encoding="utf-8") as json_file:
        json.dump(all_results, json_file, indent=4, ensure_ascii=False)

    # Print final extracted JSON for debugging
    print(json.dumps(json_data, indent=4))

    # Small delay to avoid API rate limits
    time.sleep(2)

print(f"\n All results saved successfully to {OUTPUT_JSON_FILE}!")