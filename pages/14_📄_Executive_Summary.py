import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from connectors.google_ads import GoogleAdsConnector
from connectors.facebook_ads import FacebookAdsConnector
from utils.auth_helper import render_client_selector, get_context_credentials
from utils.data_processing import load_lead_data, merge_api_and_leads
from utils.client_manager import get_active_clients

# Page Config
st.set_page_config(
    page_title="Executive Summary",
    page_icon="📄",
    layout="wide"
)

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

# Print view toggle
print_view = st.sidebar.checkbox("Print View", value=False, help="Optimize layout for printing/screenshots")

# Load Credentials
google_creds, fb_creds, is_all_clients = get_context_credentials()

if is_all_clients:
    st.warning("⚠️ You have selected 'All Clients'. Please select a specific client to view executive summary.")
    st.stop()

# Get client name
client_id = st.session_state.get('selected_client_id')
active_clients = get_active_clients()
client_name = next((c['name'] for c in active_clients if c['id'] == client_id), "Unknown Client")

# --- Data Fetching ---
@st.cache_data(ttl=300)
def load_summary_data(start, end, mock, g_creds, f_creds):
    g_conn = GoogleAdsConnector(credentials=g_creds, use_mock=mock)
    fb_conn = FacebookAdsConnector(credentials=f_creds, use_mock=mock)
    
    g_data = g_conn.get_ad_group_data(start, end)
    f_data = fb_conn.get_ad_set_data(start, end)
    
    return g_data, f_data

# Calculate previous period
period_duration = (end_date - start_date).days
previous_start = start_date - timedelta(days=period_duration + 1)
previous_end = start_date - timedelta(days=1)

with st.spinner("Generating Executive Summary..."):
    if not use_mock_data and (not google_creds.get('developer_token') and not fb_creds.get('access_token')):
        st.warning("⚠️ No credentials found. Please go to 'Connections' or use Mock Data.")
        st.stop()
    
    # Load current period data
    g_df, f_df = load_summary_data(start_date, end_date, use_mock_data, google_creds, fb_creds)
    
    # Load previous period data
    prev_g_df, prev_f_df = load_summary_data(previous_start, previous_end, use_mock_data, google_creds, fb_creds)
    
    # Load Lead Data
    if client_id == "ALL": client_id = None
    lead_df = load_lead_data(client_id=client_id)
    
    has_lead_data = not lead_df.empty
    
    # Merge current period with leads
    if has_lead_data:
        if not g_df.empty:
            g_df = merge_api_and_leads(g_df, lead_df)
        if not f_df.empty:
            f_df = merge_api_and_leads(f_df, lead_df)
        
        # Merge previous period with leads
        if not prev_g_df.empty:
            prev_g_df = merge_api_and_leads(prev_g_df, lead_df)
        if not prev_f_df.empty:
            prev_f_df = merge_api_and_leads(prev_f_df, lead_df)
    
    # Combine data
    current_df = pd.concat([g_df, f_df], ignore_index=True)
    previous_df = pd.concat([prev_g_df, prev_f_df], ignore_index=True)
    
    if current_df.empty:
        st.warning("No data available for the selected period.")
        st.stop()

# --- Calculate Metrics ---
def calculate_metrics(df, has_leads=False):
    metrics = {
        'spend': df['Spend'].sum(),
        'leads': df['Conversions'].sum(),
        'clicks': df['Clicks'].sum(),
        'impressions': df['Impressions'].sum()
    }
    
    metrics['cpl'] = (metrics['spend'] / metrics['leads']) if metrics['leads'] > 0 else 0
    metrics['ctr'] = (metrics['clicks'] / metrics['impressions'] * 100) if metrics['impressions'] > 0 else 0
    
    if has_leads:
        metrics['qualified_leads'] = df['Qualified Leads'].sum()
        metrics['cpql'] = (metrics['spend'] / metrics['qualified_leads']) if metrics['qualified_leads'] > 0 else 0
        metrics['qual_rate'] = (metrics['qualified_leads'] / metrics['leads'] * 100) if metrics['leads'] > 0 else 0
    else:
        metrics['qualified_leads'] = 0
        metrics['cpql'] = 0
        metrics['qual_rate'] = 0
    
    return metrics

current_metrics = calculate_metrics(current_df, has_lead_data)
previous_metrics = calculate_metrics(previous_df, has_lead_data) if not previous_df.empty else None

# Calculate percentage changes
def calc_change(current, previous):
    if previous is None or previous == 0:
        return 0
    return ((current - previous) / previous * 100)

if previous_metrics:
    changes = {
        'spend': calc_change(current_metrics['spend'], previous_metrics['spend']),
        'leads': calc_change(current_metrics['leads'], previous_metrics['leads']),
        'qualified_leads': calc_change(current_metrics['qualified_leads'], previous_metrics['qualified_leads']),
        'cpl': calc_change(current_metrics['cpl'], previous_metrics['cpl']),
        'cpql': calc_change(current_metrics['cpql'], previous_metrics['cpql']),
        'qual_rate': current_metrics['qual_rate'] - previous_metrics['qual_rate']  # Percentage point change
    }
