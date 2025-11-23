import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials
from utils.data_processing import load_lead_data, merge_api_and_leads

# Page Config
st.set_page_config(
    page_title="Qualification Analysis",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Lead Qualification Analysis")
st.markdown("Analyze lead qualification rates, trends, and patterns across campaigns and sources.")

# --- Sidebar Configuration ---
st.sidebar.header("Configuration")
render_client_selector()
use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

today = datetime.today()
last_30_days = today - timedelta(days=30)
date_range = st.sidebar.date_input("Select Date Range", value=(last_30_days, today), max_value=today)

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
start_date, end_date = date_range

# Load Credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view qualification analysis.")
    st.stop()

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_qualification_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # Get granular data for better matching
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching and Processing Data..."):
    if not use_mock_data and (not google_creds.get('developer_token') and not fb_creds.get('access_token')):
        st.warning("⚠️ No credentials found. Please go to 'Connections' or use Mock Data.")
        st.stop()
    
    g_df, f_df = load_qualification_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    
    # Load Lead Data
    client_id = st.session_state.get('selected_client_id')
    if client_id == "ALL": client_id = None
    
    lead_df = load_lead_data(client_id=client_id)
    
    if lead_df.empty:
        st.warning("⚠️ No lead data uploaded. Please go to 'Lead Upload' to add your lead data for qualification analysis.")
        st.stop()
    
    # Merge API data with leads
    if not g_df.empty:
        g_df = merge_api_and_leads(g_df, lead_df)
    else:
        g_df['Qualified Leads'] = 0
    
    if not f_df.empty:
        f_df = merge_api_and_leads(f_df, lead_df)
    else:
        f_df['Qualified Leads'] = 0
    
    # Combine data
    if not g_df.empty:
        g_df['AdGroup/AdSet'] = g_df['AdGroup']
        g_df_clean = g_df.drop(columns=['AdGroup', 'AdGroup ID'], errors='ignore')
    else:
        g_df_clean = pd.DataFrame()
    
    if not f_df.empty:
        f_df['AdGroup/AdSet'] = f_df['AdSet']
        f_df_clean = f_df.drop(columns=['AdSet', 'AdSet ID'], errors='ignore')
    else:
        f_df_clean = pd.DataFrame()
    
    combined_df = pd.concat([g_df_clean, f_df_clean], ignore_index=True)
    
    if combined_df.empty:
        st.warning("No data available for the selected period.")
        st.stop()

# --- Key Metrics Overview ---
st.subheader("📊 Qualification Overview")

total_spend = combined_df['Spend'].sum()
total_leads = combined_df['Conversions'].sum()
total_qualified = combined_df['Qualified Leads'].sum()
qualification_rate = (total_qualified / total_leads * 100) if total_leads > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Leads", f"{total_leads:,.0f}")
col2.metric("Qualified Leads", f"{total_qualified:,.0f}")
col3.metric("Qualification Rate", f"{qualification_rate:.1f}%")
col4.metric("Total Spend", f"₹{total_spend:,.0f}")

st.markdown("---")

# --- Qualification Rate Trend ---
st.subheader("📈 Qualification Rate Trend")

# Aggregate by date
daily_stats = combined_df.groupby('Date').agg({
    'Conversions': 'sum',
    'Qualified Leads': 'sum',
    'Spend': 'sum'
}).reset_index()

daily_stats['Qualification Rate %'] = (daily_stats['Qualified Leads'] / daily_stats['Conversions'] * 100).fillna(0)
daily_stats['CPL'] = (daily_stats['Spend'] / daily_stats['Conversions']).replace([float('inf')], 0).fillna(0)
daily_stats['CPQL'] = (daily_stats['Spend'] / daily_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)

# Create dual-axis chart
fig_trend = go.Figure()

# Add qualification rate line
fig_trend.add_trace(go.Scatter(
    x=daily_stats['Date'],
    y=daily_stats['Qualification Rate %'],
    name='Qualification Rate %',
    mode='lines+markers',
    line=dict(color='#2E86AB', width=3),
    yaxis='y'
))

# Add total leads bars
fig_trend.add_trace(go.Bar(
    x=daily_stats['Date'],
    y=daily_stats['Conversions'],
    name='Total Leads',
    marker_color='#A23B72',
    opacity=0.3,
    yaxis='y2'
))

fig_trend.update_layout(
    title='Qualification Rate Trend Over Time',
    xaxis=dict(title='Date'),
    yaxis=dict(title='Qualification Rate %', side='left'),
    yaxis2=dict(title='Total Leads', side='right', overlaying='y'),
    hovermode='x unified',
    height=400
)

st.plotly_chart(fig_trend, use_container_width=True)

# --- Source Comparison ---
st.markdown("---")
st.subheader("🔍 Source Performance Comparison")

source_stats = combined_df.groupby('Source').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum'
}).reset_index()

