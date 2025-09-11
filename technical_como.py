import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import traceback

# --- Page Configuration ---
st.set_page_config(layout="wide")

# --- Database Connection (RESTORED TO YOUR ORIGINAL METHOD) ---
try:
    DB_HOST = st.secrets["database"]["host"]
    DB_PORT = st.secrets["database"]["port"]
    DB_NAME = st.secrets["database"]["dbname"]
    DB_USER = st.secrets["database"]["user"]
    DB_PASS = st.secrets["database"]["password"]

    engine = create_engine(
        f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    connection = engine.connect()
except Exception as e:
    st.error("❌ Database connection failed. Please check your credentials in secrets.toml.")
    st.code(traceback.format_exc())
    st.stop()

# --- Data Loading Function ---
@st.cache_data(ttl=600) # Cache data for 10 minutes
def load_data():
    """Loads data from the database and converts date column."""
    try:
        # Simplified query to only get necessary columns
        query = """
            SELECT 
                equipment_name,
                component,
                point_measurement,
                date,
                value,
                status,
                note
            FROM data
            WHERE value IS NOT NULL
        """
        df = pd.read_sql(query, connection)
        
        # Convert 'date' column, coercing errors to NaT (Not a Time)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        
        # Drop rows where date conversion failed
        df.dropna(subset=['date'], inplace=True)
        
        return df
    except Exception as e:
        st.error("❌ Failed to load data from the database.")
        st.code(traceback.format_exc())
        return pd.DataFrame() # Return empty dataframe on error

# Load the data
df = load_data()

if df.empty:
    st.warning("⚠️ No data available to display.")
    st.stop()

# --- Main Dashboard ---
st.title("📊 Technical Condition Monitoring Dashboard")
st.caption("Filter by Equipment, then Component, then select points to plot in the Trend Analysis tab.")

# --- Sidebar Filters ---
st.sidebar.header("Filters")
equipment_choice = st.sidebar.selectbox(
    "1. Select Equipment",
    options=sorted(df["equipment_name"].dropna().unique())
)

filtered_by_eq = df[df["equipment_name"] == equipment_choice]

component_choice = st.sidebar.selectbox(
    "2. Select Component",
    options=sorted(filtered_by_eq["component"].dropna().unique())
)

# This is the main dataframe for the selected component
component_df = filtered_by_eq[filtered_by_eq["component"] == component_choice]

point_choices = st.sidebar.multiselect(
    "3. Select Measurement Point(s) to Plot",
    options=sorted(component_df["point_measurement"].dropna().unique())
)

# --- Tabbed Layout for Graph and Table ---
tab1, tab2 = st.tabs(["Trend Analysis 📈", "Historical Data 📋"])

## --- Tab 1: Trend Analysis Graph ---
with tab1:
    st.subheader(f"Trend for: {equipment_choice} → {component_choice}")
    
    if not point_choices:
        st.info("ℹ️ Select one or more measurement points from the sidebar to plot the trend.")
    else:
        plot_df = component_df[component_df["point_measurement"].isin(point_choices)].copy()
        plot_df = plot_df.sort_values(by="date")

        fig = px.line(
            plot_df,
            x="date",
            y="value",
            color="point_measurement",
            markers=True,
            title="Selected Measurement Points Trend"
        )
        fig.update_layout(legend_title="Measurement Point", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

## --- Tab 2: Historical Data Table ---
with tab2:
    st.subheader(f"Complete Historical Data for: {component_choice}")

    table_columns = ["point_measurement", "date", "value", "status", "note"]
    historical_df = component_df[table_columns].copy()
    historical_df = historical_df.sort_values(by="date", ascending=False)
    
    def color_status(val):
        val_lower = str(val).lower()
        if "excellent" in val_lower:
            return "background-color: rgba(0, 128, 0, 0.7); color: white;"
        elif "acceptable" in val_lower:
            return "background-color: rgba(144, 238, 144, 0.7); color: black;"
        elif "requires evaluation" in val_lower:
            return "background-color: rgba(255, 255, 0, 0.7); color: black;"
        elif "unacceptable" in val_lower:
            return "background-color: rgba(255, 0, 0, 0.7); color: white;"
        return ""

    st.dataframe(
        historical_df.style.applymap(color_status, subset=['status']),
        use_container_width=True,
        hide_index=True
    )
