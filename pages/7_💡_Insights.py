import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.config_manager import load_credentials

# Page Config
st.set_page_config(
    page_title="Insights",
    page_icon="💡",
    layout="wide"
)

st.title("💡 Deep Insights")
st.markdown("Explore granular performance data: Keywords, Locations, Placements, and more.")

# --- Config & Data ---
# --- Config & Data ---
st.sidebar.header("Configuration")

from utils.auth_helper import render_client_selector
render_client_selector()

use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
start_date, end_date = date_range

from utils.auth_helper import get_context_credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view detailed insights.")
    st.stop()

# --- Google Ads Insights ---
st.header("Google Ads Insights")
g_conn = GoogleAdsConnector(credentials=google_creds, use_mock=use_mock_data)

tab_kw, tab_geo = st.tabs(["🔑 Keywords", "🌍 Location"])

with tab_kw:
    st.subheader("Top Performing Keywords")
    with st.spinner("Fetching Keyword Data..."):
        kw_df = g_conn.get_keyword_data(start_date, end_date)
    
    if not kw_df.empty:
        # Metrics
        total_spend = kw_df['Spend'].sum()
        total_clicks = kw_df['Clicks'].sum()
        avg_cpc = total_spend / total_clicks if total_clicks > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Keywords Tracked", len(kw_df))
        c2.metric("Total Spend", f"₹{total_spend:,.0f}")
        c3.metric("Avg CPC", f"₹{avg_cpc:.2f}")
        
        # Chart
        top_kw = kw_df.sort_values(by='Spend', ascending=False).head(10)
        fig_kw = px.bar(top_kw, x='Spend', y='Keyword', orientation='h', title='Top 10 Keywords by Spend', text='Spend')
        fig_kw.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_kw, use_container_width=True)
        
        # Table
        st.dataframe(kw_df.sort_values(by='Spend', ascending=False), use_container_width=True)
    else:
        st.info("No keyword data available.")

with tab_geo:
    st.subheader("Geographic Performance")
    with st.spinner("Fetching Location Data..."):
        geo_df = g_conn.get_geo_data(start_date, end_date)
        
    if not geo_df.empty:
        # Chart
        fig_geo = px.bar(geo_df.sort_values(by='Spend', ascending=False).head(15), 
                         x='Location', y='Spend', color='Clicks', 
                         title='Top Locations by Spend')
        st.plotly_chart(fig_geo, use_container_width=True)
        
        st.dataframe(geo_df, use_container_width=True)
    else:
        st.info("No geographic data available.")

st.markdown("---")

# --- Meta Ads Insights ---
st.header("Meta Ads Insights")
fb_conn = FacebookAdsConnector(credentials=fb_creds, use_mock=use_mock_data)

tab_region, tab_place, tab_plat = st.tabs(["🗺️ Region", "📱 Placement", "🖥️ Platform"])

with tab_region:
    st.subheader("Regional Performance")
    with st.spinner("Fetching Regional Data..."):
        reg_df = fb_conn.get_breakdown_data(start_date, end_date, breakdown='region')
        
    if not reg_df.empty:
        fig_reg = px.bar(reg_df.sort_values(by='Spend', ascending=False).head(15),
                         x='Breakdown', y='Spend', title='Top Regions by Spend', labels={'Breakdown': 'Region'})
        st.plotly_chart(fig_reg, use_container_width=True)
        st.dataframe(reg_df, use_container_width=True)
    else:
        st.info("No regional data available.")

with tab_place:
    st.subheader("Ad Placement Performance")
    with st.spinner("Fetching Placement Data..."):
        place_df = fb_conn.get_breakdown_data(start_date, end_date, breakdown='platform_position')
        
    if not place_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            fig_place = px.pie(place_df, values='Spend', names='Breakdown', title='Spend by Placement')
            st.plotly_chart(fig_place, use_container_width=True)
        with c2:
            fig_place_bar = px.bar(place_df, x='Breakdown', y='Clicks', title='Clicks by Placement')
            st.plotly_chart(fig_place_bar, use_container_width=True)
            
        st.dataframe(place_df, use_container_width=True)
    else:
        st.info("No placement data available.")

with tab_plat:
    st.subheader("Platform Performance (FB vs IG)")
    with st.spinner("Fetching Platform Data..."):
        plat_df = fb_conn.get_breakdown_data(start_date, end_date, breakdown='publisher_platform')
        
    if not plat_df.empty:
        fig_plat = px.bar(plat_df, x='Breakdown', y=['Spend', 'Impressions'], barmode='group', title='Platform Comparison')
        st.plotly_chart(fig_plat, use_container_width=True)
        st.dataframe(plat_df, use_container_width=True)
    else:
        st.info("No platform data available.")