source_stats['Qualification Rate %'] = (source_stats['Qualified Leads'] / source_stats['Conversions'] * 100).fillna(0)
source_stats['CPQL'] = (source_stats['Spend'] / source_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)

col_left, col_right = st.columns(2)

with col_left:
    fig_source_qual = px.bar(
        source_stats,
        x='Source',
        y='Qualification Rate %',
        title='Qualification Rate by Source',
        color='Source',
        text='Qualification Rate %'
    )
    fig_source_qual.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    st.plotly_chart(fig_source_qual, use_container_width=True)

with col_right:
    fig_source_cpql = px.bar(
        source_stats,
        x='Source',
        y='CPQL',
        title='Cost Per Qualified Lead by Source',
        color='Source',
        text='CPQL'
    )
    fig_source_cpql.update_traces(texttemplate='₹%{text:,.0f}', textposition='outside')
    st.plotly_chart(fig_source_cpql, use_container_width=True)

# --- Campaign Performance Table ---
st.markdown("---")
st.subheader("🎯 Campaign Qualification Performance")

campaign_stats = combined_df.groupby(['Campaign', 'Source']).agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum'
}).reset_index()

campaign_stats['Qualification Rate %'] = (campaign_stats['Qualified Leads'] / campaign_stats['Conversions'] * 100).fillna(0)
campaign_stats['CPL'] = (campaign_stats['Spend'] / campaign_stats['Conversions']).replace([float('inf')], 0).fillna(0)
campaign_stats['CPQL'] = (campaign_stats['Spend'] / campaign_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)

# Sort by qualified leads
campaign_stats = campaign_stats.sort_values(by='Qualified Leads', ascending=False)

# Display top campaigns chart
top_campaigns = campaign_stats.head(10)
fig_campaigns = px.bar(
    top_campaigns,
    x='Qualified Leads',
    y='Campaign',
    orientation='h',
    color='Source',
    title='Top 10 Campaigns by Qualified Leads',
    text='Qualified Leads'
)
fig_campaigns.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_campaigns, use_container_width=True)

# Display detailed table
st.dataframe(
    campaign_stats.style.format({
        'Spend': '₹{:,.2f}',
        'Conversions': '{:,.0f}',
        'Qualified Leads': '{:,.0f}',
        'Qualification Rate %': '{:.1f}%',
        'CPL': '₹{:,.2f}',
        'CPQL': '₹{:,.2f}'
    }),
    use_container_width=True
)

# --- Dynamic Field Analysis ---
st.markdown("---")
st.subheader("🔬 Custom Field Analysis")

# Detect available fields in lead data (excluding standard columns)
standard_columns = ['Campaign ID', 'Ad Group ID', 'Ad Set ID', 'Lead Stage', 'Lead Stage Normalized', 'Is Qualified', 'Service']
available_fields = [col for col in lead_df.columns if col not in standard_columns and lead_df[col].dtype == 'object']

