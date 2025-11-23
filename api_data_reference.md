# API Data Reference

This document lists all the data fields currently being fetched from Google Ads and Facebook (Meta) Ads APIs for the dashboard.

## 1. Google Ads API

**Connector File**: `connectors/google_ads.py`

### Campaign Level Data
Fetched via `campaign` resource.
- **Campaign Name**: `campaign.name`
- **Campaign ID**: `campaign.id`
- **Campaign Type**: `campaign.advertising_channel_type` (Search, Display, etc.)
- **Date**: `segments.date`
- **Impressions**: `metrics.impressions`
- **Clicks**: `metrics.clicks`
- **Cost (Spend)**: `metrics.cost_micros` (Converted to currency)
- **Conversions**: `metrics.conversions`
- **Conversion Value**: `metrics.conversions_value`

### Ad Group Level Data
Fetched via `ad_group` resource.
- **Campaign Name**: `campaign.name`
- **Campaign ID**: `campaign.id`
- **Ad Group Name**: `ad_group.name`
- **Ad Group ID**: `ad_group.id`
- **Date**: `segments.date`
- **Impressions**: `metrics.impressions`
- **Clicks**: `metrics.clicks`
- **Cost**: `metrics.cost_micros`
- **Conversions**: `metrics.conversions`
- **Conversion Value**: `metrics.conversions_value`

### Ad Level (Creative) Data
Fetched via `ad_group_ad` resource.
- **Campaign Name**: `campaign.name`
- **Ad Group Name**: `ad_group.name`
- **Ad Name (Headline)**: `ad_group_ad.ad.final_urls` (or derived name)
- **Date**: `segments.date`
- **Impressions**: `metrics.impressions`
- **Clicks**: `metrics.clicks`
- **Cost**: `metrics.cost_micros`
- **Conversions**: `metrics.conversions`
- **Conversion Value**: `metrics.conversions_value`

### Geographic Data (New)
Fetched via `geographic_view` resource.
- **Location**: `segments.geo_target_city` or `segments.geo_target_state`
- **Impressions**: `metrics.impressions`
- **Clicks**: `metrics.clicks`
- **Spend**: `metrics.cost_micros`

### Keyword Data (New)
Fetched via `keyword_view` resource.
- **Keyword**: `ad_group_criterion.keyword.text`
- **Impressions**: `metrics.impressions`
- **Clicks**: `metrics.clicks`
- **Spend**: `metrics.cost_micros`

---

## 2. Facebook (Meta) Ads API

**Connector File**: `connectors/facebook_ads.py`

### Campaign/Ad Set Level Data
Fetched via `AdAccount.get_insights`.
- **Date**: `date_start`
- **Campaign Name**: `campaign_name`
- **Campaign ID**: `campaign_id`
- **Ad Set Name**: `adset_name`
- **Ad Set ID**: `adset_id`
- **Objective**: `objective`
- **Impressions**: `impressions`
- **Clicks**: `clicks`
- **Spend**: `spend`
- **Conversions**: Calculated based on Objective.
    - If Objective is **LEAD**, counts `lead`, `on_facebook_lead`, `mobile_app_install`.
    - Otherwise, counts `purchase`, `omni_purchase`.
- **Conversion Value**: `action_values` (Purchase value)

### Ad Level (Creative) Data
Fetched via `AdAccount.get_insights` (level='ad').
- **Date**: `date_start`
- **Campaign Name**: `campaign_name`
- **Ad Set Name**: `adset_name`
- **Ad Name**: `ad_name`
- **Ad ID**: `ad_id`
- **Impressions**: `impressions`
- **Clicks**: `clicks`
- **Spend**: `spend`
- **Conversions**: Same logic as above.
- **Conversion Value**: `action_values`

### Breakdown Data (New)
Fetched via `AdAccount.get_insights` with `breakdowns` parameter.
- **Region**: `region`
- **Platform**: `publisher_platform` (Facebook, Instagram, Audience Network)
- **Placement**: `platform_position` (Feed, Story, etc.)
- **Impressions**: `impressions`
- **Clicks**: `clicks`
- **Spend**: `spend`
