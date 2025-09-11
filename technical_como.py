import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import traceback

# --- 1. Database Connection Setup ---
try:
    DB_HOST = st.secrets["database"]["host"]
    DB_PORT = st.secrets["database"]["port"]
    DB_NAME = st.secrets["database"]["dbname"]
    DB_USER = st.secrets["database"]["user"]
    DB_PASS = st.secrets["database"]["password"]

    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_pre_ping=True,
    )
    connection = engine.connect()
    st.success("✅ Connected to database!")

except Exception as e:
    st.error("❌ Database connection failed!")
    st.code(traceback.format_exc())
    st.stop()

# --- 2. Load Data Table ---
try:
    query = """
        SELECT *
        FROM data
        LIMIT 200;  -- just to avoid loading huge dataset
    """
    df = pd.read_sql(query, connection)

    st.subheader("📊 Data Table Preview")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error("❌ Could not load data table.")
    st.code(traceback.format_exc())
