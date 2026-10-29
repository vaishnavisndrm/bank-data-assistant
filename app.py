"""Streamlit text-to-SQL chat over the bank SQLite DB, powered by a local Ollama model."""
import os
import re
import sqlite3

import pandas as pd
import requests
import streamlit as st

API_KEY = st.secrets["OLLAMA_API_KEY"]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = ".\central_bank_sample.db"
#os.path.join(HERE,r"C:\Users\V1223232\OneDrive - Saint-Gobain\Pytho\Shyams guide\central_bank_sample.db")
SCHEMA_FILE = os.path.join(HERE, "schema.sql")

BUSINESS_NOTES = """
Notes about the data:
- Dates are stored as ISO text 'YYYY-MM-DD'. Use SQLite date functions: date('now'), strftime('%Y-%m', txn_date), etc.
- Amounts and balances are in INR.
- accounts.status: Active/Dormant/Closed/Frozen. A customer (cif_id) can have many accounts.
- transactions.txn_type is 'Credit' (money in) or 'Debit' (money out).
- loans.npa_status: Standard, SMA, Substandard, Doubtful, Loss. NPA (non-performing) usually means Substandard, Doubtful or Loss.
- Customer full name = first_name || ' ' || last_name.
- branches.region is one of North/South/East/West/Central.
- To report by branch/city, JOIN branches on branch_id (accounts.branch_id, loans.branch_id) or customers.home_branch_id.
"""

SYSTEM_PROMPT = """You are an expert SQLite analyst for a retail bank.
Convert the user's question into ONE read-only SQLite query.

Rules:
- Output ONLY the SQL query, no explanation, no markdown fences.
- Only SELECT (or WITH ... SELECT). Never modify data.
- Use only tables and columns that exist in the schema below.
- Prefer explicit JOINs with table aliases, and add sensible column aliases.
- Never select PAN, mobile or email unless the user explicitly asks for them.
- If the question cannot be answered from the schema, output exactly: SELECT 'Not answerable from available data' AS message

Schema:
{schema}
{notes}
"""

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


# ---------- Ollama ----------

# def list_models(host: str) -> list[str]:
#     try:
#         r = requests.get(f"https://ollama.com/api/tags", timeout=5)
#         r.raise_for_status()
#         return [m["name"] for m in r.json().get("models", [])]
#     except Exception:
#         return []


import requests

def list_models(host: str) -> list[str]:
    # Define the exact model you want to allow
    TARGET_MODEL = "gemma4:31b" 
    
    try:
        r = requests.get("https://ollama.com/api/tags", timeout=5)
        r.raise_for_status()
        
        # Filter the incoming JSON array to only keep the target model name
        return [m["name"] for m in r.json().get("models", []) if m["name"] == TARGET_MODEL]
        
    except Exception:
        return []


