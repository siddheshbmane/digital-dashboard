import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials
from utils.data_processing import load_lead_data, merge_api_and_leads

# Page Config
st.set_page_config(
    page_title="Cost Variance Analysis",
    page_icon="💰",
    layout="wide"
)

st.title("💰 Cost Variance Analysis")
st.markdown("Track CPL and CPQL trends over time and identify cost anomalies.")

# --- Sidebar Configuration ---
st.sidebar.header("Configuration")
render_client_selector()
use_mock_data = st.sidebar.checkbox("Use Mock Data", value=False)

# Extended date range for better trend analysis
today = datetime.today()
last_60_days = today - timedelta(days=60)
date_range = st.sidebar.date_input(
    "Select Date Range",
    value=(last_60_days, today),
    max_value=today,
    help="Longer date ranges provide better trend analysis"
)

if len(date_range) != 2:
    st.info("Please select a start and end date.")
    st.stop()
start_date, end_date = date_range

# Variance thresholds
st.sidebar.subheader("Alert Thresholds")
warning_threshold = st.sidebar.slider("Warning Threshold (%)", 10, 50, 20, 5, help="Percentage increase to trigger warning")
critical_threshold = st.sidebar.slider("Critical Threshold (%)", 30, 100, 50, 5, help="Percentage increase to trigger critical alert")

# Rolling window for average calculation
rolling_window = st.sidebar.slider("Rolling Average Window (days)", 3, 14, 7, 1, help="Number of days for rolling average calculation")

# Load Credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view cost variance analysis.")
    st.stop()

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_variance_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    # Get granular data
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

with st.spinner("Fetching and Processing Data..."):
    if not use_mock_data and (not google_creds.get('developer_token') and not fb_creds.get('access_token')):
        st.warning("⚠️ No credentials found. Please go to 'Connections' or use Mock Data.")
        st.stop()
    
    g_df, f_df = load_variance_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    
    # Load Lead Data
    client_id = st.session_state.get('selected_client_id')
    if client_id == "ALL": client_id = None
    
    lead_df = load_lead_data(client_id=client_id)
    
    if lead_df.empty:
        st.warning("⚠️ No lead data uploaded. CPQL analysis requires lead data. CPL analysis will still be available.")
        has_lead_data = False
    else:
        has_lead_data = True
        # Merge API data with leads
        if not g_df.empty:
            g_df = merge_api_and_leads(g_df, lead_df)
        if not f_df.empty:
            f_df = merge_api_and_leads(f_df, lead_df)
    
    # Combine data
    combined_df = pd.concat([g_df, f_df], ignore_index=True)
    
    if combined_df.empty:
        st.warning("No data available for the selected period.")
        st.stop()

# --- Calculate Daily Metrics ---
daily_stats = combined_df.groupby('Date').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum' if has_lead_data else lambda x: 0
}).reset_index()

# Calculate CPL and CPQL
daily_stats['CPL'] = (daily_stats['Spend'] / daily_stats['Conversions']).replace([float('inf')], np.nan).fillna(0)

if has_lead_data:
    daily_stats['CPQL'] = (daily_stats['Spend'] / daily_stats['Qualified Leads']).replace([float('inf')], np.nan).fillna(0)
else:
    daily_stats['CPQL'] = 0

# Calculate rolling averages
daily_stats['CPL_Rolling_Avg'] = daily_stats['CPL'].rolling(window=rolling_window, min_periods=1).mean()

if has_lead_data:
    daily_stats['CPQL_Rolling_Avg'] = daily_stats['CPQL'].rolling(window=rolling_window, min_periods=1).mean()
else:
    daily_stats['CPQL_Rolling_Avg'] = 0

