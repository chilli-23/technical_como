import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import traceback

# --- Page Configuration ---
st.set_page_config(layout="wide")

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
    connection = engine.connect()
except Exception as e:
    st.error("❌ Database connection failed. Please check your credentials in secrets.toml.")
    st.code(traceback.format_exc())
    st.stop()

# --- Data Loading Function ---
@st.cache_data(ttl=600)
def load_data():
    """Loads data, converting the 'date' column and handling potential errors."""
    try:
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
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        return df
    except Exception as e:
        st.error("❌ Failed to load data from the database.")
        st.code(traceback.format_exc())
        return pd.DataFrame()

# Load data and stop if it's empty
df = load_data()
if df.empty:
    st.warning("⚠️ No data available to display.")
    st.stop()

# --- Main Dashboard ---
st.title("📊 Technical Condition Monitoring Dashboard")
st.caption("Filter from Equipment → Component → Point Measurement to display the trend graph and historical data.")

# --- Horizontal Filters ---
col1, col2, col3 = st.columns(3)

with col1:
    equipment_choice = st.selectbox(
        "Equipment",
        options=sorted(df["equipment_name"].dropna().unique())
    )

filtered_by_eq = df[df["equipment_name"] == equipment_choice]

with col2:
    component_choice = st.selectbox(
        "Component",
        options=sorted(filtered_by_eq["component"].dropna().unique())
    )

component_df = filtered_by_eq[filtered_by_eq["component"] == component_choice]

with col3:
    point_choices = st.multiselect(
        "Measurement Point(s)",
        options=sorted(component_df["point_measurement"].dropna().unique())
    )

# --- Display Area: Graph and Tables ---
if point_choices:
    filtered_df = component_df[component_df["point_measurement"].isin(point_choices)].copy()
    
    # --- Trend Graph Section ---
    st.subheader(f"Trend for: {equipment_choice} → {component_choice}")
    plot_df = filtered_df.sort_values(by="date")

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
    
    # --- CHANGE 1: Function with Updated, Bolder Colors at 70% Visibility ---
    def color_status(val):
        """Applies bolder background colors to cells based on the 'status' column."""
        val_lower = str(val).lower()
        if "excellent" in val_lower:
            # Dark Green
            return "background-color: rgba(0, 128, 0, 0.7); color: white;"
        elif "acceptable" in val_lower:
            # Lime Green (less pastel)
            return "background-color: rgba(50, 205, 50, 0.7); color: black;"
        elif "requires evaluation" in val_lower:
            # Orange (stronger warning color)
            return "background-color: rgba(255, 165, 0, 0.7); color: black;"
        elif "unacceptable" in val_lower:
            # Bright Red
            return "background-color: rgba(255, 0, 0, 0.7); color: white;"
        return ""

    # --- CHANGE 2: Loop to Create a Separate Table for Each Selected Point ---
    st.header("Historical Data for Selected Points")
    
    # Sort the selected points alphabetically for consistent order
    for point in sorted(point_choices):
        st.subheader(f"History for: {point}")
        
        # Create a smaller dataframe for just the current point in the loop
        point_df = filtered_df[filtered_df['point_measurement'] == point]
        
        table_columns = ["date", "value", "status", "note"]
        historical_df = point_df[table_columns].sort_values(by="date", ascending=False)
        
        # Display the styled dataframe for this specific point
        st.dataframe(
            historical_df.style.applymap(color_status, subset=['status']),
            use_container_width=True,
            hide_index=True
        )
        st.markdown("---") # Add a visual separator between tables

else:
    st.info("ℹ️ Select one or more measurement points to display the trend graph and historical data.")
