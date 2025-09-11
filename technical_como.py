import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from st_aggrid import AgGrid, GridOptionsBuilder
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

except Exception:
    st.error("❌ Database connection failed!")
    st.code(traceback.format_exc())
    st.stop()


# --- 2. Load Data ---
@st.cache_data
def load_data():
    # --- CHANGE 1: Added 'note' to the SQL query ---
    # The 'note' column is now fetched from the database.
    query = """
        SELECT 
            equipment_tag_id,
            equipment_name,
            technology,
            component,
            key,
            alarm_standard,
            date,
            point_measurement,
            value,
            unit,
            status,
            note 
        FROM data
        WHERE value IS NOT NULL
        ORDER BY date;
    """
    return pd.read_sql(query, connection)

try:
    df = load_data()
    # Best practice: Ensure the date column is in datetime format for accurate plotting
    df['date'] = pd.to_datetime(df['date'])
    
except Exception:
    st.error("❌ Could not load data.")
    st.code(traceback.format_exc())
    st.stop()

st.subheader("📊 Technical Condition Monitoring Dashboard")
st.caption("Filter from Equipment → Component → Point Measurement")

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

    # add unit to legend labels for clarity
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

    # --- 5. Table of selected measurements ---
    st.markdown("### 📋 Historical Data")
    
    # --- CHANGE 2: Updated the list of columns for the table ---
    # This list now exactly matches your request.
    columns_for_table = [
        "point_measurement", 
        "date", 
        "value",  
        "unit", 
        "status", 
        "note"
    ]
    table_df = plot_df[columns_for_table].copy()
    
    # Format date for better readability in the table
    table_df['date'] = table_df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')


    # Set up AgGrid with conditional formatting
    gb = GridOptionsBuilder.from_dataframe(table_df)
    gb.configure_pagination(enabled=True, paginationAutoPageSize=True)
    gb.configure_default_column(resizable=True, filter=True, sortable=True)

    # Custom JS code for cell style based on 'status' value
    cell_style_jscode = """
    function(params) {
        if (params.value === 'Excellent' || params.value === 'excellent') {
            return { 'backgroundColor': 'rgba(0,128,0,0.7)', 'color': 'white' };
        } else if (params.value === 'Acceptable' || params.value === 'acceptable') {
            return { 'backgroundColor': 'rgba(144,238,144,0.7)', 'color': 'black' };
        } else if (params.value === 'Requires Evaluation' || params.value === 'requires evaluation') {
            return { 'backgroundColor': 'rgba(255,255,0,0.7)', 'color': 'black' };
        } else if (params.value === 'Unacceptable' || params.value === 'unacceptable') {
            return { 'backgroundColor': 'rgba(255,0,0,0.7)', 'color': 'white' };
        }
    }
    """
    gb.configure_column("status", cellStyle=cell_style_jscode)

    grid_options = gb.build()

    AgGrid(table_df, gridOptions=grid_options, fit_columns_on_grid_load=True, theme='streamlit')

else:
    st.info("👆 Please select one or more measurement points to see the trend.")
