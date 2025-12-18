"""X/Twitter API Service - Wrapper for Twitter API v2"""
import tweepy
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import config

# Initialize Twitter API client
client = None
use_http_client = False
api_key = config.X_BEARER_TOKEN or config.X_API_KEY

# Detect if using twitterapi.io (has X_API_KEY but no X_BEARER_TOKEN)
# Skip tweepy initialization in this case
if config.X_API_KEY and not config.X_BEARER_TOKEN:
    print("Detected twitterapi.io API key - using HTTP client directly")
    use_http_client = True
else:
    # Try tweepy first (for official Twitter API)
    if api_key:
        try:
            # Use Bearer Token if available, otherwise try API Key as Bearer Token
            client = tweepy.Client(
                bearer_token=api_key,
                wait_on_rate_limit=True
            )
            # Don't test immediately - let it fail on first real call
            # This avoids unnecessary API calls and handles errors gracefully
        except Exception as e:
            print(f"Warning: Could not initialize Twitter client with Bearer Token: {e}")
            print("Will use HTTP client for twitterapi.io")
            use_http_client = True
            # Fallback: try with API Key + Secret if available
            if config.X_API_KEY and config.X_API_SECRET:
                try:
                    client = tweepy.Client(
                        consumer_key=config.X_API_KEY,
                        consumer_secret=config.X_API_SECRET,
                        wait_on_rate_limit=True
                    )
                    use_http_client = False
                except Exception as e2:
                    print(f"Warning: Could not initialize Twitter client: {e2}")
                    use_http_client = True

# If using HTTP client (twitterapi.io), initialize it
if use_http_client and api_key:
    try:
        from services.x_api_http import HTTPAPIClient
        client = HTTPAPIClient(api_key)
        print("Using HTTP client for twitterapi.io")
    except ImportError:
        print("Warning: HTTP client not available, API calls will fail")
        client = None