def chat(host: str, model: str, messages: list[dict], temperature: float = 0.0) -> str:
    r = requests.post(
        f"{host}/api/chat",
        json={"model": model, "messages": messages, "stream": False,
              "options": {"temperature": temperature}},
        headers=headers,
        timeout=300,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# ---------- SQL helpers ----------
@st.cache_data
def load_schema() -> str:
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        return f.read()


def extract_sql(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)  # reasoning models
    m = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        text = m.group(1)
    return text.strip().rstrip(";").strip()


def validate_sql(sql: str) -> str | None:
    """Return an error message if the query is unsafe, else None."""
    if not re.match(r"^\s*(select|with)\b", sql, re.IGNORECASE):
        return "Only SELECT queries are allowed."
    if ";" in sql:
        return "Only a single statement is allowed."
    if FORBIDDEN.search(sql):
        return "Query contains a forbidden keyword."
    return None


def run_query(db_path: str, sql: str, max_rows: int) -> pd.DataFrame:
    # Read-only connection: even a bad query cannot change data.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.execute(sql)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(max_rows)
        return pd.DataFrame(rows, columns=cols)
    finally:
        conn.close()


def generate_and_run(question, history, host, model, db_path, max_rows):
    """Ask the LLM for SQL, run it, and retry once with the error if it fails."""
    system = SYSTEM_PROMPT.format(schema=load_schema(), notes=BUSINESS_NOTES)
    messages = [{"role": "system", "content": system}]
    for q in history[-3:]:  # a little context for follow-up questions
        messages.append({"role": "user", "content": q["question"]})
        messages.append({"role": "assistant", "content": q["sql"]})
    messages.append({"role": "user", "content": question})

    sql, error = "", None
    for attempt in range(2):
        sql = extract_sql(chat(host, model, messages))
        error = validate_sql(sql)
        if not error:
            try:
                return sql, run_query(db_path, sql, max_rows), None
            except Exception as e:  # SQL error -> let the model fix it
                error = str(e)
        messages.append({"role": "assistant", "content": sql})
        messages.append({"role": "user",
                         "content": f"That query failed: {error}\nReturn a corrected SQL query only."})
    return sql, None, error


# ---------- UI ----------
st.set_page_config(page_title="Bank Data Assistant", page_icon="🏦", layout="wide")
st.title("🏦 Bank Data Assistant")
st.caption("Ask questions in plain English. A local Ollama model writes the SQL; results come from your database.")

with st.sidebar:
    st.header("Settings")
    host = st.text_input("Ollama host", os.getenv("OLLAMA_HOST", "https://ollama.com/"))
    models = list_models(host)
    if models:
        model = st.selectbox("Model", models)
    else:
        st.warning("Can't reach Ollama or no models pulled. Run `ollama serve` and `ollama pull qwen2.5-coder`.")
        model = st.text_input("Model name", "qwen2.5-coder:7b")
    db_path = st.text_input("SQLite DB path", DEFAULT_DB)
    max_rows = st.slider("Max rows returned", 10, 1000, 200, step=10)
    summarize = st.checkbox("Summarize results in words", value=False)
    if st.button("Clear chat"):
        st.session_state.history = []
        st.rerun()
    with st.expander("Schema"):
        st.code(load_schema(), language="sql")
    st.markdown("**Try:**")
    examples = [
        "Top 5 branches by total account balance",
        "How many customers have an expired KYC?",
        "Total NPA outstanding by loan type",
        "Monthly UPI debit volume in 2026",
        "Customers with more than 2 active accounts",
    ]
    for ex in examples:
        if st.button(ex, key=ex):
            st.session_state.pending = ex

if "history" not in st.session_state:
    st.session_state.history = []

if not os.path.exists(db_path):
    st.error(f"Database not found at `{db_path}`. Run `python seed_db.py` first.")
    st.stop()

# replay history
for item in st.session_state.history:
    with st.chat_message("user"):
        st.write(item["question"])
    with st.chat_message("assistant"):
        st.code(item["sql"], language="sql")
        if item["df"] is not None:
            st.dataframe(item["df"], use_container_width=True)
            if item.get("summary"):
                st.write(item["summary"])
        else:
            st.error(item["error"])

question = st.chat_input("e.g. Which cities have the highest loan outstanding?") or st.session_state.pop("pending", None)

if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                sql, df, error = generate_and_run(question, st.session_state.history, host, model, db_path, max_rows)
            except requests.RequestException as e:
                st.error(f"Ollama request failed: {e}")
                st.stop()
        st.code(sql, language="sql")
        summary = None
        if df is not None:
            st.dataframe(df, use_container_width=True)
            st.caption(f"{len(df)} row(s)")
            numeric = df.select_dtypes("number").columns
            if len(df) > 1 and len(numeric) >= 1 and len(df.columns) >= 2:
                with st.expander("Chart"):
                    st.bar_chart(df.set_index(df.columns[0])[numeric[0]])
            if summarize and not df.empty:
                with st.spinner("Summarizing..."):
                    summary = chat(host, model, [
                        {"role": "system", "content": "Summarize query results for a bank manager in 2-3 sentences. Use only the data given."},
                        {"role": "user", "content": f"Question: {question}\nResults (first 30 rows):\n{df.head(30).to_csv(index=False)}"},
                    ], temperature=0.2)
                st.write(summary)
        else:
            st.error(error)
        st.session_state.history.append(
            {"question": question, "sql": sql, "df": df, "error": error, "summary": summary})
