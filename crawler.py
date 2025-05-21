import asyncio
from crawl4ai import *
import os
from groq import Groq
from dotenv import load_dotenv
import json
import csv
import pandas as pd

load_dotenv()

# Define all the keys we want to populate in our JSON
ALL_INFO_KEYS = ["phone_number", "email", "company_overview", "headquarters_location"]

async def extract_info_from_content(client: Groq, content: str, existing_data: dict = None, return_tokens: bool = False, model_name: str = "qwen-qwq-32b", info_keys=None) -> dict:
    """
    Uses Groq to extract structured information from text content.
    If existing_data is provided, it's included in the prompt to guide the LLM.
    If return_tokens is True, also returns the number of tokens used.
    info_keys: list of keys to extract (defaults to ALL_INFO_KEYS)
    """
    if info_keys is None:
        info_keys = ALL_INFO_KEYS
    if not content:
        if return_tokens:
            return {key: "Not found" for key in info_keys}, 0
        else:
            return {key: "Not found" for key in info_keys}

    current_data_prompt_part = ""
    if existing_data:
        prompt_existing_data = {key: existing_data.get(key, "Not found") for key in info_keys}
        current_data_str = json.dumps(prompt_existing_data, indent=2)
        current_data_prompt_part = f"""
We have already gathered some information:
---
{current_data_str}
---
Please use the new website content to update or complete this information, especially focusing on any fields currently marked as \"Not found\" or improving existing entries.
"""

    prompt = f"""
Given the following website content:
---
{content}
---
{current_data_prompt_part}
Please extract or update the following information about the company and provide it in JSON format.
The JSON object should have the following keys: {json.dumps(info_keys)}.
If any information cannot be found in the current content or the existing information, use \"Not found\" as the value for the corresponding key.
Ensure the output is a single, valid JSON object.
"""

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model_name, # Use the provided model name
            response_format={"type": "json_object"}, # Request JSON output
        )
        llm_output_str = chat_completion.choices[0].message.content
        extracted_info = json.loads(llm_output_str)
        for key in info_keys:
            if key not in extracted_info:
                extracted_info[key] = "Not found"
        tokens_used = 0
        if hasattr(chat_completion, 'usage') and chat_completion.usage:
            tokens_used = getattr(chat_completion.usage, 'total_tokens', 0)
        if return_tokens:
            return extracted_info, tokens_used
        else:
            return extracted_info
    except json.JSONDecodeError as e:
        if return_tokens:
            return {key: existing_data.get(key, "Not found") if existing_data else "Not found" for key in info_keys}, 0
        else:
            return {key: existing_data.get(key, "Not found") if existing_data else "Not found" for key in info_keys}
    except Exception as e:
        if return_tokens:
            return {key: existing_data.get(key, "Not found") if existing_data else "Not found" for key in info_keys}, 0
        else:
            return {key: existing_data.get(key, "Not found") if existing_data else "Not found" for key in info_keys}

def is_data_complete(data: dict, info_keys=None) -> bool:
    """Checks if all values in the data dictionary are filled (not 'Not found')."""
    if info_keys is None:
        info_keys = ALL_INFO_KEYS
    if not data:
        return False
    for key in info_keys:
        if data.get(key, "Not found") == "Not found":
            return False
    return True

def update_master_json(master_data: dict, new_data: dict, info_keys=None):
    """Updates master_data with new_data, prioritizing non-'Not found' values."""
    if info_keys is None:
        info_keys = ALL_INFO_KEYS
    for key in info_keys:
        if key in new_data and new_data[key] != "Not found":
            master_data[key] = new_data[key]
        elif key not in master_data: # Initialize if key is missing
            master_data[key] = "Not found"

async def process_single_url(start_url: str, client: Groq, return_tokens: bool = False, model_name: str = "qwen-qwq-32b", info_keys=None) -> dict:
    if info_keys is None:
        info_keys = ALL_INFO_KEYS
    master_json_data = {key: "Not found" for key in info_keys}
    visited_urls = set()
    max_pages_to_crawl = 5 # Limit for inner pages
    total_tokens = 0

    async with AsyncWebCrawler(max_depth=1,exclude_external_links=True,exclude_social_media_links=True) as crawler:
        result = await crawler.arun(url=start_url)
        visited_urls.add(start_url)

        if result and result.markdown:
            homepage_info, tokens_used = await extract_info_from_content(client, result.markdown, master_json_data, return_tokens=True, model_name=model_name, info_keys=info_keys)
            total_tokens += tokens_used
            update_master_json(master_json_data, homepage_info, info_keys=info_keys)

        if not is_data_complete(master_json_data, info_keys=info_keys) and result and result.links:
            internal_links_data = result.links.get("internal", [])
            links_to_check = []
            if internal_links_data:
                links_to_check = [link_dict.get('href') for link_dict in internal_links_data if link_dict.get('href')]
            contact_keywords = ["contact", "contatti", "contattaci"]
            prioritized_links = []
            other_links = []
            for link_url in links_to_check:
                if any(keyword in link_url.lower() for keyword in contact_keywords):
                    prioritized_links.append(link_url)
                else:
                    other_links.append(link_url)
            ordered_links_to_crawl = (prioritized_links + other_links)[:max_pages_to_crawl]
            for inner_url in ordered_links_to_crawl:
                if inner_url in visited_urls:
                    continue
                if is_data_complete(master_json_data, info_keys=info_keys):
                    break
                try:
                    inner_result = await crawler.arun(url=inner_url)
                    visited_urls.add(inner_url)
                    if inner_result and inner_result.markdown:
                        inner_page_info, tokens_used = await extract_info_from_content(client, inner_result.markdown, master_json_data, return_tokens=True, model_name=model_name, info_keys=info_keys)
                        total_tokens += tokens_used
                        update_master_json(master_json_data, inner_page_info, info_keys=info_keys)
                except Exception:
                    pass
    if return_tokens:
        return master_json_data, total_tokens
    else:
        return master_json_data

async def crawl_urls(urls: list[str]) -> pd.DataFrame:
    """Crawl a list of URLs and return a DataFrame with the results."""
    load_dotenv()
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY not found in environment variables. Please set it in your .env file.")
    client = Groq(api_key=groq_api_key)
    results = []
    for i, url in enumerate(urls):
        # Ensure url has protocol
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        info = await process_single_url(url, client)
        row = {"original_url": url}
        row.update(info)
        results.append(row)
    df = pd.DataFrame(results)
    return df

async def main(start_url:str):
    load_dotenv()
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        print("GROQ_API_KEY not found in environment variables. Please set it in your .env file.")
        return
    client = Groq(api_key=groq_api_key)
    info = await process_single_url(start_url, client)
    output_filename = "company_info.csv"
    file_exists = os.path.isfile(output_filename)
    fieldnames = ["original_url"] + ALL_INFO_KEYS
    row_data = {"original_url": start_url}
    row_data.update(info)
    with open(output_filename, "a", encoding="utf-8", newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_data)
    print(f"\nFinal extracted information appended to {output_filename}:")
    print(info)
    if not is_data_complete(info):
        print("\nWarning: Some information might still be missing ('Not found').")

def run_all_urls():
    input_urls = pd.read_csv("urls.csv")
    urls = input_urls['url'].tolist()
    for url in urls:
        print(f"\nStarting crawl for: {url}")
        asyncio.run(main("https://"+url))

if __name__ == "__main__":
    run_all_urls()