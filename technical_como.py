import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
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
    # Use a connection from the engine
    connection = engine.connect()
except Exception as e:
    st.error("❌ Database connection failed. Please check your credentials in secrets.toml.")
    st.code(traceback.format_exc())
    st.stop()

# --- Data Loading Function ---
@st.cache_data(ttl=600)
def load_data():
    """
    Loads data by joining the 'data' and 'alarm_standards' tables.
    """
    try:
        query = """
            SELECT 
                d.equipment_name,
                d.component,
                d.point_measurement,
                d.date,
                d.value,
                d.unit,
                d.status,
                d.note,
                d.alarm_standard,
                stds.excellent,
                stds.acceptable,
                stds.requires_evaluation,
                stds.unacceptable
            FROM data d
            LEFT JOIN alarm_standards stds ON d.alarm_standard = stds.standard
            WHERE d.value IS NOT NULL
        """
        df = pd.read_sql(query, connection)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df.dropna(subset=['date'], inplace=True)
        return df
    except Exception as e:
        st.error("❌ Failed to load data from the database.")
        st.code(traceback.format_exc())
        return pd.DataFrame()

# --- NEW FEATURE: UPLOAD DATA ---
with st.sidebar.expander("⬆️ Upload New Data"):
    # Define which tables the user is allowed to upload to
    table_options = ["data", "alarm_standards", "equipment", "alarm"]
    target_table = st.selectbox("1. Select table to add data to", options=table_options)

    uploaded_file = st.file_uploader("2. Choose a CSV file", type="csv")

    if st.button("3. Upload and Add Data"):
        if uploaded_file is not None and target_table is not None:
            try:
                # Read the uploaded CSV into a DataFrame
                csv_df = pd.read_csv(uploaded_file)
                st.write("Preview of uploaded data:")
                st.dataframe(csv_df.head())

                # --- Safety Check: Validate Columns ---
                st.info(f"Checking columns for the '{target_table}' table...")
                
                # Get the actual column names from the database table
                db_cols_query = text(f"SELECT * FROM {target_table} LIMIT 0")
                db_cols = pd.read_sql(db_cols_query, connection).columns.tolist()
                
                csv_cols = csv_df.columns.tolist()

                # Compare the column lists
                if set(csv_cols) != set(db_cols):
                    st.error(
                        f"Column Mismatch! The CSV columns do not match the '{target_table}' table."
                    )
                    st.write("**Expected Columns:**", db_cols)
                    st.write("**Your CSV Columns:**", csv_cols)
                    st.stop()

                # --- Append data to the database ---
                st.info(f"Columns match. Appending {len(csv_df)} rows to '{target_table}'...")
                csv_df.to_sql(target_table, con=engine, if_exists='append', index=False)
                
                # --- Success and Refresh ---
                st.success(f"✅ Successfully added {len(csv_df)} rows to the '{target_table}' table!")
                st.info("Clearing cache and refreshing the app to show new data...")
                
                # Clear the cache and rerun the app
                st.cache_data.clear()
                st.experimental_rerun()

            except Exception as upload_error:
                st.error(f"An error occurred during the upload process:")
                st.code(traceback.format_exc())
        else:
            st.warning("⚠️ Please select a table and upload a CSV file first.")

# --- Main Dashboard ---
st.title("📊 Technical Condition Monitoring Dashboard")
st.caption("Filter from Equipment → Component → Point Measurement to display the trend graph and related data.")

# Load data for the dashboard
df = load_data()
if df.empty:
    st.warning("⚠️ No data available to display.")
    st.stop()

# --- Horizontal Filters ---
col1, col2, col3 = st.columns(3)
with col1:
    equipment_choice = st.selectbox("Equipment", options=sorted(df["equipment_name"].dropna().unique()))
filtered_by_eq = df[df["equipment_name"] == equipment_choice]
with col2:
    component_choice = st.selectbox("Component", options=sorted(filtered_by_eq["component"].dropna().unique()))
component_df = filtered_by_eq[filtered_by_eq["component"] == component_choice]
with col3:
    point_choices = st.multiselect("Measurement Point(s)", options=sorted(component_df["point_measurement"].dropna().unique()))

# --- Display Area: Graph and Tables ---
if point_choices:
    filtered_df = component_df[component_df["point_measurement"].isin(point_choices)].copy()
    
    st.subheader(f"Trend for: {equipment_choice} → {component_choice}")
    plot_df = filtered_df.sort_values(by="date")
    fig = px.line(
        plot_df, x="date", y="value", color="point_measurement", markers=True,
        title="Selected Measurement Points Trend"
    )
    fig.update_layout(legend_title="Measurement Point", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Associated Alarm Standards for Selected Points")
    alarm_cols = [
        "point_measurement", "alarm_standard", "excellent", "acceptable", 
        "requires_evaluation", "unacceptable", "unit"
    ]
    alarm_df = filtered_df[alarm_cols].drop_duplicates()
    st.dataframe(alarm_df, use_container_width=True, hide_index=True)
    
    def color_status(val):
        val_lower = str(val).lower()
        if "excellent" in val_lower: return "background-color: rgba(0, 128, 0, 0.7); color: white;"
        elif "acceptable" in val_lower: return "background-color: rgba(50, 205, 50, 0.7); color: black;"
        elif "requires evaluation" in val_lower: return "background-color: rgba(255, 165, 0, 0.7); color: black;"
        elif "unacceptable" in val_lower: return "background-color: rgba(255, 0, 0, 0.7); color: white;"
        return ""

    st.header("Detailed Historical Data")
    for point in sorted(point_choices):
        st.subheader(f"History for: {point}")
        point_df = filtered_df[filtered_df['point_measurement'] == point]
        hist_cols = ["date", "value", "unit", "status", "note"]
        historical_df = point_df[hist_cols].sort_values(by="date", ascending=False)
        historical_df['date'] = historical_df['date'].dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            historical_df.style.format({'value': '{:g}'}).applymap(color_status, subset=['status']),
            use_container_width=True, 
            hide_index=True
        )
        st.markdown("---")

else:
    st.info("ℹ️ Select one or more measurement points to display the trend graph and historical data.")

# Close the connection when the script finishes
connection.close()
