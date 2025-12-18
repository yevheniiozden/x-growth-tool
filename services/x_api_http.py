"""HTTP-based X/Twitter API Client for twitterapi.io and similar services"""
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json


class HTTPAPIClient:
    """HTTP client for twitterapi.io API"""
    
    def __init__(self, api_key: str):
        """
        Initialize HTTP API client
        
        Args:
            api_key: API key from twitterapi.io
        """
        self.api_key = api_key
        # Try standard Twitter API v2 first (most third-party services proxy to this)
        self.base_url = "https://api.twitter.com/2"
        self.headers = {
            "Authorization": f"Bearer {api_key}",  # Primary: Bearer token
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
        
        Returns:
            Response JSON or None
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            else:
                response = requests.request(method, url, headers=self.headers, json=params, timeout=10)
            
            if response.status_code == 401:
                # Log the error for debugging
                print(f"HTTP API authentication error: {response.status_code}")
                print(f"URL: {url}")
                print(f"Response: {response.text[:200]}")
                # Try alternative base URL if current one fails
                if "api.twitter.com" in self.base_url:
                    # Try twitterapi.io specific endpoint
                    self.base_url = "https://api.twitterapi.io/v1"
                    url = f"{self.base_url}{endpoint}"
                    response = requests.get(url, headers=self.headers, params=params, timeout=10)
                elif "twitterapi.io" in self.base_url:
                    # Try with X-API-Key header instead
                    self.headers = {
                        "X-API-Key": self.api_key,
                        "Content-Type": "application/json"
                    }
                    response = requests.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print(f"HTTP API authentication error: {response.status_code} - {response.text[:200]}")
                return None
            else:
                print(f"HTTP API error: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"HTTP API request error: {e}")
            return None
    
    def get_user(self, username: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]:
        """
        Get user information
        
        Args:
            username: Twitter username
            user_id: Twitter user ID
        
        Returns:
            User object (compatible with tweepy format)
        """
        if username:
            endpoint = f"/users/by/username/{username}"
        elif user_id:
            endpoint = f"/users/{user_id}"
        else:
            return None
        
        data = self._make_request("GET", endpoint)
        if not data:
            return None
        
        # Return object compatible with tweepy format
        return type('User', (), {
            'data': type('UserData', (), {
                'id': data.get('id'),
                'username': data.get('username'),
                'name': data.get('name'),
                'description': data.get('description'),
                'public_metrics': data.get('public_metrics', {}),
                'verified': data.get('verified', False)
            })()
        })()
    
    def get_users_tweets(
        self,
        id: str,
        max_results: int = 100,
        start_time: Optional[datetime] = None,
        tweet_fields: Optional[List[str]] = None,
        pagination_token: Optional[str] = None
    ) -> Any:
        """
        Get user's tweets
        
        Args:
            id: User ID
            max_results: Maximum results
            start_time: Start time filter
            tweet_fields: Fields to include
            pagination_token: Pagination token
        
        Returns:
            Response object (compatible with tweepy format)
        """
        endpoint = f"/users/{id}/tweets"
        params = {
            "max_results": min(max_results, 100)
        }
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        
        if pagination_token:
            params["pagination_token"] = pagination_token
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Convert to tweepy-compatible format
        tweets = []
        for tweet_data in data.get('data', []):
            tweet = type('Tweet', (), {
                'id': tweet_data.get('id'),
                'text': tweet_data.get('text'),
                'created_at': datetime.fromisoformat(tweet_data.get('created_at', '').replace('Z', '+00:00')) if tweet_data.get('created_at') else None,
                'author_id': tweet_data.get('author_id'),
                'public_metrics': type('Metrics', (), tweet_data.get('public_metrics', {}))()
            })()
            tweets.append(tweet)
        
        return type('Response', (), {
            'data': tweets,
            'meta': data.get('meta', {})
        })()
    
    def search_recent_tweets(
        self,
        query: str,
        max_results: int = 100,
        tweet_fields: Optional[List[str]] = None,
        user_fields: Optional[List[str]] = None
    ) -> Any:
        """
        Search for recent tweets
        
        Args:
            query: Search query
            max_results: Maximum results
            tweet_fields: Fields to include
            user_fields: User fields to include
        
        Returns:
            Response object (compatible with tweepy format)
        """
        endpoint = "/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max_results, 100)
        }
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Convert to tweepy-compatible format
        tweets = []
        for tweet_data in data.get('data', []):
            tweet = type('Tweet', (), {
                'id': tweet_data.get('id'),
                'text': tweet_data.get('text'),
                'created_at': datetime.fromisoformat(tweet_data.get('created_at', '').replace('Z', '+00:00')) if tweet_data.get('created_at') else None,
                'author_id': tweet_data.get('author_id'),
                'public_metrics': type('Metrics', (), tweet_data.get('public_metrics', {}))()
            })()
            tweets.append(tweet)
        
        return type('Response', (), {
            'data': tweets,
            'meta': data.get('meta', {})
        })()
    
    def get_users(self, ids: List[str], user_fields: Optional[List[str]] = None) -> Any:
        """
        Get multiple users by IDs
        
        Args:
            ids: List of user IDs
            user_fields: Fields to include
        
        Returns:
            Response object (compatible with tweepy format)
        """
        endpoint = "/users"
        params = {
            "ids": ",".join(ids[:100])  # Limit to 100
        }
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None})()
        
        # Convert to tweepy-compatible format
        users = []
        for user_data in data.get('data', []):
            user = type('User', (), {
                'id': user_data.get('id'),
                'username': user_data.get('username'),
                'name': user_data.get('name'),
                'description': user_data.get('description'),
                'public_metrics': type('Metrics', (), user_data.get('public_metrics', {}))(),
                'verified': user_data.get('verified', False),
                'profile_image_url': user_data.get('profile_image_url')
            })()
            users.append(user)
        
        return type('Response', (), {'data': users})()
    
    def get_list_tweets(
        self,
        id: str,
        max_results: int = 100,
        start_time: Optional[datetime] = None,
        tweet_fields: Optional[List[str]] = None,
        pagination_token: Optional[str] = None
    ) -> Any:
        """
        Get tweets from a list
        
        Args:
            id: List ID
            max_results: Maximum results
            start_time: Start time filter
            tweet_fields: Fields to include
            pagination_token: Pagination token
        
        Returns:
            Response object (compatible with tweepy format)
        """
        endpoint = f"/lists/{id}/tweets"
        params = {
            "max_results": min(max_results, 100)
        }
        
        if start_time:
            params["start_time"] = start_time.isoformat()
        
        if pagination_token:
            params["pagination_token"] = pagination_token
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Convert to tweepy-compatible format
        tweets = []
        for tweet_data in data.get('data', []):
            tweet = type('Tweet', (), {
                'id': tweet_data.get('id'),
                'text': tweet_data.get('text'),
                'created_at': datetime.fromisoformat(tweet_data.get('created_at', '').replace('Z', '+00:00')) if tweet_data.get('created_at') else None,
                'author_id': tweet_data.get('author_id'),
                'public_metrics': type('Metrics', (), tweet_data.get('public_metrics', {}))()
            })()
            tweets.append(tweet)
        
        return type('Response', (), {
            'data': tweets,
            'meta': data.get('meta', {})
        })()
    
    def get_list_members(
        self,
        id: str,
        max_results: int = 100,
        user_fields: Optional[List[str]] = None,
        pagination_token: Optional[str] = None
    ) -> Any:
        """
        Get members of a list
        
        Args:
            id: List ID
            max_results: Maximum results
            user_fields: Fields to include
            pagination_token: Pagination token
        
        Returns:
            Response object (compatible with tweepy format)
        """
        endpoint = f"/lists/{id}/members"
        params = {
            "max_results": min(max_results, 100)
        }
        
        if pagination_token:
            params["pagination_token"] = pagination_token
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Convert to tweepy-compatible format
        users = []
        for user_data in data.get('data', []):
            user = type('User', (), {
                'id': user_data.get('id'),
                'username': user_data.get('username'),
                'name': user_data.get('name')
            })()
            users.append(user)
        
        return type('Response', (), {
            'data': users,
            'meta': data.get('meta', {})
        })()
    
    def get_user_lists(
        self,
        user_id: Optional[str] = None,
        max_results: int = 100
    ) -> Any:
        """
        Get user's lists
        
        Args:
            user_id: User ID
            max_results: Maximum results
        
        Returns:
            Response object (compatible with tweepy format)
        """
        if not user_id:
            return type('Response', (), {'data': None})()
        
        endpoint = f"/users/{user_id}/owned_lists"
        params = {
            "max_results": min(max_results, 100)
        }
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None})()
        
        # Convert to tweepy-compatible format
        lists = []
        for list_data in data.get('data', []):
            list_obj = type('List', (), {
                'id': list_data.get('id'),
                'name': list_data.get('name'),
                'description': list_data.get('description')
            })()
            lists.append(list_obj)
        
        return type('Response', (), {'data': lists})()

