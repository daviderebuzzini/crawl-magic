import sys
import asyncio
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
import pandas as pd
import nest_asyncio
import os
import json
import time
from crawler import process_single_url
from groq import Groq
from dotenv import load_dotenv

nest_asyncio.apply()

st.set_page_config(page_title="The Magic Scraper", layout="centered")
st.title("🪄 The Magic Scraper")
st.markdown("""
Upload a CSV file with a **'url'** column. The app will crawl each website, extract company info, and let you download the results. Progress, token usage, and model info are shown below.
""")

uploaded_file = st.file_uploader("Upload a CSV file with a 'url' column", type="csv")

MODEL_NAME = "qwen-qwq-32b"  # Keep in sync with crawler.py
# Pricing for QwQ 32B (from screenshot):
# Input: $0.29 per 1M tokens, Output: $0.39 per 1M tokens
# We'll use output token price for a conservative estimate
TOKEN_COST_PER_MILLION = 0.39

st.info(f"**Model in use:** `{MODEL_NAME}` | **Output token price:** ${TOKEN_COST_PER_MILLION}/1M tokens")

token_counter = st.empty()
progress_bar = st.empty()
status_text = st.empty()

DEFAULT_INFO_KEYS = [
    "phone_number",
    "email",
    "company_overview",
    "headquarters_location"
]

st.markdown("---")
st.subheader("Select which fields to extract:")
selected_keys = st.multiselect(
    "Choose the information fields you want to extract from each website:",
    options=DEFAULT_INFO_KEYS,
    default=DEFAULT_INFO_KEYS,
    help="You can select or deselect fields as needed."
)

if uploaded_file is not None and selected_keys:
    df = pd.read_csv(uploaded_file)
    st.subheader("Preview of uploaded URLs:")
    st.dataframe(df.head(), use_container_width=True)
    urls = df['url'].tolist()
    if st.button("✨ Start Crawling", type="primary"):
        load_dotenv()
        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            st.error("GROQ_API_KEY not found in environment variables. Please set it in your .env file.")
            st.stop()
        client = Groq(api_key=groq_api_key)
        results = []
        total_tokens = 0
        n = len(urls)
        progress = 0
        progress_bar.progress(progress, text=f"Starting...")
        start_time = time.time()
        for i, url in enumerate(urls):
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            status_text.info(f"Crawling: {url} ({i+1}/{n})")
            info, tokens_used = asyncio.get_event_loop().run_until_complete(
                process_single_url(url, client, return_tokens=True, model_name=MODEL_NAME, info_keys=selected_keys)
            )
            total_tokens += tokens_used
            row = {"original_url": url}
            row.update(info)
            results.append(row)
            progress = int(((i+1)/n)*100)
            # Calculate cost so far
            cost_so_far = (total_tokens / 1_000_000) * TOKEN_COST_PER_MILLION
            progress_bar.progress(progress, text=f"Processed {i+1} of {n} URLs")
            token_counter.info(f"**Total Groq tokens used so far:** {total_tokens} | **Estimated cost:** ${cost_so_far:.4f}")
        end_time = time.time()
        elapsed = (end_time - start_time) / 60  # minutes
        status_text.success(f"All URLs processed in {elapsed:.2f} minutes!")
        results_df = pd.DataFrame(results)
        st.subheader("Results Table")
        st.dataframe(results_df, use_container_width=True)
        # Fill rate calculation
        fill_rates = {}
        total_filled = 0
        total_possible = n * len(selected_keys)
        for key in selected_keys:
            filled = results_df[key].ne("Not found").sum()
            fill_rates[key] = filled / n * 100
            total_filled += filled
        overall_fill_rate = total_filled / total_possible * 100
        st.markdown("### Fill Rate per Field:")
        for key in selected_keys:
            st.write(f"{key}: {fill_rates[key]:.1f}%")
        st.write(f"**Overall fill rate:** {overall_fill_rate:.1f}%")
        csv = results_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Download Results as CSV",
            data=csv,
            file_name='company_info.csv',
            mime='text/csv',
            use_container_width=True
        )
        total_cost = (total_tokens / 1_000_000) * TOKEN_COST_PER_MILLION
        st.info(f"**Model used:** `{MODEL_NAME}` | **Total Groq tokens used:** {total_tokens} | **Estimated cost:** ${total_cost:.4f} | **Time taken:** {elapsed:.2f} minutes | **Overall fill rate:** {overall_fill_rate:.1f}%")