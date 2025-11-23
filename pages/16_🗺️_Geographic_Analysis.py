import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from utils.auth_helper import render_client_selector, get_context_credentials
from connectors.google_ads import GoogleAdsConnector
from utils.currency import format_currency

# Page Config
st.set_page_config(page_title="Geographic Analysis", page_icon="🗺️", layout="wide")

# --- Top-Level Filters ---
st.title("🗺️ Geographic Performance")
st.markdown("Analyze performance by City and State directly from Google Ads.")

# Create a container for filters at the top
with st.container():
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Client Selector
        render_client_selector(key_suffix="_geo")
        
    with col2:
        # Date Range
        today = datetime.today()
        last_30_days = today - timedelta(days=30)
        date_range = st.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

    with col3:
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

# Check Client Selection
if st.session_state.get('selected_client_id') == "ALL":
    st.warning("Please select a specific client to view this report.")
    st.stop()

if 'selected_client_id' not in st.session_state:
    st.warning("Please select a client.")
    st.stop()

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
    
start_date, end_date = date_range

# --- Data Loading ---
with st.spinner("Fetching Geographic Data from Google Ads..."):
    # Get Credentials
    google_creds, _, _ = get_context_credentials()
    
    # Initialize Connector
    use_mock = not bool(google_creds)
    connector = GoogleAdsConnector(credentials=google_creds, use_mock=use_mock)
    
    # Fetch Data
    geo_data = connector.get_geo_data(start_date, end_date)
    age_data = connector.get_age_range_data(start_date, end_date)
    gender_data = connector.get_gender_data(start_date, end_date)

if geo_data.empty and age_data.empty and gender_data.empty:
    st.info("No data available for the selected period.")
    st.stop()

# --- Calculations & Helper Functions ---
def process_data(df, group_col):
    if df.empty:
        return df
    
    # Ensure numeric columns
    cols_to_numeric = ['Impressions', 'Clicks', 'Spend', 'Conversions', 'ConversionValue']
    for col in cols_to_numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            df[col] = 0.0 # Ensure column exists to prevent KeyError

    # Calculated Columns
    df['CTR'] = (df['Clicks'] / df['Impressions'] * 100).fillna(0)
    df['CPC'] = (df['Spend'] / df['Clicks']).replace([float('inf')], 0).fillna(0)
    df['CPA'] = (df['Spend'] / df['Conversions']).replace([float('inf')], 0).fillna(0)
    df['ROAS'] = (df['ConversionValue'] / df['Spend'] * 100).replace([float('inf')], 0).fillna(0)
    
    return df

# Process all dataframes
geo_data = process_data(geo_data, 'Location')
age_data = process_data(age_data, 'Age Range')
gender_data = process_data(gender_data, 'Gender')

# --- Geographic Performance ---
st.header("🌍 Location Performance")

