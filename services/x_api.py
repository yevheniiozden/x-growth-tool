"""X/Twitter API Service - Wrapper for Twitter API v2"""
import tweepy
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import config

# Initialize Twitter API client
client = None
# Try Bearer Token first (preferred for read-only operations)
bearer_token = config.X_BEARER_TOKEN or config.X_API_KEY
if bearer_token:
    try:
        # Use Bearer Token if available, otherwise try API Key as Bearer Token
        # This works for third-party services like twitterapi.io
        client = tweepy.Client(
            bearer_token=bearer_token,
            wait_on_rate_limit=True
        )
    except Exception as e:
        print(f"Warning: Could not initialize Twitter client with Bearer Token: {e}")
        # Fallback: try with API Key + Secret if available
        if config.X_API_KEY and config.X_API_SECRET:
            try:
                client = tweepy.Client(
                    consumer_key=config.X_API_KEY,
                    consumer_secret=config.X_API_SECRET,
                    wait_on_rate_limit=True
                )
            except Exception as e2:
                print(f"Warning: Could not initialize Twitter client: {e2}")


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
            if user.data:
                user_id = user.data.id
        
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
            
            if not response.data:
                break
            
            for tweet in response.data:
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author": username or user_id,
                    "metrics": {
                        "likes": tweet.public_metrics.get("like_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "replies": tweet.public_metrics.get("reply_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "retweets": tweet.public_metrics.get("retweet_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                    }
                })
            
            # Check for more pages
            if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                break
            pagination_token = response.meta['next_token']
        
        return tweets
    
    except Exception as e:
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
            if user.data:
                user_id = user.data.id
        
        if not user_id:
            return []
        
        start_time = datetime.now() - timedelta(days=days_back)
        
        tweets = []
        pagination_token = None
        
        while len(tweets) < max_results:
            response = client.get_liked_tweets(
                id=user_id,
                max_results=min(100, max_results - len(tweets)),
                start_time=start_time,
                tweet_fields=['created_at', 'public_metrics', 'text', 'author_id'],
                pagination_token=pagination_token
            )
            
            if not response.data:
                break
            
            # Get author usernames
            author_ids = [tweet.author_id for tweet in response.data if hasattr(tweet, 'author_id')]
            authors = {}
            if author_ids:
                users = client.get_users(ids=author_ids)
                if users.data:
                    for user in users.data:
                        authors[user.id] = user.username
            
            for tweet in response.data:
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else None
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author": authors.get(author_id, author_id) if author_id else "Unknown",
                    "metrics": {
                        "likes": tweet.public_metrics.get("like_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "replies": tweet.public_metrics.get("reply_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "retweets": tweet.public_metrics.get("retweet_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                    }
                })
            
            if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                break
            pagination_token = response.meta['next_token']
        
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
            
            if not response.data:
                break
            
            for user in response.data:
                members.append({
                    "id": user.id,
                    "username": user.username,
                    "name": user.name
                })
            
            if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                break
            pagination_token = response.meta['next_token']
        
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
            
            if not response.data:
                break
            
            # Get author usernames
            author_ids = [tweet.author_id for tweet in response.data if hasattr(tweet, 'author_id')]
            authors = {}
            if author_ids:
                users = client.get_users(ids=author_ids)
                if users.data:
                    for user in users.data:
                        authors[user.id] = user.username
            
            for tweet in response.data:
                author_id = tweet.author_id if hasattr(tweet, 'author_id') else None
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "author": authors.get(author_id, author_id) if author_id else "Unknown",
                    "author_id": author_id,
                    "metrics": {
                        "likes": tweet.public_metrics.get("like_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "replies": tweet.public_metrics.get("reply_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                        "retweets": tweet.public_metrics.get("retweet_count", 0) if hasattr(tweet, 'public_metrics') else 0,
                    }
                })
            
            if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                break
            pagination_token = response.meta['next_token']
        
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
            if user.data:
                user_id = user.data.id
        
        if not user_id:
            return []
        
        lists = []
        pagination_token = None
        
        while True:
            response = client.get_owned_lists(
                id=user_id,
                max_results=100,
                list_fields=['name', 'description'],
                pagination_token=pagination_token
            )
            
            if not response.data:
                break
            
            for list_obj in response.data:
                lists.append({
                    "id": list_obj.id,
                    "name": list_obj.name,
                    "description": list_obj.description if hasattr(list_obj, 'description') else ""
                })
            
            if not hasattr(response, 'meta') or not response.meta.get('next_token'):
                break
            pagination_token = response.meta['next_token']
        
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

