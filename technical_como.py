import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
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
except Exception:
    st.error("❌ Database connection failed. Please check credentials.")
    st.stop()

# --- Load Data ---
@st.cache_data
def load_data():
    # --- MODIFIED QUERY ---
    # Simplified the query to remove the unnecessary join to 'component'
    # and fixed the join to 'alarm' to be more specific.
    query = """
        SELECT 
            d.date,
            d.equipment_name,
            d.point_measurement,
            d.value,
            d.key,
            d.status,
            d.note,
            d.equipment_tag_id,
            d.technology,
            d.component,
            d.unit,
            a.alarm_standard,
            a.parameter,
            a.excellent,
            a.acceptable,
            a.requires_evaluation,
            a.unacceptable,
            a.al_set,
            a.load_kw
        FROM data d
        LEFT JOIN alarm a ON d.alarm_standard = a.alarm_standard AND d.key = a.key
        WHERE d.value IS NOT NULL;
    """
    return pd.read_sql(query, conn)

df = load_data()

if df.empty:
    st.warning("⚠️ No data available in database.")
    st.stop()

# Ensure 'date' column is in datetime format for proper sorting and plotting
df['date'] = pd.to_datetime(df['date'])

# --- Filtering ---
st.title("Equipment Monitoring Dashboard")
col1, col2, col3 = st.columns(3)

with col1:
    selected_equipment = st.selectbox("Select Equipment", df["equipment_name"].dropna().unique())

# Filter dataframe based on selected equipment
equipment_df = df[df["equipment_name"] == selected_equipment]

with col2:
    comp_options = equipment_df["component"].dropna().unique()
    selected_component = st.selectbox("Select Component", comp_options)

# Filter dataframe based on selected component
component_df = equipment_df[equipment_df["component"] == selected_component]

with col3:
    pm_options = component_df["point_measurement"].dropna().unique()
    selected_pms = st.multiselect("Select Point Measurement", pm_options)

# Final filtered dataframe for plotting and tables
plot_df = df[df["point_measurement"].isin(selected_pms)].copy()

# --- Graph ---
st.header("📈 Trend Analysis")
if not plot_df.empty:
    # Sort data by date to ensure the line chart connects points correctly
    plot_df = plot_df.sort_values(by="date")

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
    st.header("📑 Historical Data")
    
    # --- MODIFIED COLUMNS ---
    # Updated this list to match your exact request.
    historical_cols = [
        "point_measurement",
        "date",
        "value",
        "unit",
        "status",
        "note",
    ]
    # Filter the dataframe to only include the requested columns
    hist_df = plot_df[[c for c in historical_cols if c in plot_df.columns]].copy()

    # Format the date to be more readable in the table
    hist_df['date'] = hist_df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')

    def color_status(val):
        if val is None:
            return ""
        val = str(val).lower()
        if val == "excellent":
            return "background-color: rgba(0, 128, 0, 0.7); color: white;"
        elif val == "acceptable":
            return "background-color: rgba(144, 238, 144, 0.7); color: black;"
        elif val == "requires evaluation":
            return "background-color: rgba(255, 255, 0, 0.7); color: black;"
        elif val == "unacceptable":
            return "background-color: rgba(255, 0, 0, 0.7); color: white;"
        return ""

    st.dataframe(
        hist_df.style.applymap(color_status, subset=["status"]),
        use_container_width=True
    )

    # --- Alarm Data Table ---
    st.header("📊 Alarm Data")
    expected_alarm_cols = [
        "point_measurement",
        "alarm_standard",
        "parameter",
        "excellent",
        "acceptable",
        "requires_evaluation",
        "unacceptable",
    ]
    alarm_df = plot_df[expected_alarm_cols].drop_duplicates().copy()
    st.dataframe(alarm_df, use_container_width=True)

else:
    st.info("ℹ️ Select at least one Point Measurement to display data.")
