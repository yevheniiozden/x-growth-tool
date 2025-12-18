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
        # twitterapi.io base URL
        self.base_url = "https://api.twitterapi.io"
        self.headers = {
            "x-api-key": api_key,  # twitterapi.io requires x-api-key header
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
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                print(f"HTTP API authentication error: {response.status_code} - {response.text[:200]}")
                print(f"URL: {url}")
                print(f"Headers: {list(self.headers.keys())}")
                return None
            else:
                print(f"HTTP API error: {response.status_code} - {response.text[:200]}")
                print(f"URL: {url}")
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
            endpoint = f"/twitter/user/info?userName={username}"
        elif user_id:
            endpoint = f"/twitter/user/info?userId={user_id}"
        else:
            return None
        
        data = self._make_request("GET", endpoint)
        if not data:
            return None
        
        # twitterapi.io response format may differ, handle both formats
        # Check if data is nested or direct
        user_data = data.get('data', data) if isinstance(data, dict) else data
        
        # Return object compatible with tweepy format
        return type('User', (), {
            'data': type('UserData', (), {
                'id': str(user_data.get('id', user_data.get('userId', ''))),
                'username': user_data.get('username', user_data.get('userName', '')),
                'name': user_data.get('name', user_data.get('displayName', '')),
                'description': user_data.get('description', user_data.get('bio', '')),
                'public_metrics': type('Metrics', (), {
                    'followers_count': user_data.get('followersCount', user_data.get('public_metrics', {}).get('followers_count', 0)),
                    'following_count': user_data.get('followingCount', user_data.get('public_metrics', {}).get('following_count', 0)),
                    'tweet_count': user_data.get('tweetCount', user_data.get('public_metrics', {}).get('tweet_count', 0)),
                    'like_count': user_data.get('likeCount', user_data.get('public_metrics', {}).get('like_count', 0))
                })(),
                'verified': user_data.get('verified', False)
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
        endpoint = f"/twitter/user/lastTweets?userId={id}&count={min(max_results, 100)}"
        params = {}
        
        # Note: twitterapi.io may not support all these parameters
        # Adjust based on actual API documentation
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # twitterapi.io response format - handle both nested and direct formats
        tweets_data = data.get('data', data.get('tweets', [])) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Convert to tweepy-compatible format
        tweets = []
        for tweet_data in tweets_data:
            # Handle different response formats
            tweet_id = tweet_data.get('id', tweet_data.get('tweetId', ''))
            tweet_text = tweet_data.get('text', tweet_data.get('content', ''))
            created_at_str = tweet_data.get('created_at', tweet_data.get('createdAt', ''))
            
            # Parse created_at
            created_at = None
            if created_at_str:
                try:
                    # Try different date formats
                    if 'T' in created_at_str:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        # Try other formats if needed
                        created_at = datetime.fromisoformat(created_at_str)
                except:
                    pass
            
            # Get metrics
            metrics_data = tweet_data.get('public_metrics', tweet_data.get('metrics', {}))
            if not isinstance(metrics_data, dict):
                metrics_data = {}
            
            tweet = type('Tweet', (), {
                'id': str(tweet_id),
                'text': tweet_text,
                'created_at': created_at,
                'author_id': str(id),  # User ID is the author
                'public_metrics': type('Metrics', (), {
                    'like_count': metrics_data.get('like_count', metrics_data.get('likeCount', 0)),
                    'reply_count': metrics_data.get('reply_count', metrics_data.get('replyCount', 0)),
                    'retweet_count': metrics_data.get('retweet_count', metrics_data.get('retweetCount', 0))
                })()
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
        endpoint = f"/twitter/tweet/advancedSearch?query={query}&count={min(max_results, 100)}"
        params = {}
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # twitterapi.io response format
        tweets_data = data.get('data', data.get('tweets', [])) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Convert to tweepy-compatible format
        tweets = []
        for tweet_data in tweets_data:
            # Handle different response formats
            tweet_id = tweet_data.get('id', tweet_data.get('tweetId', ''))
            tweet_text = tweet_data.get('text', tweet_data.get('content', ''))
            created_at_str = tweet_data.get('created_at', tweet_data.get('createdAt', ''))
            author_id = tweet_data.get('author_id', tweet_data.get('userId', ''))
            
            # Parse created_at
            created_at = None
            if created_at_str:
                try:
                    if 'T' in created_at_str:
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    else:
                        created_at = datetime.fromisoformat(created_at_str)
                except:
                    pass
            
            # Get metrics
            metrics_data = tweet_data.get('public_metrics', tweet_data.get('metrics', {}))
            if not isinstance(metrics_data, dict):
                metrics_data = {}
            
            tweet = type('Tweet', (), {
                'id': str(tweet_id),
                'text': tweet_text,
                'created_at': created_at,
                'author_id': str(author_id) if author_id else None,
                'public_metrics': type('Metrics', (), {
                    'like_count': metrics_data.get('like_count', metrics_data.get('likeCount', 0)),
                    'reply_count': metrics_data.get('reply_count', metrics_data.get('replyCount', 0)),
                    'retweet_count': metrics_data.get('retweet_count', metrics_data.get('retweetCount', 0))
                })()
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
        # twitterapi.io batch endpoint
        endpoint = f"/twitter/user/batchUserInfo?userIds={','.join(ids[:100])}"  # Limit to 100
        params = {}
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None})()
        
        # twitterapi.io response format
        users_data = data.get('data', data.get('users', [])) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Convert to tweepy-compatible format
        users = []
        for user_data in users_data:
            user = type('User', (), {
                'id': str(user_data.get('id', user_data.get('userId', ''))),
                'username': user_data.get('username', user_data.get('userName', '')),
                'name': user_data.get('name', user_data.get('displayName', '')),
                'description': user_data.get('description', user_data.get('bio', '')),
                'public_metrics': type('Metrics', (), {
                    'followers_count': user_data.get('followersCount', user_data.get('public_metrics', {}).get('followers_count', 0)),
                    'following_count': user_data.get('followingCount', user_data.get('public_metrics', {}).get('following_count', 0)),
                    'tweet_count': user_data.get('tweetCount', user_data.get('public_metrics', {}).get('tweet_count', 0)),
                    'like_count': user_data.get('likeCount', user_data.get('public_metrics', {}).get('like_count', 0))
                })(),
                'verified': user_data.get('verified', False),
                'profile_image_url': user_data.get('profile_image_url', user_data.get('avatar', ''))
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
        
        Note: twitterapi.io may not have a direct list tweets endpoint
        This is a placeholder that may need to be implemented differently
        
        Args:
            id: List ID
            max_results: Maximum results
            start_time: Start time filter
            tweet_fields: Fields to include
            pagination_token: Pagination token
        
        Returns:
            Response object (compatible with tweepy format)
        """
        # twitterapi.io may not support this endpoint directly
        # Return empty for now - may need to get list members first, then their tweets
        print(f"Warning: get_list_tweets not fully implemented for twitterapi.io")
        return type('Response', (), {'data': None, 'meta': {}})()
    
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
        # twitterapi.io endpoint for list members
        endpoint = f"/twitter/list/members?listId={id}&count={min(max_results, 100)}"
        params = {}
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # twitterapi.io response format
        users_data = data.get('data', data.get('members', [])) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        
        # Convert to tweepy-compatible format
        users = []
        for user_data in users_data:
            user = type('User', (), {
                'id': str(user_data.get('id', user_data.get('userId', ''))),
                'username': user_data.get('username', user_data.get('userName', '')),
                'name': user_data.get('name', user_data.get('displayName', ''))
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
        
        Note: twitterapi.io may not have a direct endpoint for this
        This is a placeholder that may need to be implemented differently
        
        Args:
            user_id: User ID
            max_results: Maximum results
        
        Returns:
            Response object (compatible with tweepy format)
        """
        if not user_id:
            return type('Response', (), {'data': None})()
        
        # twitterapi.io may not support this endpoint directly
        print(f"Warning: get_user_lists not fully implemented for twitterapi.io")
        return type('Response', (), {'data': None})()

