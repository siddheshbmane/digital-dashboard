import streamlit as st
import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.ads.googleads.client import GoogleAdsClient
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.user import User

class AuthManager:
    def __init__(self):
        pass

    def google_oauth_flow(self, client_config):
        """
        Runs the Google Ads OAuth flow using InstalledAppFlow.
        client_config: Dict containing 'client_id' and 'client_secret'.
        Returns: refresh_token (str) or None
        """
        try:
            # Create a temporary client_secrets.json content
            client_secrets = {
                "installed": {
                    "client_id": client_config['client_id'],
                    "client_secret": client_config['client_secret'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
            
            # Scopes needed for Google Ads
            scopes = ["https://www.googleapis.com/auth/adwords"]

            flow = InstalledAppFlow.from_client_config(client_secrets, scopes=scopes)
            
            # Run the local server flow
            # Note: This opens a browser window on the server machine. 
            # Since this is a local app, it works.
            credentials = flow.run_local_server(port=0)
            
            return credentials.refresh_token
        except Exception as e:
            st.error(f"Google OAuth failed: {e}")
            return None

    def get_google_accounts(self, credentials):
        """
        Fetches accessible Google Ads accounts.
        credentials: Dict containing developer_token, client_id, client_secret, refresh_token.
        Returns: List of dicts [{'id': '123', 'name': 'Account Name', 'is_manager': True/False}]
        """
        try:
            # Initialize client without login_customer_id first to list accounts
            # We need to use a "dummy" login_customer_id or none if we are just listing accessible accounts
            # However, listing accessible accounts usually requires just the credentials.
            
            # Construct config for GoogleAdsClient
            config = {
                "developer_token": credentials['developer_token'],
                "client_id": credentials['client_id'],
                "client_secret": credentials['client_secret'],
                "refresh_token": credentials['refresh_token'],
                "use_proto_plus": True
            }
            
            client = GoogleAdsClient.load_from_dict(config)
            customer_service = client.get_service("CustomerService")
            
            # List accessible customers
            accessible_customers = customer_service.list_accessible_customers()
            
            accounts = []
            for resource_name in accessible_customers.resource_names:
                customer_id = resource_name.split("/")[1]
                # We could fetch more details for each, but that requires iterating and might be slow/fail if permissions vary.
                # For now, we list IDs. To get names, we'd need to query each.
                
                # Let's try to fetch details for each to get the name
                try:
                    ga_service = client.get_service("GoogleAdsService")
                    query = "SELECT customer.id, customer.descriptive_name, customer.manager FROM customer LIMIT 1"
                    # We must set login_customer_id to the customer_id we are querying to get its details if it's a client
                    # But we don't know if it's a client or manager yet.
                    # Actually, list_accessible_customers returns accounts we can login to directly.
                    
                    # Re-instantiate client with login_customer_id
                    client_specific = GoogleAdsClient.load_from_dict({**config, "login_customer_id": customer_id})
                    ga_service_specific = client_specific.get_service("GoogleAdsService")
                    
                    stream = ga_service_specific.search_stream(customer_id=customer_id, query=query)
                    for batch in stream:
                        for row in batch.results:
                            accounts.append({
                                'id': str(row.customer.id),
                                'name': row.customer.descriptive_name or f"Account {row.customer.id}",
                                'is_manager': row.customer.manager
                            })
                except Exception:
                    # If we fail to query details, just add the ID
                    accounts.append({'id': customer_id, 'name': f"Customer {customer_id}", 'is_manager': False})

            return accounts
        except Exception as e:
            st.error(f"Failed to fetch Google Ads accounts: {e}")
            return []

    def get_google_sub_accounts(self, manager_id, credentials):
        """
        Fetches sub-accounts for a given Manager Account.
        """
        try:
            config = {
                "developer_token": credentials['developer_token'],
                "client_id": credentials['client_id'],
                "client_secret": credentials['client_secret'],
                "refresh_token": credentials['refresh_token'],
                "login_customer_id": manager_id, # Important: Login as the Manager
                "use_proto_plus": True
            }
            
            client = GoogleAdsClient.load_from_dict(config)
            ga_service = client.get_service("GoogleAdsService")
            
            # Query customer_client to find direct children (level <= 1)
            # We filter for status = ENABLED to avoid cancelled accounts
            query = """
                SELECT 
                    customer_client.client_customer, 
                    customer_client.level, 
                    customer_client.manager, 
                    customer_client.descriptive_name, 
                    customer_client.id 
                FROM customer_client 
                WHERE 
                    customer_client.level <= 1 
                    AND customer_client.status = 'ENABLED'
            """
            
            stream = ga_service.search_stream(customer_id=manager_id, query=query)
            
            sub_accounts = []
            for batch in stream:
                for row in batch.results:
                    # Skip the manager itself (level 0)
                    if row.customer_client.level == 0:
                        continue
                        
                    sub_accounts.append({
                        'id': str(row.customer_client.id),
                        'name': row.customer_client.descriptive_name or f"Account {row.customer_client.id}",
                        'is_manager': row.customer_client.manager
                    })
            
            return sub_accounts

        except Exception as e:
            st.error(f"Failed to fetch sub-accounts: {e}")
            return []

    def get_facebook_accounts(self, credentials):
        """
        Fetches accessible Facebook Ad Accounts.
        credentials: Dict containing app_id, app_secret, access_token.
        Returns: List of dicts [{'id': 'act_123', 'name': 'Account Name'}]
        """
        try:
            FacebookAdsApi.init(
                credentials['app_id'], 
                credentials['app_secret'], 
                credentials['access_token']
            )
            
            me = User(fbid='me')
            my_accounts = me.get_ad_accounts(fields=['name', 'account_id'])
            
            accounts = []
            for acc in my_accounts:
                accounts.append({
                    'id': f"act_{acc['account_id']}",
                    'name': acc['name']
                })
            
            return accounts
        except Exception as e:
            st.error(f"Failed to fetch Facebook accounts: {e}")
            return []
