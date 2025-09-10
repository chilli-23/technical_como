import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import traceback

# --- 1. Database Connection Setup ---
# Securely load credentials from Streamlit's secrets management
try:
    DB_HOST = st.secrets["database"]["host"]
    DB_PORT = st.secrets["database"]["port"]
    DB_NAME = st.secrets["database"]["dbname"]
    DB_USER = st.secrets["database"]["user"]
    DB_PASS = st.secrets["database"]["password"]

    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(conn_str)
except Exception as e:
    st.error(f"Error creating database engine. Please check your secrets configuration. Details: {e}")
    st.stop()


# --- 2. Data Loading Function ---
@st.cache_data
def load_master_data():
    """
    Loads and joins data from the 'data', 'component', and 'alarm' tables.
    This creates a single master DataFrame for the entire application.
    """
    query = text("""
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
            a.excellent,
            a.acceptable,
            a.requires_evaluation,
            a.unacceptable
        FROM 
            data d
        LEFT JOIN 
            component tc ON d.point_measurement = tc.point
        LEFT JOIN 
            alarm a ON d.alarm_standard = a.alarm_standard
        WHERE 
            d.value IS NOT NULL;
    """)
    
    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception:
        st.error("Fatal Error: Could not execute the master SQL query.")
        st.error("Please check that 'data', 'component', and 'alarm' tables exist and have the correct columns for joining.")
        st.code(traceback.format_exc())
        return None


# --- 3. Main Application ---
def main():
    st.set_page_config(layout="wide")
    st.title(" Technical Condition Monitoting Dashboard")
    st.markdown("Use the filters below to drill down from an equipment to a specific measurement point.")

    df = load_master_data()

    if df is None or df.empty:
        st.warning("No data was loaded. Please check the database connection and table structures.")
        return

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        equipment_list = sorted(df['equipment_name'].unique())
        selected_equipment = st.selectbox(
            label="1. Select Equipment", options=equipment_list, index=0,
            help="Choose the equipment to analyze."
        )

    with col2:
        if selected_equipment:
            tech_df = df[df['equipment_name'] == selected_equipment]
            tech_list = sorted(tech_df['technology'].dropna().unique())
            selected_technology = st.selectbox(
                label="2. Select Technology", options=tech_list,
                help="The technology associated with the measurement."
            )
        else:
            selected_technology = st.selectbox("2. Select Technology", [], disabled=True)

    with col3:
        if selected_equipment and selected_technology:
            point_df = df[(df['equipment_name'] == selected_equipment) & (df['technology'] == selected_technology)]
            point_list = sorted(point_df['point_measurement'].unique())
            selected_points = st.multiselect(
                label="3. Select Measurement Point(s)", options=point_list,
                help="Select one or more points to plot."
            )
        else:
            selected_points = st.multiselect("3. Select Measurement Point(s)", [], disabled=True)

    st.divider()

    if selected_equipment and selected_technology and selected_points:
        filtered_df = df[(df['equipment_name'] == selected_equipment) & (df['technology'] == selected_technology) & (df['point_measurement'].isin(selected_points))].sort_values(by='date')

        if not filtered_df.empty:
            filtered_df['legend_label'] = filtered_df['point_measurement'] + ' (' + filtered_df['unit'].astype(str) + ')'
            st.subheader(f"Vibration Trend for: {selected_equipment}")
            
            fig = px.line(filtered_df, x='date', y='value', color='legend_label', markers=True, labels={"date": "Date", "value": "Vibration Value", "legend_label": "Point (Unit)"})
            fig.update_traces(marker=dict(size=8, symbol="circle"), line=dict(width=3))
            st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Alarm Standards for Selected Points")
            alarm_cols = ['point_measurement', 'equipment_tag_id', 'alarm_standard', 'excellent', 'acceptable', 'requires_evaluation', 'unacceptable', 'unit']
            alarm_standards_df = filtered_df[alarm_cols].drop_duplicates().reset_index(drop=True)
            alarm_standards_df.rename(columns={'point_measurement': 'Point Measurement', 'equipment_tag_id': 'Tag ID', 'alarm_standard': 'Alarm Standard', 'excellent': 'Excellent', 'acceptable': 'Acceptable', 'requires_evaluation': 'Requires Evaluation', 'unacceptable': 'Unacceptable', 'unit': 'Unit'}, inplace=True)
            
            def style_alarm_columns(s, column_styles):
                return [column_styles.get(s.name, '')] * len(s)

            column_styles = {'Excellent': 'background-color: rgba(0, 100, 0, 0.6)', 'Acceptable': 'background-color: rgba(144, 238, 144, 0.6)', 'Requires Evaluation': 'background-color: rgba(255, 255, 0, 0.6)', 'Unacceptable': 'background-color: rgba(255, 0, 0, 0.6)'}
            styled_alarm_df = alarm_standards_df.style.apply(style_alarm_columns, column_styles=column_styles, axis=0)
            st.dataframe(styled_alarm_df, use_container_width=True, hide_index=True)

            for point in selected_points:
                st.subheader(f"Data Details for: {point}")
                point_df = filtered_df[filtered_df['point_measurement'] == point].sort_values(by='date', ascending=False)
                display_cols = ['point_measurement', 'equipment_tag_id', 'component', 'key', 'alarm_standard', 'date', 'value', 'unit', 'status', 'note']
                table_df_to_display = point_df[display_cols].copy()
                
                for col in ['alarm_standard', 'status', 'note']:
                    table_df_to_display[col].fillna('Unavailable', inplace=True)
                
                table_df_to_display.rename(columns={'component': 'Component', 'key': 'Key', 'alarm_standard': 'Alarm Standard', 'date': 'Date', 'point_measurement': 'Point Measurement', 'equipment_tag_id': 'Tag ID', 'value': 'Value', 'unit': 'Unit', 'status': 'Status', 'note': 'Note'}, inplace=True)
                table_df_to_display['Date'] = table_df_to_display['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
                st.dataframe(table_df_to_display, use_container_width=True, hide_index=True)
        else:
            st.warning("No data found for the specific combination of filters.")

if __name__ == "__main__":
    main()


