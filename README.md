# Magic Scraper

A Streamlit web app to crawl company websites and extract structured information using Groq LLMs.

## Features
- Upload a CSV file with a `url` column
- Select which fields to extract (phone, email, overview, headquarters, etc.)
- Progress bar, live token usage, and cost estimate
- Fill rate and time taken for the crawl
- Download results as CSV

## Setup

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/your-repo-name.git
cd your-repo-name
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Set up your Groq API key**

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
```

**Never commit your `.env` file or API keys to GitHub!**

4. **Run the app locally**

```bash
streamlit run app.py
```

5. **Deploy to Streamlit Cloud**
- Push your code to GitHub (the `.env` file is ignored by `.gitignore`)
- On [Streamlit Cloud](https://streamlit.io/cloud), set your `GROQ_API_KEY` as a secret in the app settings

## Input Format
- Upload a CSV file with a column named `url` (one website per row)

## Output
- Download a CSV with the original URL and the extracted fields

## Security
- `.env` and any files containing secrets are excluded from git by `.gitignore`
- **Never share your API key publicly**

## License
MIT
