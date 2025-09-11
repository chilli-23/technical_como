import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from st_aggrid import AgGrid, JsCode
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
    query = """
        SELECT 
            d.date, d.equipment_name, d.component, d.point_measurement,
            d.value, d.unit, d.status, d.technology, d.key, d.note,
            d.equipment_tag_id, d.alarm_standard
        FROM data d
        WHERE d.value IS NOT NULL
        ORDER BY d.date;
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


# --- 3. Filters ---
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


# --- 4. Graph ---
if point_choices:
    plot_df = filtered_comp[filtered_comp["point_measurement"].isin(point_choices)].copy()

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

    # --- 5. Historical Data Table (AgGrid) ---
    st.subheader("📑 Historical Data")
    hist_df = plot_df[
        [
            "point_measurement",
            "technology",
            "key",
            "date",
            "value",
            "unit",
            "status",
            "note",
        ]
    ].copy()

    # Conditional formatting for status
    status_color_js = JsCode("""
    function(params) {
        if (params.value == 'excellent') {
            return {'color': 'white', 'backgroundColor': 'rgba(0,128,0,0.8)'};
        } else if (params.value == 'acceptable') {
            return {'color': 'black', 'backgroundColor': 'rgba(144,238,144,0.8)'};
        } else if (params.value == 'requires evaluation') {
            return {'color': 'black', 'backgroundColor': 'rgba(255,255,0,0.8)'};
        } else if (params.value == 'unacceptable') {
            return {'color': 'white', 'backgroundColor': 'rgba(255,0,0,0.8)'};
        }
        return null;
    }
    """)

    AgGrid(
        hist_df,
        height=300,
        theme="balham",
        enable_enterprise_modules=False,
        fit_columns_on_grid_load=True,
        custom_css={".ag-cell": {"line-height": "20px", "padding": "4px"}},
        columns_auto_size_mode="FIT_CONTENTS",
        key="hist_table",
        update_mode="NO_UPDATE",
        allow_unsafe_jscode=True,
        gridOptions={
            "getRowStyle": status_color_js,
        },
    )

    # --- 6. Alarm Info Table (AgGrid) ---
    st.subheader("🚨 Alarm Settings")
    query_alarm = f"""
        SELECT a.alarm_standard, a.parameter, a.excellent, a.acceptable,
               a.requires_evaluation, a.unacceptable, a.al_set, a.load_kw
        FROM alarm a
        WHERE a.alarm_standard IN (
            SELECT DISTINCT alarm_standard
            FROM data
            WHERE point_measurement = ANY(ARRAY{point_choices})
        );
    """
    try:
        alarm_df = pd.read_sql(query_alarm, connection)
        AgGrid(
            alarm_df,
            height=250,
            theme="balham",
            enable_enterprise_modules=False,
            fit_columns_on_grid_load=True,
            key="alarm_table",
        )
    except Exception:
        st.warning("⚠️ No alarm info available for the selected points.")

else:
    st.info("👆 Please select one or more measurement points to see the trend.")