else:
    changes = {k: 0 for k in ['spend', 'leads', 'qualified_leads', 'cpl', 'cpql', 'qual_rate']}

# --- Header ---
if not print_view:
    st.title("📄 Executive Summary")
else:
    # Compact header for print view
    st.markdown(f"<h1 style='text-align: center; margin-bottom: 0;'>📄 Executive Summary</h1>", unsafe_allow_html=True)

st.markdown(f"<h3 style='text-align: center; color: #666;'>{client_name}</h3>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #888;'>Report Period: {start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}</p>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align: center; color: #888; font-size: 0.9em;'>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>", unsafe_allow_html=True)

st.markdown("---")

# --- Key Metrics Cards ---
st.subheader("📊 Key Performance Metrics")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Spend",
        f"₹{current_metrics['spend']:,.0f}",
        f"{changes['spend']:+.1f}%",
        delta_color="inverse"
    )
    
    st.metric(
        "Total Leads",
        f"{current_metrics['leads']:,.0f}",
        f"{changes['leads']:+.1f}%"
    )

with col2:
    if has_lead_data:
        st.metric(
            "Qualified Leads",
            f"{current_metrics['qualified_leads']:,.0f}",
            f"{changes['qualified_leads']:+.1f}%"
        )
        
        st.metric(
            "Qualification Rate",
            f"{current_metrics['qual_rate']:.1f}%",
            f"{changes['qual_rate']:+.1f}pp"
        )
    else:
        st.info("Upload lead data to see qualification metrics")

with col3:
    st.metric(
        "Cost Per Lead",
        f"₹{current_metrics['cpl']:,.0f}",
        f"{changes['cpl']:+.1f}%",
        delta_color="inverse"
    )
    
    if has_lead_data:
        st.metric(
            "Cost Per Qualified Lead",
            f"₹{current_metrics['cpql']:,.0f}",
            f"{changes['cpql']:+.1f}%",
            delta_color="inverse"
        )

st.markdown("---")

# --- Trend Sparklines ---
st.subheader("📈 Performance Trends")

# Aggregate daily data for sparklines
daily_current = current_df.groupby('Date').agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum' if has_lead_data else lambda x: 0
}).reset_index()

if has_lead_data:
    daily_current['Qual_Rate'] = (daily_current['Qualified Leads'] / daily_current['Conversions'] * 100).fillna(0)

spark_col1, spark_col2, spark_col3 = st.columns(3)

with spark_col1:
    fig_spend = go.Figure()
    fig_spend.add_trace(go.Scatter(
        x=daily_current['Date'],
        y=daily_current['Spend'],
        mode='lines',
        fill='tozeroy',
        line=dict(color='#2E86AB', width=2)
    ))
    fig_spend.update_layout(
        title='Daily Spend Trend',
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor='#eee')
    )
    st.plotly_chart(fig_spend, use_container_width=True)

with spark_col2:
    fig_leads = go.Figure()
    fig_leads.add_trace(go.Scatter(
        x=daily_current['Date'],
        y=daily_current['Conversions'],
        mode='lines',
        fill='tozeroy',
        line=dict(color='#A23B72', width=2)
    ))
    fig_leads.update_layout(
        title='Daily Leads Trend',
        height=200,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=True, gridcolor='#eee')
    )
    st.plotly_chart(fig_leads, use_container_width=True)

with spark_col3:
    if has_lead_data:
        fig_qual = go.Figure()
        fig_qual.add_trace(go.Scatter(
            x=daily_current['Date'],
            y=daily_current['Qual_Rate'],
            mode='lines',
            fill='tozeroy',
            line=dict(color='#F18F01', width=2)
        ))
        fig_qual.update_layout(
            title='Qualification Rate Trend (%)',
            height=200,
            margin=dict(l=20, r=20, t=40, b=20),
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=True, gridcolor='#eee')
        )
        st.plotly_chart(fig_qual, use_container_width=True)

st.markdown("---")

# --- Top Performers ---
st.subheader("🏆 Top Performing Campaigns")

# Calculate campaign stats
campaign_stats = current_df.groupby(['Campaign', 'Source']).agg({
    'Spend': 'sum',
    'Conversions': 'sum',
    'Qualified Leads': 'sum' if has_lead_data else lambda x: 0
}).reset_index()

campaign_stats['CPL'] = (campaign_stats['Spend'] / campaign_stats['Conversions']).replace([float('inf')], 0).fillna(0)
if has_lead_data:
    campaign_stats['CPQL'] = (campaign_stats['Spend'] / campaign_stats['Qualified Leads']).replace([float('inf')], 0).fillna(0)

top_col1, top_col2 = st.columns(2)

