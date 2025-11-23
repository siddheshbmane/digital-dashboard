import pandas as pd
import numpy as np
from datetime import timedelta
import streamlit as st

class GoogleAdsConnector:
    def __init__(self, credentials=None, use_mock=True):
        self.credentials = credentials
        self.use_mock = use_mock

    def get_data(self, start_date, end_date):
        if self.use_mock:
            return self._get_mock_data(start_date, end_date)
        else:
            return self._get_real_data(start_date, end_date)

    def _get_mock_data(self, start_date, end_date):
        """
        Simulates fetching data from Google Ads API.
        """
        dates = pd.date_range(start=start_date, end=end_date)
        data = []
        
        campaigns = ['Search - Brand', 'Search - Generic', 'Display - Retargeting', 'Video - Awareness']
        
        for date in dates:
            for campaign in campaigns:
                impressions = np.random.randint(100, 10000)
                clicks = int(impressions * np.random.uniform(0.01, 0.05))
                spend = clicks * np.random.uniform(0.5, 5.0)
                conversions = int(clicks * np.random.uniform(0.02, 0.10))
                
                data.append({
                    'Date': date,
                    'Campaign': campaign,
                    'Source': 'Google Ads',
                    'Impressions': impressions,
                    'Clicks': clicks,
                    'Spend': round(spend, 2),
                    'Conversions': conversions
                })
                
        return pd.DataFrame(data)

    def _get_real_data(self, start_date, end_date):
        """
        Fetches data from Google Ads API.
        """
        if not self.credentials:
            st.error("Google Ads Credentials missing.")
            return pd.DataFrame()

        try:
            from google.ads.googleads.client import GoogleAdsClient
            from google.ads.googleads.errors import GoogleAdsException

            # Initialize client
            # Assuming credentials is a dict with necessary keys
            # In a real app, you might load this from a file or env vars
            # For this demo, we'll try to construct it from the dict
            
            # NOTE: This is a simplified setup. Real Google Ads auth is complex.
            # We will assume the user provides a dict compatible with load_from_dict
            
            # Initialize client
            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            
            # Set login_customer_id if provided (required for Manager Accounts accessing Client Accounts)
            login_customer_id = self.credentials.get("login_customer_id")
            if login_customer_id:
                client.login_customer_id = login_customer_id

            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id") # Must be provided

            query = f"""
                SELECT
                    campaign.name,
                    campaign.advertising_channel_type,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM campaign
                WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
            """

            stream = ga_service.search_stream(customer_id=customer_id, query=query)

            data = []
            for batch in stream:
                for row in batch.results:
                    data.append({
                        'Date': pd.to_datetime(row.segments.date),
                        'Campaign': row.campaign.name,
                        'Campaign Type': row.campaign.advertising_channel_type.name,
                        'Source': 'Google Ads',
                        'Impressions': row.metrics.impressions,
                        'Clicks': row.metrics.clicks,
                        'Spend': row.metrics.cost_micros / 1000000, # Convert micros to currency
                        'Conversions': row.metrics.conversions,
                        'ConversionValue': row.metrics.conversions_value
                    })

            return pd.DataFrame(data)

        except ImportError:
            st.error("google-ads library not installed.")
            return pd.DataFrame()
        except Exception as e:
            # Check for Manager Account error in string representation if specific exception handling fails
            error_str = str(e)
            if "REQUESTED_METRICS_FOR_MANAGER" in error_str:
                st.error("Error: You are using a Manager Account ID. Please use a Client Account ID to fetch metrics.")
            else:
                st.error(f"Failed to fetch Google Ads data: {e}")
            return pd.DataFrame()

    def get_geo_data(self, start_date, end_date):
        """
        Fetches Geographic view data (Location).
        """
        if self.use_mock:
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            locations = ['New York', 'California', 'Texas', 'London', 'Mumbai']
            for date in dates:
                for loc in locations:
                    data.append({
                        'Date': date,
                        'Location': loc,
                        'Impressions': np.random.randint(100, 2000),
                        'Clicks': np.random.randint(10, 100),
                        'Spend': np.random.uniform(10, 50)
                    })
            return pd.DataFrame(data)

        if not self.credentials:
            return pd.DataFrame()

        try:
            from google.ads.googleads.client import GoogleAdsClient
            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            if self.credentials.get("login_customer_id"):
                client.login_customer_id = self.credentials.get("login_customer_id")
            
            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id")
            
            # geographic_view is usually segmented by geo_target_constant
            # We need to join with geo_target_constant to get the name, but that's complex in GAQL (no joins).
            # Instead, we select geographic_view and segments.geo_target_region (or similar).
            # Actually, user wants "Location". `geographic_view` allows `segments.geo_target_city`, `segments.geo_target_state`, etc.
            
            query = f"""
                SELECT
                    segments.geo_target_state,
                    segments.geo_target_city,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros
                FROM geographic_view
                WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
            """
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            data = []
            for batch in stream:
                for row in batch.results:
                    # Construct a location string
                    loc = row.segments.geo_target_city or row.segments.geo_target_state or "Unknown"
                    data.append({
                        'Location': loc,
                        'Impressions': row.metrics.impressions,
                        'Clicks': row.metrics.clicks,
                        'Spend': row.metrics.cost_micros / 1000000
                    })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Geo data: {e}")
            return pd.DataFrame()

    def get_keyword_data(self, start_date, end_date):
        """
        Fetches Keyword view data.
        """
        if self.use_mock:
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            keywords = ['buy shoes', 'best sneakers', 'running shoes', 'discount footwear']
            for date in dates:
                for kw in keywords:
                    data.append({
                        'Date': date,
                        'Keyword': kw,
                        'Impressions': np.random.randint(50, 500),
                        'Clicks': np.random.randint(5, 50),
                        'Spend': np.random.uniform(5, 30)
                    })
            return pd.DataFrame(data)

        if not self.credentials:
            return pd.DataFrame()

        try:
            from google.ads.googleads.client import GoogleAdsClient
            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            if self.credentials.get("login_customer_id"):
                client.login_customer_id = self.credentials.get("login_customer_id")
            
            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id")
            
            query = f"""
                SELECT
                    ad_group_criterion.keyword.text,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM keyword_view
                WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
            """
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            data = []
            for batch in stream:
                for row in batch.results:
                    data.append({
                        'Keyword': row.ad_group_criterion.keyword.text,
                        'Impressions': row.metrics.impressions,
                        'Clicks': row.metrics.clicks,
                        'Spend': row.metrics.cost_micros / 1000000,
                        'Conversions': row.metrics.conversions,
                        'ConversionValue': row.metrics.conversions_value
                    })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Keyword data: {e}")
            return pd.DataFrame()

    def get_ad_group_data(self, start_date, end_date):
        """
        Fetches Ad Group level data.
        """
        if self.use_mock:
            # Mock data for Ad Groups
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            for date in dates:
                for i in range(5):
                    data.append({
                        'Date': date,
                        'Campaign': f"Campaign {i%2 + 1}",
                        'AdGroup': f"Ad Group {i}",
                        'Impressions': np.random.randint(100, 1000),
                        'Clicks': np.random.randint(10, 100),
                        'Spend': np.random.uniform(50, 200),
                        'Conversions': np.random.randint(0, 5),
                        'ConversionValue': np.random.uniform(0, 500)
                    })
            return pd.DataFrame(data)
            
        # Real API
        if not self.credentials:
            return pd.DataFrame()
            
        try:
            from google.ads.googleads.client import GoogleAdsClient
            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            if self.credentials.get("login_customer_id"):
                client.login_customer_id = self.credentials.get("login_customer_id")
            
            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id")
            
            query = f"""
                SELECT
                    campaign.name,
                    campaign.id,
                    ad_group.name,
                    ad_group.id,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM ad_group
                WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
            """
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            data = []
            for batch in stream:
                for row in batch.results:
                    data.append({
                        'Date': pd.to_datetime(row.segments.date),
                        'Campaign': row.campaign.name,
                        'Campaign ID': row.campaign.id,
                        'AdGroup': row.ad_group.name,
                        'AdGroup ID': row.ad_group.id,
                        'Source': 'Google Ads',
                        'Impressions': row.metrics.impressions,
                        'Clicks': row.metrics.clicks,
                        'Spend': row.metrics.cost_micros / 1000000,
                        'Conversions': row.metrics.conversions,
                        'ConversionValue': row.metrics.conversions_value
                    })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Ad Group data: {e}")
            return pd.DataFrame()

    def get_ad_data(self, start_date, end_date):
        """
        Fetches Ad level data (Creative).
        """
        if self.use_mock:
            # Mock data for Ads
            dates = pd.date_range(start=start_date, end=end_date)
            data = []
            for date in dates:
                for i in range(5):
                    data.append({
                        'Date': date,
                        'Campaign': f"Campaign {i%2 + 1}",
                        'AdGroup': f"Ad Group {i}",
                        'Ad': f"Ad {i} - Headline",
                        'Impressions': np.random.randint(50, 500),
                        'Clicks': np.random.randint(5, 50),
                        'Spend': np.random.uniform(20, 100),
                        'Conversions': np.random.randint(0, 3),
                        'ConversionValue': np.random.uniform(0, 300)
                    })
            return pd.DataFrame(data)

        # Real API
        if not self.credentials:
            return pd.DataFrame()
            
        try:
            from google.ads.googleads.client import GoogleAdsClient
            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            if self.credentials.get("login_customer_id"):
                client.login_customer_id = self.credentials.get("login_customer_id")
            
            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id")
            
            # Fetching ad_group_ad details
            query = f"""
                SELECT
                    campaign.name,
                    ad_group.name,
                    ad_group_ad.ad.name,
                    ad_group_ad.ad.id,
                    ad_group_ad.ad.final_urls,
                    segments.date,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions,
                    metrics.conversions_value
                FROM ad_group_ad
                WHERE segments.date BETWEEN '{start_date.strftime('%Y-%m-%d')}' AND '{end_date.strftime('%Y-%m-%d')}'
            """
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            data = []
            for batch in stream:
                for row in batch.results:
                    # Ad name might be empty, use ID
                    ad_name = row.ad_group_ad.ad.name or f"Ad {row.ad_group_ad.ad.id}"
                    
                    # Extract Final URL (take the first one)
                    final_url = "Unknown"
                    if row.ad_group_ad.ad.final_urls:
                        final_url = row.ad_group_ad.ad.final_urls[0]

                    data.append({
                        'Date': pd.to_datetime(row.segments.date),
                        'Campaign': row.campaign.name,
                        'AdGroup': row.ad_group.name,
                        'Ad': ad_name,
                        'Landing Page': final_url,
                        'Source': 'Google Ads',
                        'Impressions': row.metrics.impressions,
                        'Clicks': row.metrics.clicks,
                        'Spend': row.metrics.cost_micros / 1000000,
                        'Conversions': row.metrics.conversions,
                        'ConversionValue': row.metrics.conversions_value
                    })
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Failed to fetch Ad data: {e}")
            return pd.DataFrame()

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
            from google.ads.googleads.client import GoogleAdsClient
            from google.ads.googleads.errors import GoogleAdsException

            config = {**self.credentials, "use_proto_plus": True}
            client = GoogleAdsClient.load_from_dict(config)
            
            # Set login_customer_id if provided
            login_customer_id = self.credentials.get("login_customer_id")
            if login_customer_id:
                client.login_customer_id = login_customer_id
                
            ga_service = client.get_service("GoogleAdsService")
            customer_id = self.credentials.get("customer_id")

            # Try a minimal query to check access and account type
            # We query 'customer' resource which is allowed for Manager Accounts too, 
            # but we check if it is a manager.
            query = "SELECT customer.id, customer.manager, customer.descriptive_name FROM customer LIMIT 1"
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            
            for batch in stream:
                for row in batch.results:
                    if row.customer.manager:
                         return False, f"Error: Account '{row.customer.descriptive_name}' ({row.customer.id}) is a Manager Account. Please use a Client Account ID."
            
            return True, "Connection successful!"

        except ImportError:
            return False, "google-ads library not installed."
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