# Calculate variance from rolling average
daily_stats['CPL_Variance_%'] = ((daily_stats['CPL'] - daily_stats['CPL_Rolling_Avg']) / daily_stats['CPL_Rolling_Avg'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)

if has_lead_data:
    daily_stats['CPQL_Variance_%'] = ((daily_stats['CPQL'] - daily_stats['CPQL_Rolling_Avg']) / daily_stats['CPQL_Rolling_Avg'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
else:
    daily_stats['CPQL_Variance_%'] = 0

# Identify anomalies
daily_stats['CPL_Alert'] = daily_stats['CPL_Variance_%'].apply(
    lambda x: 'Critical' if x >= critical_threshold else ('Warning' if x >= warning_threshold else 'Normal')
)

if has_lead_data:
    daily_stats['CPQL_Alert'] = daily_stats['CPQL_Variance_%'].apply(
        lambda x: 'Critical' if x >= critical_threshold else ('Warning' if x >= warning_threshold else 'Normal')
    )
else:
    daily_stats['CPQL_Alert'] = 'Normal'

# --- Alert Summary ---
st.subheader("🚨 Alert Summary")

# Current metrics
current_cpl = daily_stats['CPL'].iloc[-1] if len(daily_stats) > 0 else 0
avg_cpl = daily_stats['CPL_Rolling_Avg'].iloc[-1] if len(daily_stats) > 0 else 0
cpl_variance = daily_stats['CPL_Variance_%'].iloc[-1] if len(daily_stats) > 0 else 0

if has_lead_data:
    current_cpql = daily_stats['CPQL'].iloc[-1] if len(daily_stats) > 0 else 0
    avg_cpql = daily_stats['CPQL_Rolling_Avg'].iloc[-1] if len(daily_stats) > 0 else 0
    cpql_variance = daily_stats['CPQL_Variance_%'].iloc[-1] if len(daily_stats) > 0 else 0
else:
    current_cpql = 0
    avg_cpql = 0
    cpql_variance = 0

# Determine alert colors
cpl_color = "🔴" if cpl_variance >= critical_threshold else ("🟡" if cpl_variance >= warning_threshold else "🟢")
cpql_color = "🔴" if cpql_variance >= critical_threshold else ("🟡" if cpql_variance >= warning_threshold else "🟢")

col1, col2 = st.columns(2)

with col1:
    st.metric(
        f"{cpl_color} Current CPL",
        f"₹{current_cpl:,.0f}",
        f"{cpl_variance:+.1f}% vs avg",
        delta_color="inverse"
    )
    st.caption(f"{rolling_window}-day average: ₹{avg_cpl:,.0f}")

with col2:
    if has_lead_data:
        st.metric(
            f"{cpql_color} Current CPQL",
            f"₹{current_cpql:,.0f}",
            f"{cpql_variance:+.1f}% vs avg",
            delta_color="inverse"
        )
        st.caption(f"{rolling_window}-day average: ₹{avg_cpql:,.0f}")
    else:
        st.info("CPQL metrics require lead data. Please upload lead data to enable CPQL analysis.")

# Count anomalies
cpl_critical_count = len(daily_stats[daily_stats['CPL_Alert'] == 'Critical'])
cpl_warning_count = len(daily_stats[daily_stats['CPL_Alert'] == 'Warning'])

if has_lead_data:
    cpql_critical_count = len(daily_stats[daily_stats['CPQL_Alert'] == 'Critical'])
    cpql_warning_count = len(daily_stats[daily_stats['CPQL_Alert'] == 'Warning'])
else:
    cpql_critical_count = 0
    cpql_warning_count = 0

st.info(f"📊 **Anomaly Summary:** {cpl_critical_count} critical CPL spikes, {cpl_warning_count} CPL warnings" + 
        (f", {cpql_critical_count} critical CPQL spikes, {cpql_warning_count} CPQL warnings" if has_lead_data else ""))

st.markdown("---")

# --- CPL Trend Chart ---
st.subheader("📈 Cost Per Lead (CPL) Trend")

fig_cpl = go.Figure()

# Add actual CPL line
fig_cpl.add_trace(go.Scatter(
    x=daily_stats['Date'],
    y=daily_stats['CPL'],
    name='Actual CPL',
    mode='lines+markers',
    line=dict(color='#2E86AB', width=2),
    marker=dict(size=6)
))

# Add rolling average line
fig_cpl.add_trace(go.Scatter(
    x=daily_stats['Date'],
    y=daily_stats['CPL_Rolling_Avg'],
    name=f'{rolling_window}-Day Avg',
    mode='lines',
    line=dict(color='#A23B72', width=2, dash='dash')
))

# Add anomaly markers
critical_days = daily_stats[daily_stats['CPL_Alert'] == 'Critical']
warning_days = daily_stats[daily_stats['CPL_Alert'] == 'Warning']

if not critical_days.empty:
    fig_cpl.add_trace(go.Scatter(
        x=critical_days['Date'],
        y=critical_days['CPL'],
        name='Critical Alert',
        mode='markers',
        marker=dict(color='red', size=12, symbol='x', line=dict(width=2))
    ))

if not warning_days.empty:
    fig_cpl.add_trace(go.Scatter(
        x=warning_days['Date'],
        y=warning_days['CPL'],
        name='Warning',
        mode='markers',
        marker=dict(color='orange', size=10, symbol='triangle-up')
    ))

fig_cpl.update_layout(
    title='Cost Per Lead Trend with Anomaly Detection',
    xaxis=dict(title='Date'),
    yaxis=dict(title='CPL (₹)'),
    hovermode='x unified',
    height=450
)

st.plotly_chart(fig_cpl, use_container_width=True)

# --- CPQL Trend Chart ---
if has_lead_data:
    st.markdown("---")
    st.subheader("📊 Cost Per Qualified Lead (CPQL) Trend")
    
    fig_cpql = go.Figure()
    
    # Add actual CPQL line
    fig_cpql.add_trace(go.Scatter(
        x=daily_stats['Date'],
        y=daily_stats['CPQL'],
        name='Actual CPQL',
        mode='lines+markers',
        line=dict(color='#F18F01', width=2),
        marker=dict(size=6)
    ))
    
    # Add rolling average line
    fig_cpql.add_trace(go.Scatter(
        x=daily_stats['Date'],
        y=daily_stats['CPQL_Rolling_Avg'],
        name=f'{rolling_window}-Day Avg',
        mode='lines',
        line=dict(color='#C73E1D', width=2, dash='dash')
    ))
    
    # Add anomaly markers
    cpql_critical_days = daily_stats[daily_stats['CPQL_Alert'] == 'Critical']
    cpql_warning_days = daily_stats[daily_stats['CPQL_Alert'] == 'Warning']
    
    if not cpql_critical_days.empty:
        fig_cpql.add_trace(go.Scatter(
            x=cpql_critical_days['Date'],
            y=cpql_critical_days['CPQL'],
            name='Critical Alert',
            mode='markers',
            marker=dict(color='red', size=12, symbol='x', line=dict(width=2))
        ))
    
    if not cpql_warning_days.empty:
        fig_cpql.add_trace(go.Scatter(
            x=cpql_warning_days['Date'],
            y=cpql_warning_days['CPQL'],
            name='Warning',
            mode='markers',
            marker=dict(color='orange', size=10, symbol='triangle-up')
        ))
    
    fig_cpql.update_layout(
        title='Cost Per Qualified Lead Trend with Anomaly Detection',
        xaxis=dict(title='Date'),
        yaxis=dict(title='CPQL (₹)'),
        hovermode='x unified',
        height=450
    )
    
    st.plotly_chart(fig_cpql, use_container_width=True)

# --- Variance Table ---
st.markdown("---")
st.subheader("📋 Detailed Variance Analysis")

# Calculate day-over-day and week-over-week changes
variance_table = daily_stats.copy()
variance_table['CPL_DoD_%'] = variance_table['CPL'].pct_change() * 100
variance_table['CPL_WoW_%'] = variance_table['CPL'].pct_change(periods=7) * 100

if has_lead_data:
    variance_table['CPQL_DoD_%'] = variance_table['CPQL'].pct_change() * 100
    variance_table['CPQL_WoW_%'] = variance_table['CPQL'].pct_change(periods=7) * 100

# Filter to show only recent data (last 30 days)
recent_variance = variance_table.tail(30)

# Select columns to display
display_cols = ['Date', 'CPL', 'CPL_Rolling_Avg', 'CPL_Variance_%', 'CPL_DoD_%', 'CPL_WoW_%', 'CPL_Alert']
if has_lead_data:
    display_cols.extend(['CPQL', 'CPQL_Rolling_Avg', 'CPQL_Variance_%', 'CPQL_DoD_%', 'CPQL_WoW_%', 'CPQL_Alert'])

# Style the dataframe
def highlight_alerts(row):
    colors = []
    for col in row.index:
        if 'Alert' in col:
            if row[col] == 'Critical':
                colors.append('background-color: #ffcccc')
            elif row[col] == 'Warning':
                colors.append('background-color: #fff4cc')
            else:
                colors.append('background-color: #ccffcc')
        else:
            colors.append('')
    return colors

format_dict = {
    'CPL': '₹{:,.0f}',
    'CPL_Rolling_Avg': '₹{:,.0f}',
    'CPL_Variance_%': '{:+.1f}%',
    'CPL_DoD_%': '{:+.1f}%',
    'CPL_WoW_%': '{:+.1f}%'
}

if has_lead_data:
    format_dict.update({
        'CPQL': '₹{:,.0f}',
        'CPQL_Rolling_Avg': '₹{:,.0f}',
        'CPQL_Variance_%': '{:+.1f}%',
        'CPQL_DoD_%': '{:+.1f}%',
        'CPQL_WoW_%': '{:+.1f}%'
    })

st.dataframe(
    recent_variance[display_cols].style.apply(highlight_alerts, axis=1).format(format_dict),
    use_container_width=True,
    height=400
)

# --- Insights ---
st.markdown("---")
st.subheader("💡 Key Insights")

insights = []

# CPL insights
if cpl_variance >= critical_threshold:
    insights.append(f"🔴 **Critical Alert:** Current CPL is {cpl_variance:.1f}% higher than the {rolling_window}-day average. Immediate investigation recommended.")
elif cpl_variance >= warning_threshold:
    insights.append(f"🟡 **Warning:** Current CPL is {cpl_variance:.1f}% higher than the {rolling_window}-day average. Monitor closely.")
else:
    insights.append(f"🟢 **Stable:** Current CPL is within normal range ({cpl_variance:+.1f}% vs average).")

# CPQL insights
if has_lead_data:
    if cpql_variance >= critical_threshold:
        insights.append(f"🔴 **Critical Alert:** Current CPQL is {cpql_variance:.1f}% higher than the {rolling_window}-day average. Review qualification criteria and campaign targeting.")
    elif cpql_variance >= warning_threshold:
        insights.append(f"🟡 **Warning:** Current CPQL is {cpql_variance:.1f}% higher than the {rolling_window}-day average. Monitor qualification rates.")
    else:
        insights.append(f"🟢 **Stable:** Current CPQL is within normal range ({cpql_variance:+.1f}% vs average).")

# Trend insights
cpl_trend = "increasing" if daily_stats['CPL'].iloc[-7:].mean() > daily_stats['CPL'].iloc[-14:-7].mean() else "decreasing"
insights.append(f"📊 **Trend:** CPL is {cpl_trend} over the past week.")

if has_lead_data:
    cpql_trend = "increasing" if daily_stats['CPQL'].iloc[-7:].mean() > daily_stats['CPQL'].iloc[-14:-7].mean() else "decreasing"
    insights.append(f"📊 **Trend:** CPQL is {cpql_trend} over the past week.")

# Display insights
for insight in insights:
    st.markdown(insight)