with top_col1:
    st.markdown("**Top 3 by Qualified Leads**" if has_lead_data else "**Top 3 by Total Leads**")
    
    if has_lead_data:
        top_by_qual = campaign_stats.nlargest(3, 'Qualified Leads')[['Campaign', 'Source', 'Qualified Leads', 'CPQL']]
        for idx, row in top_by_qual.iterrows():
            st.markdown(f"**{row['Campaign']}** ({row['Source']})")
            st.caption(f"Qualified Leads: {row['Qualified Leads']:.0f} | CPQL: ₹{row['CPQL']:,.0f}")
    else:
        top_by_leads = campaign_stats.nlargest(3, 'Conversions')[['Campaign', 'Source', 'Conversions', 'CPL']]
        for idx, row in top_by_leads.iterrows():
            st.markdown(f"**{row['Campaign']}** ({row['Source']})")
            st.caption(f"Leads: {row['Conversions']:.0f} | CPL: ₹{row['CPL']:,.0f}")

with top_col2:
    st.markdown("**Top 3 by Lowest CPQL**" if has_lead_data else "**Top 3 by Lowest CPL**")
    
    if has_lead_data:
        # Filter out campaigns with 0 qualified leads
        valid_campaigns = campaign_stats[campaign_stats['Qualified Leads'] > 0]
        if not valid_campaigns.empty:
            top_by_cpql = valid_campaigns.nsmallest(3, 'CPQL')[['Campaign', 'Source', 'Qualified Leads', 'CPQL']]
            for idx, row in top_by_cpql.iterrows():
                st.markdown(f"**{row['Campaign']}** ({row['Source']})")
                st.caption(f"Qualified Leads: {row['Qualified Leads']:.0f} | CPQL: ₹{row['CPQL']:,.0f}")
        else:
            st.info("No campaigns with qualified leads")
    else:
        valid_campaigns = campaign_stats[campaign_stats['Conversions'] > 0]
        if not valid_campaigns.empty:
            top_by_cpl = valid_campaigns.nsmallest(3, 'CPL')[['Campaign', 'Source', 'Conversions', 'CPL']]
            for idx, row in top_by_cpl.iterrows():
                st.markdown(f"**{row['Campaign']}** ({row['Source']})")
                st.caption(f"Leads: {row['Conversions']:.0f} | CPL: ₹{row['CPL']:,.0f}")

st.markdown("---")

# --- Auto-Generated Insights ---
st.subheader("💡 Key Insights")

insights = []

# Spend insight
if changes['spend'] > 10:
    insights.append(f"📈 Spend increased by {changes['spend']:.1f}% compared to the previous period.")
elif changes['spend'] < -10:
    insights.append(f"📉 Spend decreased by {abs(changes['spend']):.1f}% compared to the previous period.")
else:
    insights.append(f"➡️ Spend remained relatively stable (change: {changes['spend']:+.1f}%).")

# Lead efficiency insight
if changes['leads'] > changes['spend']:
    insights.append(f"✅ Lead generation efficiency improved - leads grew faster ({changes['leads']:+.1f}%) than spend ({changes['spend']:+.1f}%).")
elif changes['leads'] < changes['spend'] and changes['spend'] > 0:
    insights.append(f"⚠️ Lead generation efficiency declined - spend grew faster ({changes['spend']:+.1f}%) than leads ({changes['leads']:+.1f}%).")

# Qualification insight
if has_lead_data:
    if changes['qual_rate'] > 5:
        insights.append(f"🎯 Qualification rate improved significantly by {changes['qual_rate']:+.1f} percentage points.")
    elif changes['qual_rate'] < -5:
        insights.append(f"⚠️ Qualification rate declined by {abs(changes['qual_rate']):.1f} percentage points. Review targeting and qualification criteria.")
    
    # CPQL insight
    if changes['cpql'] < -10:
        insights.append(f"💰 Cost efficiency improved - CPQL decreased by {abs(changes['cpql']):.1f}%.")
    elif changes['cpql'] > 10:
        insights.append(f"💸 CPQL increased by {changes['cpql']:.1f}%. Consider optimizing campaign targeting.")

# Platform performance
source_performance = current_df.groupby('Source').agg({
    'Spend': 'sum',
    'Conversions': 'sum'
}).reset_index()
source_performance['CPL'] = source_performance['Spend'] / source_performance['Conversions']

if len(source_performance) > 1:
    best_source = source_performance.loc[source_performance['CPL'].idxmin(), 'Source']
    insights.append(f"🏅 {best_source} is currently the most cost-efficient platform.")

# Display insights
for insight in insights:
    st.markdown(f"- {insight}")

# --- Footer ---
st.markdown("---")
st.markdown(f"<p style='text-align: center; color: #999; font-size: 0.85em;'>This report was automatically generated by the Ads Reporting Dashboard</p>", unsafe_allow_html=True)

if print_view:
    st.info("💡 Tip: Use your browser's print function (Cmd/Ctrl + P) to save this summary as a PDF.")