if not geo_data.empty:
    # Metrics
    total_impressions = geo_data['Impressions'].sum()
    total_clicks = geo_data['Clicks'].sum()
    total_spend = geo_data['Spend'].sum()
    total_conversions = geo_data['Conversions'].sum()
    total_revenue = geo_data['ConversionValue'].sum()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Spend", format_currency(total_spend))
    m2.metric("Total Conversions", int(total_conversions))
    m3.metric("Total Revenue", format_currency(total_revenue))
    m4.metric("ROAS", f"{(total_revenue/total_spend*100 if total_spend > 0 else 0):.0f}%")

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top Locations by Spend")
        top_spend = geo_data.sort_values('Spend', ascending=False).head(10)
        fig_spend = px.bar(top_spend, x='Spend', y='Location', orientation='h', title="Top Locations by Spend", text_auto='.2s')
        fig_spend.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_spend, use_container_width=True)

    with c2:
        st.subheader("Top Locations by Conversions")
        top_conv = geo_data.sort_values('Conversions', ascending=False).head(10)
        fig_conv = px.bar(top_conv, x='Conversions', y='Location', orientation='h', title="Top Locations by Conversions", text_auto=True)
        fig_conv.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_conv, use_container_width=True)

    # Detailed Table
    with st.expander("View Detailed Geographic Data"):
        display_df = geo_data.copy()
        display_df['Spend'] = display_df['Spend'].apply(format_currency)
        display_df['CPC'] = display_df['CPC'].apply(format_currency)
        display_df['CPA'] = display_df['CPA'].apply(format_currency)
        display_df['Revenue'] = display_df['ConversionValue'].apply(format_currency)
        display_df['CTR'] = display_df['CTR'].map('{:.2f}%'.format)
        display_df['ROAS'] = display_df['ROAS'].map('{:.0f}%'.format)

        st.dataframe(
            display_df[['Location', 'Spend', 'Impressions', 'Clicks', 'CTR', 'CPC', 'Conversions', 'CPA', 'Revenue', 'ROAS']],
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No geographic data available.")

st.markdown("---")

# --- Demographics: Age ---
st.header("🎂 Age Demographics")

if not age_data.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Spend by Age Range")
        fig_age_spend = px.pie(age_data, values='Spend', names='Age Range', title='Spend Distribution by Age')
        st.plotly_chart(fig_age_spend, use_container_width=True)
    
    with c2:
        st.subheader("Conversions by Age Range")
        fig_age_conv = px.bar(age_data, x='Age Range', y='Conversions', title='Conversions by Age', text_auto=True)
        st.plotly_chart(fig_age_conv, use_container_width=True)
        
    with st.expander("View Detailed Age Data"):
        display_age = age_data.copy()
        display_age['Spend'] = display_age['Spend'].apply(format_currency)
        display_age['CPC'] = display_age['CPC'].apply(format_currency)
        display_age['CPA'] = display_age['CPA'].apply(format_currency)
        display_age['Revenue'] = display_age['ConversionValue'].apply(format_currency)
        display_age['CTR'] = display_age['CTR'].map('{:.2f}%'.format)
        display_age['ROAS'] = display_age['ROAS'].map('{:.0f}%'.format)
        
        st.dataframe(
            display_age[['Age Range', 'Spend', 'Impressions', 'Clicks', 'CTR', 'CPC', 'Conversions', 'CPA', 'Revenue', 'ROAS']],
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No age data available.")

st.markdown("---")

# --- Demographics: Gender ---
st.header("⚧ Gender Demographics")

if not gender_data.empty:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Spend by Gender")
        fig_gender_spend = px.pie(gender_data, values='Spend', names='Gender', title='Spend Distribution by Gender', hole=0.4)
        st.plotly_chart(fig_gender_spend, use_container_width=True)
    
    with c2:
        st.subheader("Conversions by Gender")
        fig_gender_conv = px.bar(gender_data, x='Gender', y='Conversions', title='Conversions by Gender', text_auto=True)
        st.plotly_chart(fig_gender_conv, use_container_width=True)

    with st.expander("View Detailed Gender Data"):
        display_gender = gender_data.copy()
        display_gender['Spend'] = display_gender['Spend'].apply(format_currency)
        display_gender['CPC'] = display_gender['CPC'].apply(format_currency)
        display_gender['CPA'] = display_gender['CPA'].apply(format_currency)
        display_gender['Revenue'] = display_gender['ConversionValue'].apply(format_currency)
        display_gender['CTR'] = display_gender['CTR'].map('{:.2f}%'.format)
        display_gender['ROAS'] = display_gender['ROAS'].map('{:.0f}%'.format)
        
        st.dataframe(
            display_gender[['Gender', 'Spend', 'Impressions', 'Clicks', 'CTR', 'CPC', 'Conversions', 'CPA', 'Revenue', 'ROAS']],
            use_container_width=True,
            hide_index=True
        )
else:
    st.info("No gender data available.")