def get_user_timeline(
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    days_back: int = 30,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    Get user's timeline (their posts)
    
    Args:
        username: Twitter username (without @)
        user_id: Twitter user ID
        days_back: How many days back to fetch
        max_results: Maximum number of tweets to fetch
    
    Returns:
        List of tweet dictionaries
    """
    if not client:
        return []
    
    try:
        # Get user ID if username provided
        if username and not user_id:
            user = client.get_user(username=username)
            # Handle both tweepy and HTTP client responses
            if hasattr(user, 'data') and user.data:
                user_id = user.data.id
            elif hasattr(user, 'id'):
                user_id = user.id
        
        if not user_id:
            return []
        
        # Calculate start time
        start_time = datetime.now() - timedelta(days=days_back)
        
        tweets = []
        pagination_token = None
        
        while len(tweets) < max_results:
            response = client.get_users_tweets(
                id=user_id,
                max_results=min(100, max_results - len(tweets)),
                start_time=start_time,
                tweet_fields=['created_at', 'public_metrics', 'text'],
                pagination_token=pagination_token
            )
            
            # Handle both tweepy and HTTP client responses
            response_data = None
            if hasattr(response, 'data'):
                response_data = response.data
            elif isinstance(response, list):
                response_data = response
            
            if not response_data:
                break
            
            for tweet in response_data:
                # Handle both tweepy and HTTP client tweet objects
                tweet_id = tweet.id if hasattr(tweet, 'id') else tweet.get('id')
                tweet_text = tweet.text if hasattr(tweet, 'text') else tweet.get('text')
                tweet_created = tweet.created_at if hasattr(tweet, 'created_at') else tweet.get('created_at')
                
                # Get metrics
                if hasattr(tweet, 'public_metrics'):
                    metrics = tweet.public_metrics
                    if hasattr(metrics, 'get'):
                        likes = metrics.get("like_count", 0)
                        replies = metrics.get("reply_count", 0)
                        retweets = metrics.get("retweet_count", 0)
                    else:
                        likes = getattr(metrics, 'like_count', 0)
                        replies = getattr(metrics, 'reply_count', 0)
                        retweets = getattr(metrics, 'retweet_count', 0)
                else:
                    metrics = tweet.get('public_metrics', {}) if isinstance(tweet, dict) else {}
                    likes = metrics.get("like_count", 0) if isinstance(metrics, dict) else 0
                    replies = metrics.get("reply_count", 0) if isinstance(metrics, dict) else 0
                    retweets = metrics.get("retweet_count", 0) if isinstance(metrics, dict) else 0
                
                tweets.append({
                    "id": tweet_id,
                    "text": tweet_text,
                    "created_at": tweet_created.isoformat() if hasattr(tweet_created, 'isoformat') else (str(tweet_created) if tweet_created else None),
                    "author": username or user_id,
                    "metrics": {
                        "likes": likes,
                        "replies": replies,
                        "retweets": retweets,
                    }
                })
            
            # Check for more pages
            meta = None
            if hasattr(response, 'meta'):
                meta = response.meta
            elif isinstance(response, dict):
                meta = response.get('meta', {})
            
            if not meta or not meta.get('next_token'):
                break
            pagination_token = meta.get('next_token')
        
        return tweets
    
    except Exception as e:
        error_msg = str(e)
        # If we get 401 and using tweepy, try switching to HTTP client
        # Import the module to access module-level variables
        import services.x_api as x_api_module
        if ("401" in error_msg or "Unauthorized" in error_msg) and not x_api_module.use_http_client:
            print(f"Tweepy authentication failed: {e}")
            print("Switching to HTTP client for twitterapi.io")
            try:
                from services.x_api_http import HTTPAPIClient
                x_api_module.client = HTTPAPIClient(api_key)
                x_api_module.use_http_client = True
                print("Using HTTP client for twitterapi.io")
                # Retry the call with HTTP client
                return get_user_timeline(username, user_id, days_back, max_results)
            except Exception as http_error:
                print(f"HTTP client also failed: {http_error}")
        else:
            print(f"Error fetching user timeline: {e}")
        return []


def get_user_likes(
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    days_back: int = 30,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    Get tweets user has liked
    
    Args:
        username: Twitter username
        user_id: Twitter user ID
        days_back: How many days back to fetch
        max_results: Maximum number of tweets
    
    Returns:
        List of liked tweet dictionaries
    """
    if not client:
        return []
    
    try:
        if username and not user_id:
            user = client.get_user(username=username)
            # Handle both tweepy and HTTP client responses
            if hasattr(user, 'data') and user.data:
                user_id = user.data.id
            elif hasattr(user, 'id'):
                user_id = user.id
        
        if not user_id:
            return []
        
        start_time = datetime.now() - timedelta(days=days_back)
        
        tweets = []
        pagination_token = None
        
        while len(tweets) < max_results:
            # Check if client has get_liked_tweets method (tweepy) or need alternative
            if hasattr(client, 'get_liked_tweets'):
                response = client.get_liked_tweets(
                    id=user_id,
                    max_results=min(100, max_results - len(tweets)),
                    start_time=start_time,
                    tweet_fields=['created_at', 'public_metrics', 'text', 'author_id'],
                    pagination_token=pagination_token
                )
            else:
                # HTTP client might not have this, skip for now
                break
            
            # Handle both tweepy and HTTP client responses
            response_data = None
            if hasattr(response, 'data'):
                response_data = response.data
            elif isinstance(response, list):
                response_data = response
            
            if not response_data:
                break
            
            # Get author usernames
            author_ids = []
            for tweet in response_data:
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
                if author_id:
                    author_ids.append(author_id)
            
            authors = {}
            if author_ids:
                users = client.get_users(ids=author_ids)
                # Handle both tweepy and HTTP client responses
                users_data = None
                if hasattr(users, 'data'):
                    users_data = users.data
                elif isinstance(users, list):
                    users_data = users
                
                if users_data:
                    for user in users_data:
                        user_id_val = user.id if hasattr(user, 'id') else user.get('id')
                        user_username = user.username if hasattr(user, 'username') else user.get('username')
                        if user_id_val and user_username:
                            authors[user_id_val] = user_username
            
            for tweet in response_data:
                # Handle both tweepy and HTTP client tweet objects
                tweet_id = tweet.id if hasattr(tweet, 'id') else tweet.get('id')
                tweet_text = tweet.text if hasattr(tweet, 'text') else tweet.get('text')
                tweet_created = tweet.created_at if hasattr(tweet, 'created_at') else tweet.get('created_at')
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
                
                # Get metrics
                if hasattr(tweet, 'public_metrics'):
                    metrics = tweet.public_metrics
                    if hasattr(metrics, 'get'):
                        likes = metrics.get("like_count", 0)
                        replies = metrics.get("reply_count", 0)
                        retweets = metrics.get("retweet_count", 0)
                    else:
                        likes = getattr(metrics, 'like_count', 0)
                        replies = getattr(metrics, 'reply_count', 0)
                        retweets = getattr(metrics, 'retweet_count', 0)
                else:
                    metrics = tweet.get('public_metrics', {}) if isinstance(tweet, dict) else {}
                    likes = metrics.get("like_count", 0) if isinstance(metrics, dict) else 0
                    replies = metrics.get("reply_count", 0) if isinstance(metrics, dict) else 0
                    retweets = metrics.get("retweet_count", 0) if isinstance(metrics, dict) else 0
                
                tweets.append({
                    "id": tweet_id,
                    "text": tweet_text,
                    "created_at": tweet_created.isoformat() if hasattr(tweet_created, 'isoformat') else (str(tweet_created) if tweet_created else None),
                    "author": authors.get(author_id, author_id) if author_id else "Unknown",
                    "metrics": {
                        "likes": likes,
                        "replies": replies,
                        "retweets": retweets,
                    }
                })
            
            # Check for more pages
            meta = None
            if hasattr(response, 'meta'):
                meta = response.meta
            elif isinstance(response, dict):
                meta = response.get('meta', {})
            
            if not meta or not meta.get('next_token'):
                break
            pagination_token = meta.get('next_token')
        
        return tweets
    
    except Exception as e:
        print(f"Error fetching user likes: {e}")
        return []


def get_user_replies(
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    days_back: int = 30,
    max_results: int = 100
) -> List[Dict[str, Any]]:
    """
    Get user's replies to other tweets
    
    Args:
        username: Twitter username
        user_id: Twitter user ID
        days_back: How many days back
        max_results: Maximum results
    
    Returns:
        List of reply dictionaries
    """
    if not client:
        return []
    
    # Get timeline and filter for replies
    timeline = get_user_timeline(username, user_id, days_back, max_results * 2)
    
    # Filter for replies (tweets that start with @username)
    replies = []
    for tweet in timeline:
        if tweet["text"].startswith("@"):
            replies.append(tweet)
            if len(replies) >= max_results:
                break
    
    return replies


def get_list_members(list_id: str) -> List[Dict[str, Any]]:
    """
    Get members of an X List
    
    Args:
        list_id: X List ID
    
    Returns:
        List of user dictionaries
    """
    if not client:
        return []
    
    try:
        members = []
        pagination_token = None
        
        while True:
            response = client.get_list_members(
                id=list_id,
                max_results=100,
                user_fields=['username', 'name'],
                pagination_token=pagination_token
            )
            
            # Handle both tweepy and HTTP client responses
            response_data = None
            if hasattr(response, 'data'):
                response_data = response.data
            elif isinstance(response, list):
                response_data = response
            
            if not response_data:
                break
            
            for user in response_data:
                user_id_val = user.id if hasattr(user, 'id') else user.get('id')
                user_username = user.username if hasattr(user, 'username') else user.get('username')
                user_name = user.name if hasattr(user, 'name') else user.get('name')
                members.append({
                    "id": user_id_val,
                    "username": user_username,
                    "name": user_name
                })
            
            # Check for more pages
            meta = None
            if hasattr(response, 'meta'):
                meta = response.meta
            elif isinstance(response, dict):
                meta = response.get('meta', {})
            
            if not meta or not meta.get('next_token'):
                break
            pagination_token = meta.get('next_token')
        
        return members
    
    except Exception as e:
        print(f"Error fetching list members: {e}")
        return []


def get_list_timeline(
    list_id: str,
    days_back: int = 30,
    max_results: int = 200
) -> List[Dict[str, Any]]:
    """
    Get timeline of posts from all members of a list
    
    Args:
        list_id: X List ID
        days_back: How many days back
        max_results: Maximum results
    
    Returns:
        List of tweet dictionaries
    """
    if not client:
        return []
    
    try:
        start_time = datetime.now() - timedelta(days=days_back)
        
        tweets = []
        pagination_token = None
        
        while len(tweets) < max_results:
            response = client.get_list_tweets(
                id=list_id,
                max_results=min(100, max_results - len(tweets)),
                start_time=start_time,
                tweet_fields=['created_at', 'public_metrics', 'text', 'author_id'],
                pagination_token=pagination_token
            )
            
            # Handle both tweepy and HTTP client responses
            response_data = None
            if hasattr(response, 'data'):
                response_data = response.data
            elif isinstance(response, list):
                response_data = response
            
            if not response_data:
                break
            
            # Get author usernames
            author_ids = []
            for tweet in response_data:
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
                if author_id:
                    author_ids.append(author_id)
            
            authors = {}
            if author_ids:
                users = client.get_users(ids=author_ids)
                # Handle both tweepy and HTTP client responses
                users_data = None
                if hasattr(users, 'data'):
                    users_data = users.data
                elif isinstance(users, list):
                    users_data = users
                
                if users_data:
                    for user in users_data:
                        user_id_val = user.id if hasattr(user, 'id') else user.get('id')
                        user_username = user.username if hasattr(user, 'username') else user.get('username')
                        if user_id_val and user_username:
                            authors[user_id_val] = user_username
            
            for tweet in response_data:
                # Handle both tweepy and HTTP client tweet objects
                tweet_id = tweet.id if hasattr(tweet, 'id') else tweet.get('id')
                tweet_text = tweet.text if hasattr(tweet, 'text') else tweet.get('text')
                tweet_created = tweet.created_at if hasattr(tweet, 'created_at') else tweet.get('created_at')
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
                
                # Get metrics
                if hasattr(tweet, 'public_metrics'):
                    metrics = tweet.public_metrics
                    if hasattr(metrics, 'get'):
                        likes = metrics.get("like_count", 0)
                        replies = metrics.get("reply_count", 0)
                        retweets = metrics.get("retweet_count", 0)
                    else:
                        likes = getattr(metrics, 'like_count', 0)
                        replies = getattr(metrics, 'reply_count', 0)
                        retweets = getattr(metrics, 'retweet_count', 0)
                else:
                    metrics = tweet.get('public_metrics', {}) if isinstance(tweet, dict) else {}
                    likes = metrics.get("like_count", 0) if isinstance(metrics, dict) else 0
                    replies = metrics.get("reply_count", 0) if isinstance(metrics, dict) else 0
                    retweets = metrics.get("retweet_count", 0) if isinstance(metrics, dict) else 0
                
                tweets.append({
                    "id": tweet_id,
                    "text": tweet_text,
                    "created_at": tweet_created.isoformat() if hasattr(tweet_created, 'isoformat') else (str(tweet_created) if tweet_created else None),
                    "author": authors.get(author_id, author_id) if author_id else "Unknown",
                    "author_id": author_id,
                    "metrics": {
                        "likes": likes,
                        "replies": replies,
                        "retweets": retweets,
                    }
                })
            
            # Check for more pages
            meta = None
            if hasattr(response, 'meta'):
                meta = response.meta
            elif isinstance(response, dict):
                meta = response.get('meta', {})
            
            if not meta or not meta.get('next_token'):
                break
            pagination_token = meta.get('next_token')
        
        return tweets
    
    except Exception as e:
        print(f"Error fetching list timeline: {e}")
        return []


def get_user_lists(username: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get lists created by user
    
    Args:
        username: Twitter username
        user_id: Twitter user ID
    
    Returns:
        List of list dictionaries
    """
    if not client:
        return []
    
    try:
        if username and not user_id:
            user = client.get_user(username=username)
            # Handle both tweepy and HTTP client responses
            if hasattr(user, 'data') and user.data:
                user_id = user.data.id
            elif hasattr(user, 'id'):
                user_id = user.id
        
        if not user_id:
            return []
        
        lists = []
        pagination_token = None
        
        while True:
            # Check if client has get_owned_lists or get_user_lists method
            if hasattr(client, 'get_owned_lists'):
                response = client.get_owned_lists(
                    id=user_id,
                    max_results=100,
                    list_fields=['name', 'description'],
                    pagination_token=pagination_token
                )
            elif hasattr(client, 'get_user_lists'):
                response = client.get_user_lists(
                    user_id=user_id,
                    max_results=100
                )
            else:
                break
            
            # Handle both tweepy and HTTP client responses
            response_data = None
            if hasattr(response, 'data'):
                response_data = response.data
            elif isinstance(response, list):
                response_data = response
            
            if not response_data:
                break
            
            for list_obj in response_data:
                list_id = list_obj.id if hasattr(list_obj, 'id') else list_obj.get('id')
                list_name = list_obj.name if hasattr(list_obj, 'name') else list_obj.get('name')
                list_desc = list_obj.description if hasattr(list_obj, 'description') else list_obj.get('description', '')
                lists.append({
                    "id": list_id,
                    "name": list_name,
                    "description": list_desc
                })
            
            # Check for more pages
            meta = None
            if hasattr(response, 'meta'):
                meta = response.meta
            elif isinstance(response, dict):
                meta = response.get('meta', {})
            
            if not meta or not meta.get('next_token'):
                break
            pagination_token = meta.get('next_token')
        
        return lists
    
    except Exception as e:
        print(f"Error fetching user lists: {e}")
        return []


def get_current_user() -> Optional[Dict[str, Any]]:
    """Get current authenticated user info"""
    if not client:
        return None
    
    try:
        # Try to get authenticated user
        user = client.get_me(user_fields=['username', 'name'])
        if user.data:
            return {
                "id": user.data.id,
                "username": user.data.username,
                "name": user.data.name
            }
        return None
    except Exception as e:
        # If get_me fails (common with bearer token only), check if client is initialized
        # This means API is connected but may not have user context
        if client:
            return {
                "connected": True,
                "note": "API connected but user context not available. Use username parameter for operations."
            }
        print(f"Error fetching current user: {e}")
        return None

