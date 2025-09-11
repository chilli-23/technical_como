import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px

# --- Database Connection ---
try:
    DB_HOST = st.secrets["database"]["host"]
    DB_PORT = st.secrets["database"]["port"]
    DB_NAME = st.secrets["database"]["dbname"]
    DB_USER = st.secrets["database"]["user"]
    DB_PASS = st.secrets["database"]["password"]

    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    conn = engine.connect()
except Exception as e:
    st.error("❌ Database connection failed. Please check credentials.")
    st.stop()

# --- Load Data ---
@st.cache_data
def load_data():
    query = """
        SELECT 
            d.date,
            d.equipment_name,
            d.component,
            d.point_measurement,
            d.value,
            d.key,
            d.status,
            d.note,
            d.equipment_tag_id,
            tc.technology,
            tc.unit,
            a.alarm_standard,
            a.parameter,
            a.excellent,
            a.acceptable,
            a.requires_evaluation,
            a.unacceptable,
            a.al_set,
            a.load_kw
        FROM data d
        LEFT JOIN component tc ON d.component = tc.component
        LEFT JOIN alarm a ON d.alarm_standard = a.alarm_standard
        WHERE d.value IS NOT NULL;
    """
    return pd.read_sql(query, conn)

df = load_data()

if df.empty:
    st.warning("⚠️ No data available in database.")
    st.stop()

# --- Filtering ---
col1, col2, col3 = st.columns(3)

with col1:
    selected_equipment = st.selectbox("Select Equipment", df["equipment_name"].dropna().unique())

with col2:
    comp_options = df[df["equipment_name"] == selected_equipment]["component"].dropna().unique()
    selected_component = st.selectbox("Select Component", comp_options)

with col3:
    pm_options = df[
        (df["equipment_name"] == selected_equipment) &
        (df["component"] == selected_component)
    ]["point_measurement"].dropna().unique()
    selected_pms = st.multiselect("Select Point Measurement", pm_options)

plot_df = df[df["point_measurement"].isin(selected_pms)].copy()

# --- Graph ---
if not plot_df.empty:
    plot_df["legend"] = plot_df["point_measurement"] + " [" + plot_df["unit"].astype(str) + "]"
    fig = px.line(
        plot_df,
        x="date",
        y="value",
        color="legend",
        markers=True,
        title="Trend of Selected Point Measurements"
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- Historical Data Table ---
    st.subheader("📑 Historical Data")
    expected_cols = [
        "point_measurement",
        "component",
        "technology",
        "key",
        "date",
        "value",
        "unit",
        "status",
        "note",
    ]
    hist_df = plot_df[[c for c in expected_cols if c in plot_df.columns]].copy()

    def color_status(val):
        if val is None:
            return ""
        val = str(val).lower()
        if val == "excellent":
            return "background-color: rgba(0, 128, 0, 0.8); color: white;"  # dark green
        elif val == "acceptable":
            return "background-color: rgba(144, 238, 144, 0.8); color: black;"  # light green
        elif val == "requires evaluation":
            return "background-color: rgba(255, 255, 0, 0.8); color: black;"  # yellow
        elif val == "unacceptable":
            return "background-color: rgba(255, 0, 0, 0.8); color: white;"  # red
        return ""

    st.dataframe(
        hist_df.style.applymap(color_status, subset=["status"])
    )

    # --- Alarm Data Table ---
    st.subheader("📊 Alarm Data")
    expected_alarm_cols = [
        "point_measurement",
        "equipment_tag_id",
        "alarm_standard",
        "parameter",
        "excellent",
        "acceptable",
        "requires_evaluation",
        "unacceptable",
        "al_set",
        "load_kw",
    ]
    alarm_df = plot_df[[c for c in expected_alarm_cols if c in plot_df.columns]].copy()
    st.dataframe(alarm_df)

else:
    st.info("ℹ️ Select at least one point_measurement to display data.")
