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
        
        # Log request details for debugging
        print(f"HTTP API Request: {method} {url}")
        print(f"Headers: {list(self.headers.keys())}")
        if params:
            print(f"Params: {params}")
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
            else:
                response = requests.request(method, url, headers=self.headers, json=params, timeout=10)
            
            # Log response details
            print(f"HTTP API Response: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                try:
                    # Check content type before parsing
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'application/json' in content_type or 'text/json' in content_type:
                        json_data = response.json()
                        print(f"Response data type: {type(json_data)}")
                        return json_data
                    else:
                        # Try to parse anyway, but log warning
                        print(f"Warning: Non-JSON content type: {content_type}")
                        try:
                            json_data = response.json()
                            return json_data
                        except:
                            print(f"Non-JSON response (first 200 chars): {response.text[:200]}")
                            return None
                except ValueError as json_error:
                    # Response is not valid JSON
                    print(f"JSON parsing error: {json_error}")
                    print(f"Response text (first 200 chars): {response.text[:200]}")
                    return None
            elif response.status_code == 401:
                print(f"HTTP API authentication error: {response.status_code}")
                print(f"URL: {url}")
                print(f"Response: {response.text[:200]}")
                print(f"Headers sent: {list(self.headers.keys())}")
                return None
            else:
                print(f"HTTP API error: {response.status_code}")
                print(f"URL: {url}")
                print(f"Response: {response.text[:200]}")
                return None
                
        except Exception as e:
            print(f"HTTP API request error: {e}")
            import traceback
            traceback.print_exc()
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
            # URL encode username to handle special characters
            from urllib.parse import quote
            endpoint = f"/twitter/user/info?userName={quote(username)}"
        elif user_id:
            endpoint = f"/twitter/user/info?userId={user_id}"
        else:
            return None
        
        data = self._make_request("GET", endpoint)
        if not data:
            return None
        
        # Handle string responses (shouldn't happen, but be safe)
        if isinstance(data, str):
            print(f"Warning: get_user received string response: {data[:100]}")
            return None
        
        # twitterapi.io response format: {"data": {...}, "status": str, "msg": str}
        if isinstance(data, dict):
            user_data = data.get('data', {})
            if not user_data:
                print(f"Warning: get_user response missing data field: {data.get('msg', 'Unknown error')}")
                return None
        else:
            print(f"Warning: get_user received unexpected data type: {type(data)}")
            return None
        
        # Return object compatible with tweepy format
        # twitterapi.io uses camelCase field names
        return type('User', (), {
            'data': type('UserData', (), {
                'id': str(user_data.get('id', '')),
                'username': user_data.get('userName', ''),  # camelCase
                'name': user_data.get('name', ''),
                'description': user_data.get('description', ''),
                'public_metrics': type('Metrics', (), {
                    'followers_count': user_data.get('followers', 0),  # API uses 'followers'
                    'following_count': user_data.get('following', 0),  # API uses 'following'
                    'tweet_count': user_data.get('statusesCount', 0),  # API uses 'statusesCount'
                    'like_count': user_data.get('favouritesCount', 0)  # API uses 'favouritesCount'
                })(),
                'verified': user_data.get('isBlueVerified', False)  # API uses 'isBlueVerified'
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
        # URL encode parameters
        from urllib.parse import urlencode
        params_dict = {
            "userId": id,
            "count": min(max_results, 100)
        }
        endpoint = f"/twitter/user/lastTweets?{urlencode(params_dict)}"
        params = {}
        
        # Note: twitterapi.io may not support all these parameters
        # Adjust based on actual API documentation
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Handle string responses
        if isinstance(data, str):
            print(f"Warning: get_users_tweets received string response: {data[:100]}")
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # twitterapi.io response format - handle both nested and direct formats
        if isinstance(data, dict):
            tweets_data = data.get('data', data.get('tweets', []))
        elif isinstance(data, list):
            tweets_data = data
        else:
            print(f"Warning: get_users_tweets received unexpected data type: {type(data)}")
            return type('Response', (), {'data': None, 'meta': {}})()
        
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
        # URL encode query parameter - use correct endpoint with underscore
        from urllib.parse import urlencode
        params_dict = {
            "query": query,
            "queryType": "Latest"  # Required parameter, default is "Latest"
        }
        endpoint = f"/twitter/tweet/advanced_search?{urlencode(params_dict)}"
        params = {}
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # Handle string responses
        if isinstance(data, str):
            print(f"Warning: search_recent_tweets received string response: {data[:100]}")
            return type('Response', (), {'data': None, 'meta': {}})()
        
        # twitterapi.io response format
        if isinstance(data, dict):
            tweets_data = data.get('data', data.get('tweets', []))
        elif isinstance(data, list):
            tweets_data = data
        else:
            print(f"Warning: search_recent_tweets received unexpected data type: {type(data)}")
            return type('Response', (), {'data': None, 'meta': {}})()
        
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
        # twitterapi.io batch endpoint - use correct endpoint name
        from urllib.parse import urlencode
        params_dict = {
            "userIds": ','.join(ids[:100])  # Limit to 100, comma-separated
        }
        endpoint = f"/twitter/user/batch_info_by_ids?{urlencode(params_dict)}"
        params = {}
        
        data = self._make_request("GET", endpoint, params)
        if not data:
            return type('Response', (), {'data': None})()
        
        # Handle string responses
        if isinstance(data, str):
            print(f"Warning: get_users received string response: {data[:100]}")
            return type('Response', (), {'data': None})()
        
        # twitterapi.io response format: {"users": [...], "status": str, "msg": str}
        if isinstance(data, dict):
            users_data = data.get('users', [])
        elif isinstance(data, list):
            users_data = data
        else:
            print(f"Warning: get_users received unexpected data type: {type(data)}")
            return type('Response', (), {'data': None})()
        
        # Convert to tweepy-compatible format
        users = []
        for user_data in users_data:
            # twitterapi.io uses camelCase field names
            user = type('User', (), {
                'id': str(user_data.get('id', '')),
                'username': user_data.get('userName', ''),  # camelCase
                'name': user_data.get('name', ''),
                'description': user_data.get('description', ''),
                'public_metrics': type('Metrics', (), {
                    'followers_count': user_data.get('followers', 0),  # API uses 'followers' not 'followersCount'
                    'following_count': user_data.get('following', 0),  # API uses 'following' not 'followingCount'
                    'tweet_count': user_data.get('statusesCount', 0),  # API uses 'statusesCount'
                    'like_count': user_data.get('favouritesCount', 0)  # API uses 'favouritesCount'
                })(),
                'verified': user_data.get('isBlueVerified', False),  # API uses 'isBlueVerified'
                'profile_image_url': user_data.get('profilePicture', '')  # API uses 'profilePicture'
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
        # twitterapi.io endpoint for list members - use correct parameter name
        from urllib.parse import urlencode
        params_dict = {
            "list_id": id  # Parameter is list_id, not listId
        }
        # Note: max_results is handled by pagination with cursor, page size is 20
        if pagination_token:
            params_dict["cursor"] = pagination_token
        endpoint = f"/twitter/list/members?{urlencode(params_dict)}"
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