if available_fields:
    selected_field = st.selectbox(
        "Select a field to analyze qualification patterns:",
        options=available_fields,
        help="Analyze how qualification rates vary across different values of this field"
    )
    
    if selected_field:
        # Merge lead data with combined_df to get the custom field
        # We'll use the lead_df directly and group by the selected field
        field_analysis = lead_df.groupby(selected_field).agg({
            'Is Qualified': ['sum', 'count']
        }).reset_index()
        
        field_analysis.columns = [selected_field, 'Qualified Leads', 'Total Leads']
        field_analysis['Qualification Rate %'] = (field_analysis['Qualified Leads'] / field_analysis['Total Leads'] * 100).fillna(0)
        field_analysis = field_analysis.sort_values(by='Qualification Rate %', ascending=False)
        
        # Filter out entries with very few leads (less than 5)
        field_analysis_filtered = field_analysis[field_analysis['Total Leads'] >= 5]
        
        if not field_analysis_filtered.empty:
            col_chart, col_table = st.columns([2, 1])
            
            with col_chart:
                fig_field = px.bar(
                    field_analysis_filtered.head(15),
                    x='Qualification Rate %',
                    y=selected_field,
                    orientation='h',
                    title=f'Qualification Rate by {selected_field} (Min 5 leads)',
                    text='Qualification Rate %',
                    color='Qualification Rate %',
                    color_continuous_scale='RdYlGn'
                )
                fig_field.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_field.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_field, use_container_width=True)
            
            with col_table:
                st.dataframe(
                    field_analysis_filtered.style.format({
                        'Qualified Leads': '{:,.0f}',
                        'Total Leads': '{:,.0f}',
                        'Qualification Rate %': '{:.1f}%'
                    }),
                    use_container_width=True,
                    height=400
                )
        else:
            st.info(f"Not enough data for {selected_field} analysis (minimum 5 leads per value required).")
else:
    st.info("No custom fields detected in lead data. Upload lead data with additional columns (e.g., Lead Source, Location, Industry) to enable custom field analysis.")

# --- Period Comparison ---
st.markdown("---")
st.subheader("📅 Period Comparison")

# Calculate previous period
period_duration = (end_date - start_date).days
previous_start = start_date - timedelta(days=period_duration)
previous_end = start_date - timedelta(days=1)

st.write(f"**Current Period:** {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
st.write(f"**Previous Period:** {previous_start.strftime('%Y-%m-%d')} to {previous_end.strftime('%Y-%m-%d')}")

# Fetch previous period data
@st.cache_data(ttl=300)
def load_previous_period_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching previous period data..."):
    prev_g_df, prev_f_df = load_previous_period_data(previous_start, previous_end, use_mock_data, google_creds, fb_creds)
    
    # Merge with leads
    if not prev_g_df.empty:
        prev_g_df = merge_api_and_leads(prev_g_df, lead_df)
    if not prev_f_df.empty:
        prev_f_df = merge_api_and_leads(prev_f_df, lead_df)
    
    # Combine
    prev_combined = pd.concat([prev_g_df, prev_f_df], ignore_index=True)
    
    if not prev_combined.empty:
        prev_total_leads = prev_combined['Conversions'].sum()
        prev_qualified = prev_combined['Qualified Leads'].sum()
        prev_qual_rate = (prev_qualified / prev_total_leads * 100) if prev_total_leads > 0 else 0
        
        # Calculate changes
        leads_change = ((total_leads - prev_total_leads) / prev_total_leads * 100) if prev_total_leads > 0 else 0
        qualified_change = ((total_qualified - prev_qualified) / prev_qualified * 100) if prev_qualified > 0 else 0
        qual_rate_change = qualification_rate - prev_qual_rate
        
        comp_col1, comp_col2, comp_col3 = st.columns(3)
        
        comp_col1.metric(
            "Total Leads",
            f"{total_leads:,.0f}",
            f"{leads_change:+.1f}%",
            delta_color="normal"
        )
        
        comp_col2.metric(
            "Qualified Leads",
            f"{total_qualified:,.0f}",
            f"{qualified_change:+.1f}%",
            delta_color="normal"
        )
        
        comp_col3.metric(
            "Qualification Rate",
            f"{qualification_rate:.1f}%",
            f"{qual_rate_change:+.1f}pp",
            delta_color="normal"
        )
    else:
        st.info("No data available for the previous period for comparison.")
