import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
import traceback
import openpyxl 

# --- Page Configuration ---
st.set_page_config(layout="wide", initial_sidebar_state="expanded")

# --- Database Connection ---
@st.cache_resource
def get_engine():
    """Creates a cached database engine."""
    try:
        DB_HOST = st.secrets["database"]["host"]
        DB_PORT = st.secrets["database"]["port"]
        DB_NAME = st.secrets["database"]["dbname"]
        DB_USER = st.secrets["database"]["user"]
        DB_PASS = st.secrets["database"]["password"]
        return create_engine(
            f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
            poolclass=NullPool
        )
    except Exception as e:
        st.error("❌ Database connection failed. Please check your credentials in secrets.toml.")
        st.code(traceback.format_exc())
        return None

engine = get_engine()
if engine is None:
    st.stop()

# --- Data Loading Function ---
@st.cache_data(ttl=600)
def load_data():
    """Loads and caches data from the database for the dashboard."""
    try:
        with engine.connect() as connection:
            query = """
                SELECT 
                    d.equipment_tag_id, d.equipment_name, d.component, d.point_measurement,
                    d.date, d.value, d.unit, d.status, d.note, d.alarm_standard,
                    stds.excellent, stds.acceptable, stds.requires_evaluation, stds.unacceptable
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

# --- Sidebar for Navigation ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Choose a page", ["Monitoring Dashboard", "Upload New Data", "Database Viewer"])

# --- ==================================================================== ---
# ---                             PAGE 1: DASHBOARD                        ---
# --- ==================================================================== ---
if page == "Monitoring Dashboard":
    st.title("📊 Technical Condition Monitoring Dashboard")
    
    # Load data for the dashboard
    df = load_data()
    if df.empty:
        st.warning("⚠️ No data available to display.")
        st.stop()

    # --- Horizontal Filters for Dashboard ---
    st.subheader("Filters")
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
        
        st.header(f"Results for: {equipment_choice} → {component_choice}")
        
        professional_color_palette = [
            '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
            '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52'
        ]
        
        unique_points = sorted(filtered_df['point_measurement'].unique())
        color_map = {point: professional_color_palette[i % len(professional_color_palette)] for i, point in enumerate(unique_points)}

        # Trend Graph
        plot_df = filtered_df.sort_values(by="date")
        fig = px.line(
            plot_df, x="date", y="value", color="point_measurement", markers=True,
            title="Selected Measurement Points Trend",
            color_discrete_map=color_map
        )
        fig.update_layout(legend_title="Measurement Point", hovermode="x unified")
        
        # --- Add annotations for notes ---
        notes_df = plot_df.dropna(subset=['note'])
        notes_df = notes_df[~notes_df['note'].astype(str).str.strip().isin(['', '-'])]
        
        for index, row in notes_df.iterrows():
            point_name = str(row['point_measurement']).strip()
            line_color = color_map.get(point_name)
            
            solid_color = 'rgb(200, 200, 200)' 
            transparent_color = 'rgba(200, 200, 200, 0.5)' 
            
            if line_color:
                r, g, b = tuple(int(line_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
                solid_color = f'rgb({r}, {g}, {b})'
                transparent_color = f'rgba({r}, {g}, {b}, 0.5)'

            fig.add_shape(
                type="line", x0=row['date'], y0=0, x1=row['date'], y1=1,
                yref='paper', line=dict(color=transparent_color, width=1, dash="dot")
            )
            fig.add_annotation(
                x=row['date'], y=1.05, yref='paper',
                text=f"{row['note']}<br><b>({row['point_measurement']})</b>",
                showarrow=False, font=dict(size=10, color=solid_color),
                xanchor="center", align="center"
            )
        
        st.plotly_chart(fig, use_container_width=True)

        # Alarm Standards Table
        st.subheader("Alarm Standards")
        alarm_cols = ["point_measurement", "equipment_tag_id", "alarm_standard", "excellent", "acceptable", "requires_evaluation", "unacceptable", "unit"]
        alarm_df = filtered_df[alarm_cols].drop_duplicates()
        alarm_df = alarm_df.reset_index(drop=True)
        alarm_df.index = range(1, len(alarm_df) + 1)
        st.dataframe(
            alarm_df, 
            use_container_width=True, 
            hide_index=False,
            column_config={
                "point_measurement": st.column_config.TextColumn(width="medium"),
                "equipment_tag_id": st.column_config.TextColumn(width="medium"),
                "alarm_standard": st.column_config.TextColumn(width="medium"),
                "excellent": st.column_config.TextColumn(width="small"),
                "acceptable": st.column_config.TextColumn(width="small"),
                "requires_evaluation": st.column_config.TextColumn(width="small"),
                "unacceptable": st.column_config.TextColumn(width="small"),
                "unit": st.column_config.TextColumn(width="small"),
            }
        )
        
        def color_status(val):
            val_lower = str(val).lower()
            if "excellent" in val_lower: return "background-color: rgba(0, 128, 0, 0.7); color: white;"
            elif "acceptable" in val_lower: return "background-color: rgba(50, 205, 50, 0.7); color: black;"
            elif "requires evaluation" in val_lower: return "background-color: rgba(255, 165, 0, 0.7); color: black;"
            elif "unacceptable" in val_lower: return "background-color: rgba(255, 0, 0, 0.7); color: white;"
            return ""

        # Historical Data Tables
        st.header("Detailed Historical Data")
        for point in sorted(point_choices):
            st.subheader(f"History for: {point}")
            point_df = filtered_df[filtered_df['point_measurement'] == point]
            hist_cols = ["date", "value", "unit", "status", "note"]
            historical_df = point_df[hist_cols].sort_values(by="date", ascending=False)
            historical_df['date'] = historical_df['date'].dt.strftime('%Y-%m-%d')
            
            historical_df = historical_df.reset_index(drop=True)
            historical_df.index = range(1, len(historical_df) + 1)
            
            st.dataframe(
                historical_df.style.format({'value': '{:g}'}).applymap(color_status, subset=['status']),
                use_container_width=True, 
                hide_index=False,
                column_config={
                    "date": st.column_config.TextColumn(width="small"),
                    "value": st.column_config.TextColumn(width="small"),
                    "unit": st.column_config.TextColumn(width="small"),
                    "status": st.column_config.TextColumn(width="medium"),
                    "note": st.column_config.TextColumn(width="large"),
                }
            )
            st.markdown("---")
    else:
        st.info("ℹ️ Please select one or more measurement points from the filters above to see the data.")

# --- ==================================================================== ---
# ---                          PAGE 2: UPLOAD DATA                         ---
# --- ==================================================================== ---
elif page == "Upload New Data":
    st.title("⬆️ Upload New Data")
    st.write("Use this page to add new records to the database tables from a CSV or XLSX file.")
    
    # --- Uploader UI ---
    table_options = ["data", "alarm_standards", "equipment", "alarm"]
    target_table = st.selectbox("1. Select table to add data to", options=table_options)

    uploaded_file = st.file_uploader("2. Choose a file", type=["csv", "xlsx"])

    if st.button("3. Upload and Add Data"):
        if uploaded_file is not None and target_table is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    upload_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.xlsx'):
                    upload_df = pd.read_excel(uploaded_file, engine='openpyxl')
                else:
                    st.error("Unsupported file type. Please upload a CSV or XLSX file.")
                    st.stop()

                st.write("Preview of uploaded data:")
                st.dataframe(upload_df.head())

                # --- Safety Check 1: Validate Columns ---
                st.info(f"Checking columns for the '{target_table}' table...")
                with engine.connect() as connection:
                    db_cols_query = text(f"SELECT * FROM {target_table} LIMIT 0")
                    db_cols = pd.read_sql(db_cols_query, connection).columns.tolist()
                
                upload_cols = upload_df.columns.tolist()

                db_cols_set = set(db_cols)
                upload_cols_set = set(upload_cols)

                if upload_cols_set != db_cols_set:
                    st.error(f"Column Mismatch! The file columns do not match the '{target_table}' table.")
                    missing_cols = list(db_cols_set - upload_cols_set)
                    extra_cols = list(upload_cols_set - db_cols_set)
                    if missing_cols:
                        st.warning("**Columns missing from your file:**"); st.json(sorted(missing_cols))
                    if extra_cols:
                        st.warning("**Unexpected columns found in your file:**"); st.json(sorted(extra_cols))
                    st.info("For reference:")
                    st.write("**Full list of expected columns:**", sorted(db_cols))
                    st.write("**Full list of your file's columns:**", sorted(upload_cols))
                    st.stop()
                
                # --- THIS IS THE CHANGE: Safety Check 2: Check for duplicate primary keys ---
                # Assumes the unique key is 'identifier' for the 'data' table. Adjust if needed.
                unique_key = None
                if target_table == 'data':
                    unique_key = 'identifier'
                # Add other tables and their unique keys here if they also need this check
                # elif target_table == 'alarm_standards':
                #     unique_key = 'standard' 

                if unique_key and unique_key in upload_df.columns:
                    st.info(f"Checking for duplicate '{unique_key}' values...")
                    upload_ids = upload_df[unique_key].dropna().tolist()

                    if upload_ids:
                        with engine.connect() as connection:
                            query = text(f'SELECT "{unique_key}" FROM "{target_table}" WHERE "{unique_key}" IN :ids')
                            existing_ids_df = pd.read_sql(query, connection, params={'ids': tuple(upload_ids)})
                            existing_ids = set(existing_ids_df[unique_key])

                        duplicate_ids = [id for id in upload_ids if id in existing_ids]

                        if duplicate_ids:
                            st.error(f"Upload Failed: Found {len(duplicate_ids)} rows in your file where the '{unique_key}' already exists in the database.")
                            st.warning(f"The '{unique_key}' column must be unique for every record. Please remove or update the following rows in your file before trying again:")
                            st.json(sorted(list(set(duplicate_ids))))
                            st.stop()
                # --- End of change ---

                # --- Append data to the database ---
                st.info(f"All checks passed. Appending {len(upload_df)} rows to '{target_table}'...")
                with engine.connect() as connection:
                    upload_df.to_sql(target_table, con=connection, if_exists='append', index=False)
                
                st.success(f"✅ Successfully added {len(upload_df)} rows to the '{target_table}' table!")
                st.info("Clearing data cache... The dashboard will show the new data on its next load.")
                st.cache_data.clear()

            except Exception as upload_error:
                st.error("An error occurred during the upload process:")
                st.code(traceback.format_exc())
        else:
            st.warning("⚠️ Please select a table and upload a file first.")

# --- ==================================================================== ---
# ---                       PAGE 3: DATABASE VIEWER                        ---
# --- ==================================================================== ---
elif page == "Database Viewer":
    st.title("🗂️ Database Table Viewer")
    st.write("Select a table from the dropdown to view its entire contents.")

    # Dropdown to select the table
    table_options = ["data", "alarm_standards", "equipment", "alarm"]
    table_to_view = st.selectbox("Choose a table to display", options=table_options)

    if table_to_view:
        # A new function to fetch data from any table
        @st.cache_data(ttl=60) # Short cache for viewing raw data
        def view_table_data(table_name):
            try:
                with engine.connect() as connection:
                    if table_name not in table_options:
                        st.error("Invalid table selected.")
                        return pd.DataFrame()
                    query = text(f"SELECT * FROM {table_name}")
                    df = pd.read_sql(query, connection)
                    return df
            except Exception as e:
                st.error(f"Failed to load data from table '{table_name}'.")
                st.code(traceback.format_exc())
                return pd.DataFrame()
        
        # Fetch and display the data
        table_df = view_table_data(table_to_view)
        
        if not table_df.empty:
            st.info(f"Displaying {len(table_df)} rows from the '{table_to_view}' table.")
            table_df = table_df.reset_index(drop=True)
            table_df.index = range(1, len(table_df) + 1)
            st.dataframe(
                table_df, 
                use_container_width=True,
                column_config={
                    col: st.column_config.TextColumn(width="medium") for col in table_df.columns
                }
            )
        else:
            st.warning(f"The table '{table_to_view}' is empty or could not be loaded.")

