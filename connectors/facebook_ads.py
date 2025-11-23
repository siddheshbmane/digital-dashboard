import pandas as pd
import numpy as np
from datetime import timedelta
import streamlit as st

class FacebookAdsConnector:
    def __init__(self, credentials=None, use_mock=True):
        self.credentials = credentials
        self.use_mock = use_mock

    @st.cache_data(ttl=3600)
    def get_data(_self, start_date, end_date):
        if _self.use_mock:
            return _self._get_mock_data(start_date, end_date)
        else:
            return _self._get_real_data(start_date, end_date)

    def _get_mock_data(self, start_date, end_date):
        """
        Simulates fetching data from Facebook Ads API.
        """
        dates = pd.date_range(start=start_date, end=end_date)
        data = []
        
        campaigns = ['FB - Traffic', 'FB - Conversions', 'IG - Stories', 'Audience Network']
        
        for date in dates:
            for campaign in campaigns:
                impressions = np.random.randint(500, 15000)
                clicks = int(impressions * np.random.uniform(0.005, 0.03))
                spend = clicks * np.random.uniform(0.2, 3.0)
                conversions = int(clicks * np.random.uniform(0.01, 0.08))
                
                data.append({
                    'Date': date,
                    'Campaign': campaign,
                    'Source': 'Facebook Ads',
                    'Impressions': impressions,
                    'Clicks': clicks,
                    'Spend': round(spend, 2),
                    'Conversions': conversions
                })
                
        return pd.DataFrame(data)

    def _get_real_data(self, start_date, end_date):
        """
        Fetches data from Facebook Ads API.
        """
        if not self.credentials:
            st.error("Facebook Ads Credentials missing.")
            return pd.DataFrame()

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adsinsights import AdsInsights

            # Initialize API
            app_id = self.credentials.get("app_id")
            app_secret = self.credentials.get("app_secret")
            access_token = self.credentials.get("access_token")
            ad_account_id = self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)

            account = AdAccount(ad_account_id)
            fields = [
                AdsInsights.Field.campaign_name,
                AdsInsights.Field.objective,
                AdsInsights.Field.spend,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.actions, # Conversions are tricky in FB, usually in actions
                AdsInsights.Field.action_values, # Revenue
                AdsInsights.Field.date_start,
                AdsInsights.Field.date_stop,
            ]
            params = {
                'time_range': {'since': start_date.strftime('%Y-%m-%d'), 'until': end_date.strftime('%Y-%m-%d')},
                'level': 'campaign',
                'time_increment': 1,
            }

            insights = account.get_insights(fields=fields, params=params)

            data = []
            for item in insights:
                # Extract conversions based on objective
                conversions = 0
                objective = item.get('objective', '').upper()
                
                # List of lead-related action types
                lead_action_types = [
                    'lead', 
                    'on_facebook_lead', 
                    'offsite_conversion.fb_pixel_lead',
                    'mobile_app_install' # Sometimes considered a lead/result for app campaigns
                ]
                
                if 'actions' in item:
                    for action in item['actions']:
                        action_type = action['action_type']
                        
                        # Logic: If Lead Campaign, look for leads. Else look for purchases/generic conversions.
                        if 'LEAD' in objective:
                            if action_type in lead_action_types:
                                conversions += int(action['value'])
                        else:
                            # Fallback or other objectives (e.g. Sales -> Purchase)
                            if action_type in ['offsite_conversion.fb_pixel_purchase', 'purchase', 'omni_purchase']:
                                conversions += int(action['value'])
                
                # If no specific conversions found but we have actions and it's not a lead/sales campaign, 
                # maybe count all actions? No, user wants "Results".
                # For now, if 0 conversions and it's a lead campaign, it stays 0.
                
                # Extract revenue
                revenue = 0.0
                if 'action_values' in item:
                    for action in item['action_values']:
                        if action['action_type'] in ['offsite_conversion.fb_pixel_purchase', 'purchase', 'omni_purchase']: 
                            revenue += float(action['value'])
                
                data.append({
                    'Date': pd.to_datetime(item['date_start']),
                    'Campaign': item['campaign_name'],
                    'Source': 'Facebook Ads',
                    'Impressions': int(item['impressions']),
                    'Clicks': int(item['clicks']),
                    'Spend': float(item['spend']),
                    'Conversions': conversions,
                    'ConversionValue': revenue,
                    'Objective': objective
                })

            return pd.DataFrame(data)

        except ImportError:
            st.error("facebook_business library not installed.")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Failed to fetch Facebook Ads data: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_breakdown_data(_self, start_date, end_date, breakdown='region'):
        """
        Fetches data broken down by a specific dimension.
        Supported breakdowns: 'region', 'publisher_platform', 'platform_position' (placement)
        """
        if _self.use_mock:
            # Mock data
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            breakdown_values = {
                'region': ['California', 'New York', 'Texas', 'London', 'Maharashtra'],
                'publisher_platform': ['facebook', 'instagram', 'audience_network', 'messenger'],
                'platform_position': ['feed', 'story', 'right_hand_column', 'instream_video']
            }
            values = breakdown_values.get(breakdown, ['Unknown'])
            
            for date in dates:
                for val in values:
                    data.append({
                        'Date': date,
                        'Breakdown': val,
                        'Impressions': np.random.randint(100, 5000),
                        'Clicks': np.random.randint(10, 200),
                        'Spend': np.random.uniform(10, 100)
                    })
            return pd.DataFrame(data)

        if not _self.credentials:
            return pd.DataFrame()

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adsinsights import AdsInsights

            app_id = _self.credentials.get("app_id")
            app_secret = _self.credentials.get("app_secret")
            access_token = _self.credentials.get("access_token")
            ad_account_id = _self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)
            account = AdAccount(ad_account_id)
            
            fields = [
                AdsInsights.Field.spend,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.date_start,
            ]
            
            # Map friendly name to API breakdown
            api_breakdown_map = {
                'region': 'region',
                'publisher_platform': 'publisher_platform', # Platform (FB, IG)
                'platform_position': 'platform_position',   # Placement (Feed, Story)
            }
            api_breakdown = api_breakdown_map.get(breakdown, breakdown)

            params = {
                'time_range': {'since': start_date.strftime('%Y-%m-%d'), 'until': end_date.strftime('%Y-%m-%d')},
                'level': 'account', # Aggregate at account level for breakdown
                # 'time_increment': 1, # REMOVED to reduce API load
                'breakdowns': [api_breakdown]
            }

            insights = account.get_insights(fields=fields, params=params)
            data = []
            for item in insights:
                data.append({
                    'Date': pd.to_datetime(item['date_start']),
                    'Breakdown': item.get(api_breakdown, 'Unknown'),
                    'Impressions': int(item['impressions']),
                    'Clicks': int(item['clicks']),
                    'Spend': float(item['spend']),
                })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch breakdown data ({breakdown}): {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_ad_set_data(_self, start_date, end_date):
        """
        Fetches Ad Set level data.
        """
        if _self.use_mock:
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            for date in dates:
                for i in range(5):
                    data.append({
                        'Date': date,
                        'Campaign': f"Campaign {i%2 + 1}",
                        'AdSet': f"Ad Set {i}",
                        'Impressions': np.random.randint(100, 1000),
                        'Clicks': np.random.randint(10, 100),
                        'Spend': np.random.uniform(50, 200),
                        'Conversions': np.random.randint(0, 5),
                        'ConversionValue': np.random.uniform(0, 500)
                    })
            return pd.DataFrame(data)

        if not _self.credentials:
            return pd.DataFrame()

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adsinsights import AdsInsights

            app_id = _self.credentials.get("app_id")
            app_secret = _self.credentials.get("app_secret")
            access_token = _self.credentials.get("access_token")
            ad_account_id = _self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)
            account = AdAccount(ad_account_id)
            
            fields = [
                AdsInsights.Field.campaign_name,
                AdsInsights.Field.campaign_id,
                AdsInsights.Field.adset_name,
                AdsInsights.Field.adset_id,
                AdsInsights.Field.spend,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.actions,
                AdsInsights.Field.action_values,
                AdsInsights.Field.date_start,
                AdsInsights.Field.objective, # Add objective here too
            ]
            params = {
                'time_range': {'since': start_date.strftime('%Y-%m-%d'), 'until': end_date.strftime('%Y-%m-%d')},
                'level': 'adset',
                # 'time_increment': 1, # REMOVED to reduce API load
            }

            insights = account.get_insights(fields=fields, params=params)
            data = []
            for item in insights:
                conversions = 0
                objective = item.get('objective', '').upper()
                lead_action_types = ['lead', 'on_facebook_lead', 'offsite_conversion.fb_pixel_lead', 'mobile_app_install']

                if 'actions' in item:
                    for action in item['actions']:
                        action_type = action['action_type']
                        if 'LEAD' in objective:
                            if action_type in lead_action_types:
                                conversions += int(action['value'])
                        else:
                            if action_type in ['offsite_conversion.fb_pixel_purchase', 'purchase', 'omni_purchase']:
                                conversions += int(action['value'])
                
                revenue = 0.0
                if 'action_values' in item:
                    for action in item['action_values']:
                        if action['action_type'] in ['offsite_conversion.fb_pixel_purchase', 'purchase', 'omni_purchase']:
                            revenue += float(action['value'])

                data.append({
                    'Date': pd.to_datetime(item['date_start']),
                    'Campaign': item['campaign_name'],
                    'Campaign ID': item['campaign_id'],
                    'AdSet': item['adset_name'],
                    'AdSet ID': item['adset_id'],
                    'Source': 'Facebook Ads',
                    'Impressions': int(item['impressions']),
                    'Clicks': int(item['clicks']),
                    'Spend': float(item['spend']),
                    'Conversions': conversions,
                    'ConversionValue': revenue
                })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Ad Set data: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_ad_data(_self, start_date, end_date):
        """
        Fetches Ad level data (Creative).
        """
        if _self.use_mock:
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            for date in dates:
                for i in range(5):
                    data.append({
                        'Date': date,
                        'Campaign': f"Campaign {i%2 + 1}",
                        'AdSet': f"Ad Set {i}",
                        'Ad': f"Ad {i}",
                        'Impressions': np.random.randint(50, 500),
                        'Clicks': np.random.randint(5, 50),
                        'Spend': np.random.uniform(20, 100),
                        'Conversions': np.random.randint(0, 3),
                        'ConversionValue': np.random.uniform(0, 300)
                    })
            return pd.DataFrame(data)
            
        if not _self.credentials:
            return pd.DataFrame()

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.adsinsights import AdsInsights

            app_id = _self.credentials.get("app_id")
            app_secret = _self.credentials.get("app_secret")
            access_token = _self.credentials.get("access_token")
            ad_account_id = _self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)
            account = AdAccount(ad_account_id)
            
            fields = [
                AdsInsights.Field.campaign_name,
                AdsInsights.Field.adset_name,
                AdsInsights.Field.ad_name,
                AdsInsights.Field.spend,
                AdsInsights.Field.impressions,
                AdsInsights.Field.clicks,
                AdsInsights.Field.actions,
                AdsInsights.Field.action_values,
                AdsInsights.Field.date_start,
            ]
            params = {
                'time_range': {'since': start_date.strftime('%Y-%m-%d'), 'until': end_date.strftime('%Y-%m-%d')},
                'level': 'ad',
                # 'time_increment': 1, # REMOVED to reduce API load
            }

            insights = account.get_insights(fields=fields, params=params)
            data = []
            for item in insights:
                conversions = 0
                if 'actions' in item:
                    for action in item['actions']:
                        if action['action_type'] == 'offsite_conversion.fb_pixel_purchase':
                            conversions += int(action['value'])
                
                revenue = 0.0
                if 'action_values' in item:
                    for action in item['action_values']:
                        if action['action_type'] == 'offsite_conversion.fb_pixel_purchase':
                            revenue += float(action['value'])

                data.append({
                    'Date': pd.to_datetime(item['date_start']),
                    'Campaign': item['campaign_name'],
                    'AdSet': item['adset_name'],
                    'Ad': item['ad_name'],
                    'Source': 'Facebook Ads',
                    'Impressions': int(item['impressions']),
                    'Clicks': int(item['clicks']),
                    'Spend': float(item['spend']),
                    'Conversions': conversions,
                    'ConversionValue': revenue
                })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Ad data: {e}")
            return pd.DataFrame()

    @st.cache_data(ttl=3600)
    def get_ad_urls(_self):
        """
        Fetches a mapping of Ad ID to Landing Page URL.
        Note: This requires fetching Ad Creatives.
        """
        if _self.use_mock:
            # Mock URLs
            return {
                'Ad 0': 'https://example.com/landing-page-a',
                'Ad 1': 'https://example.com/landing-page-b',
                'Ad 2': 'https://example.com/landing-page-a',
                'Ad 3': 'https://example.com/landing-page-c',
                'Ad 4': 'https://example.com/landing-page-b'
            }

        if not _self.credentials:
            return {}

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            from facebook_business.adobjects.ad import Ad
            
            app_id = _self.credentials.get("app_id")
            app_secret = _self.credentials.get("app_secret")
            access_token = _self.credentials.get("access_token")
            ad_account_id = _self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)
            account = AdAccount(ad_account_id)
            
            # Fetch Ads with Creative fields
            fields = [
                Ad.Field.name,
                Ad.Field.id,
                Ad.Field.creative
            ]
            # We fetch all ads (active and paused) to build the map
            ads = account.get_ads(fields=fields, params={'limit': 100}) # Reduced limit to avoid 500 error
            
            ad_url_map = {}
            
            # For each ad, we need to inspect the creative. 
            # Ideally we batch fetch creatives, but for simplicity we'll rely on the ad object having the creative ID,
            # and then we might need to fetch creative details if the link isn't directly there.
            # Actually, Ad object -> Creative -> object_story_spec -> link_data -> link
            
            # To avoid N+1 queries, let's try to fetch creative details in the same call or batch.
            # The 'creative' field in Ad is just a reference. We need to fetch creatives separately or use field expansion.
            
            # Better approach: Fetch AdCreatives directly
            from facebook_business.adobjects.adcreative import AdCreative
            creative_fields = [
                AdCreative.Field.id,
                AdCreative.Field.object_story_spec,
                AdCreative.Field.call_to_action_type,
                AdCreative.Field.asset_feed_spec # For dynamic creative
            ]
            creatives = account.get_ad_creatives(fields=creative_fields, params={'limit': 100}) # Reduced limit
            
            creative_url_map = {}
            for creative in creatives:
                url = "Unknown"
                # Try to find link in object_story_spec
                spec = creative.get('object_story_spec', {})
                if spec:
                    link_data = spec.get('link_data', {})
                    if link_data:
                        url = link_data.get('link')
                    else:
                        # Video data?
                        video_data = spec.get('video_data', {})
                        if video_data:
                            call_to_action = video_data.get('call_to_action', {})
                            value = call_to_action.get('value', {})
                            url = value.get('link')
                
                creative_url_map[creative['id']] = url

            # Now map Ad -> Creative -> URL
            # Re-fetch ads with creative id
            for ad in ads:
                creative_id = ad.get('creative', {}).get('id')
                if creative_id:
                    ad_url_map[ad['name']] = creative_url_map.get(creative_id, "Unknown") # Map by Name to match Insights data
                    # Also map by ID if needed
                    ad_url_map[ad['id']] = creative_url_map.get(creative_id, "Unknown")
            
            return ad_url_map

        except Exception as e:
            st.error(f"Failed to fetch Ad URLs: {e}")
            return {}

    def validate_credentials(self):
        """
        Validates credentials by attempting a simple API call.
        Returns (bool, str): (IsValid, Message)
        """
        if self.use_mock:
            return True, "Mock credentials are always valid."
            
        if not self.credentials:
             return False, "No credentials provided."

        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount
            
            app_id = self.credentials.get("app_id")
            app_secret = self.credentials.get("app_secret")
            access_token = self.credentials.get("access_token")
            ad_account_id = self.credentials.get("ad_account_id")

            FacebookAdsApi.init(app_id, app_secret, access_token)
            account = AdAccount(ad_account_id)
            account.api_get(fields=['name']) # Try to fetch basic info
            
            return True, "Connection successful!"
        except ImportError:
            return False, "facebook_business library not installed."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
