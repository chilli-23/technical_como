import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
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

except Exception:
    st.error("❌ Database connection failed!")
    st.code(traceback.format_exc())
    st.stop()


# --- 2. Load Data ---
@st.cache_data
def load_data():
    query = """
        SELECT date, equipment_name, component, point_measurement, value, unit
        FROM data
        WHERE value IS NOT NULL
        ORDER BY date;
    """
    return pd.read_sql(query, connection)

try:
    df = load_data()
    st.subheader("📊 Technical Condition Monitoring Dashboard")
    st.caption("Filter from Equipment → Component → Point Measurement")

except Exception:
    st.error("❌ Could not load data.")
    st.code(traceback.format_exc())
    st.stop()


# --- 3. Filters (horizontal layout) ---
col1, col2, col3 = st.columns(3)

with col1:
    equipments = df["equipment_name"].dropna().unique()
    equipment_choice = st.selectbox("Equipment", options=sorted(equipments))

filtered_eq = df[df["equipment_name"] == equipment_choice]

with col2:
    components = filtered_eq["component"].dropna().unique()
    component_choice = st.selectbox("Component", options=sorted(components))

filtered_comp = filtered_eq[filtered_eq["component"] == component_choice]

with col3:
    points = filtered_comp["point_measurement"].dropna().unique()
    point_choices = st.multiselect("Measurement Point(s)", options=sorted(points))


# --- 4. Plot only if points selected ---
if point_choices:
    plot_df = filtered_comp[filtered_comp["point_measurement"].isin(point_choices)].copy()

    # add unit to legend labels
    plot_df["point_with_unit"] = (
        plot_df["point_measurement"] + " (" + plot_df["unit"].astype(str) + ")"
    )

    fig = px.line(
        plot_df,
        x="date",
        y="value",
        color="point_with_unit",
        markers=True,
        title=f"Trend for {equipment_choice} - {component_choice}",
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Value",
        legend_title="Measurement Point",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👆 Please select one or more measurement points to see the trend.")
