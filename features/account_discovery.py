"""Account Discovery Feature - Find relevant accounts based on keywords and criteria"""
from typing import List, Dict, Any, Optional
from services.x_api import client
import config


def search_accounts_by_keywords(
    keywords: List[str],
    min_followers: int = 1000,
    min_engagement_rate: float = 0.01,
    max_results: int = 50
) -> List[Dict[str, Any]]:
    """
    Search for accounts based on keywords and criteria
    
    Args:
        keywords: List of keywords/topics
        min_followers: Minimum follower count
        min_engagement_rate: Minimum engagement rate (likes+replies)/followers
        max_results: Maximum number of accounts to return
    
    Returns:
        List of account dictionaries with relevance scores
    """
    if not client:
        return []
    
    accounts = []
    
    try:
        # Search for accounts using keywords
        for keyword in keywords:
            try:
                # Search for tweets containing the keyword
                tweets = client.search_recent_tweets(
                    query=f"{keyword} -is:retweet lang:en",
                    max_results=100,
                    tweet_fields=['author_id', 'public_metrics', 'created_at'],
                    user_fields=['username', 'name', 'description', 'public_metrics', 'verified']
                )
            except Exception as api_error:
                # Handle 401 Unauthorized and other API errors gracefully
                error_msg = str(api_error)
                if "401" in error_msg or "Unauthorized" in error_msg:
                    print(f"X API authentication error for keyword '{keyword}': {error_msg}")
                    print("Please check your X_API_KEY in environment variables")
                else:
                    print(f"Error searching for keyword '{keyword}': {error_msg}")
                continue
            
            if not tweets or not tweets.data:
                continue
            
            # Get unique authors
            author_ids = set()
            for tweet in tweets.data:
                if tweet.author_id:
                    author_ids.add(tweet.author_id)
            
            # Fetch user details for authors
            if author_ids:
                user_ids = list(author_ids)[:20]  # Limit to avoid rate limits
                users = client.get_users(ids=user_ids, user_fields=[
                    'username', 'name', 'description', 'public_metrics', 'verified', 'profile_image_url'
                ])
                
                if users.data:
                    for user in users.data:
                        metrics = user.public_metrics
                        # Handle both dict and object metrics
                        if hasattr(metrics, 'followers_count'):
                            followers = getattr(metrics, 'followers_count', 0)
                            following_count = getattr(metrics, 'following_count', 0)
                            tweet_count = getattr(metrics, 'tweet_count', 0)
                        elif isinstance(metrics, dict):
                            followers = metrics.get('followers_count', 0)
                            following_count = metrics.get('following_count', 0)
                            tweet_count = metrics.get('tweet_count', 0)
                        else:
                            followers = 0
                            following_count = 0
                            tweet_count = 0
                        
                        # Filter by criteria
                        if followers < min_followers:
                            continue
                        
                        # Calculate engagement rate (simplified)
                        # We'd need more data for accurate calculation
                        engagement_rate = 0.02  # Placeholder - would calculate from recent posts
                        
                        if engagement_rate < min_engagement_rate:
                            continue
                        
                        # Check if account already in results
                        if any(acc.get('id') == user.id for acc in accounts):
                            continue
                        
                        # Calculate relevance score based on keyword match
                        relevance_score = _calculate_relevance(user, keyword, keywords)
                        
                        accounts.append({
                            'id': user.id,
                            'username': user.username,
                            'name': user.name,
                            'description': user.description or '',
                            'followers': followers,
                            'following': following_count,
                            'tweets': tweet_count,
                            'verified': user.verified or False,
                            'profile_image_url': getattr(user, 'profile_image_url', None),
                            'relevance_score': relevance_score,
                            'matched_keywords': [k for k in keywords if k.lower() in (user.description or '').lower()],
                            'engagement_rate': engagement_rate
                        })
        
        # Sort by relevance score
        accounts.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Remove duplicates and limit results
        seen = set()
        unique_accounts = []
        for acc in accounts:
            if acc['id'] not in seen:
                seen.add(acc['id'])
                unique_accounts.append(acc)
                if len(unique_accounts) >= max_results:
                    break
        
        return unique_accounts
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            print(f"X API authentication error: {error_msg}")
            print("Please check your X_API_KEY in environment variables")
        else:
            print(f"Error searching accounts: {error_msg}")
        # Return empty list instead of crashing - allow onboarding to proceed
        return []


def _calculate_relevance(user: Any, keyword: str, all_keywords: List[str]) -> float:
    """Calculate relevance score for an account based on keywords"""
    score = 0.0
    description = (user.description or '').lower()
    name = (user.name or '').lower()
    keyword_lower = keyword.lower()
    
    # Check if keyword appears in description
    if keyword_lower in description:
        score += 0.4
    
    # Check if keyword appears in name
    if keyword_lower in name:
        score += 0.3
    
    # Check for related terms (simple keyword matching)
    # In a real implementation, we'd use NLP/semantic search
    related_terms = {
        'ai': ['artificial intelligence', 'machine learning', 'ml', 'deep learning'],
        'startup': ['entrepreneur', 'founder', 'business', 'company'],
        'saas': ['software', 'product', 'tech', 'platform'],
        'productivity': ['efficiency', 'workflow', 'tools', 'optimization'],
        'marketing': ['growth', 'advertising', 'brand', 'campaign'],
        'design': ['ui', 'ux', 'visual', 'creative', 'aesthetic']
    }
    
    for term, related in related_terms.items():
        if term in keyword_lower:
            for rel_term in related:
                if rel_term in description:
                    score += 0.1
                    break
    
    # Boost score for verified accounts
    if user.verified:
        score += 0.1
    
    # Normalize to 0-1 range
    return min(1.0, score)


def discover_accounts_for_user(
    keywords: List[str],
    keyword_relevance: Dict[str, float],
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Discover accounts for a user based on their keyword preferences
    
    Args:
        keywords: List of keywords
        keyword_relevance: Dict mapping keywords to relevance scores (0.1-1.0)
        user_id: User ID for personalization
    
    Returns:
        List of recommended accounts sorted by relevance
    """
    # Search for accounts
    accounts = search_accounts_by_keywords(keywords, max_results=100)
    
    # Weight accounts by user's relevance preferences
    for account in accounts:
        matched_keywords = account.get('matched_keywords', [])
        weighted_score = 0.0
        
        for keyword in matched_keywords:
            relevance = keyword_relevance.get(keyword, 0.5)
            weighted_score += relevance * 0.3
        
        # Combine with base relevance score
        account['weighted_relevance'] = (account['relevance_score'] * 0.7) + (weighted_score * 0.3)
    
    # Sort by weighted relevance
    accounts.sort(key=lambda x: x.get('weighted_relevance', 0), reverse=True)
    
    return accounts[:30]  # Return top 30


def get_posts_for_onboarding(
    keywords: List[str],
    keyword_relevance: Dict[str, float],
    post_type: str = 'like',  # 'like', 'reply', 'engage'
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Get posts for onboarding (likes, replies, engagement)
    
    Args:
        keywords: List of keywords
        keyword_relevance: Dict mapping keywords to relevance scores
        post_type: Type of posts ('like', 'reply', 'engage')
        max_results: Maximum number of posts
    
    Returns:
        List of post dictionaries
    """
    if not client:
        return []
    
    posts = []
    
    try:
        # Build search query from keywords
        query_parts = []
        for keyword in keywords[:3]:  # Use top 3 keywords
            query_parts.append(keyword)
        
        # Filter out retweets AND replies - only show original posts
        query = " OR ".join(query_parts) + " -is:retweet -is:reply lang:en"
        
        # Search for recent tweets
        try:
            tweets = client.search_recent_tweets(
                query=query,
                max_results=100,
                tweet_fields=['author_id', 'public_metrics', 'created_at', 'text', 'conversation_id'],
                user_fields=['username', 'name']
            )
        except Exception as api_error:
            error_msg = str(api_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"X API authentication error getting posts: {error_msg}")
                print("Please check your X_API_KEY in environment variables")
            else:
                print(f"Error getting posts for onboarding: {error_msg}")
            return []
        
        if not tweets or not tweets.data:
            return []
        
        # First, collect all author IDs to fetch usernames in bulk
        author_ids_to_fetch = []
        tweet_list = list(tweets.data)
        for tweet in tweet_list:
            author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
            if author_id and author_id not in author_ids_to_fetch:
                author_ids_to_fetch.append(author_id)
        
        # Fetch usernames in bulk if we have author IDs
        author_usernames = {}
        if author_ids_to_fetch:
            try:
                users_response = client.get_users(ids=author_ids_to_fetch)
                users_data = None
                if hasattr(users_response, 'data'):
                    users_data = users_response.data
                elif isinstance(users_response, list):
                    users_data = users_response
                
                if users_data:
                    for user in users_data:
                        user_id = user.id if hasattr(user, 'id') else (user.get('id') if isinstance(user, dict) else None)
                        username = user.username if hasattr(user, 'username') else (user.get('username') if isinstance(user, dict) else None)
                        if user_id and username:
                            author_usernames[str(user_id)] = username
            except Exception as e:
                print(f"Error fetching author usernames: {e}")
        
        # Score and filter posts
        for tweet in tweet_list:
            text = tweet.text
            metrics = tweet.public_metrics
            
            # Handle both dict and object metrics
            if hasattr(metrics, 'like_count'):
                like_count = getattr(metrics, 'like_count', 0)
                reply_count = getattr(metrics, 'reply_count', 0)
                retweet_count = getattr(metrics, 'retweet_count', 0)
            elif isinstance(metrics, dict):
                like_count = metrics.get('like_count', 0)
                reply_count = metrics.get('reply_count', 0)
                retweet_count = metrics.get('retweet_count', 0)
            else:
                like_count = 0
                reply_count = 0
                retweet_count = 0
            
            # Calculate relevance score
            relevance_score = 0.0
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    relevance = keyword_relevance.get(keyword, 0.5)
                    relevance_score += relevance
            
            # Normalize score
            relevance_score = min(1.0, relevance_score / len(keywords))
            
            # Calculate total engagement
            total_engagement = like_count + reply_count + retweet_count
            
            # Prioritize posts with significant traction - minimum engagement thresholds
            min_engagement = {
                'like': 50,      # Posts for liking should have at least 50 likes
                'engage': 100,   # Posts for engagement should have at least 100 total engagement
                'default': 30    # Default minimum for other types
            }.get(post_type, 30)
            
            if total_engagement < min_engagement:
                continue
            
            # Get post URL for embedding
            tweet_id = tweet.id if hasattr(tweet, 'id') else (tweet.get('id') if isinstance(tweet, dict) else None)
            author_username = getattr(tweet, 'author_username', 'unknown') or (tweet.get('author_username') if isinstance(tweet, dict) else 'unknown')
            
            post_url = None
            if tweet_id and author_username:
                post_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
            
            # Calculate popularity score (weighted engagement)
            # Likes are most important, then replies, then retweets
            popularity_score = (like_count * 1.0) + (reply_count * 1.5) + (retweet_count * 0.8)
            
            posts.append({
                'id': tweet_id or str(tweet.id) if hasattr(tweet, 'id') else '',
                'text': text,
                'author_id': tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None),
                'author_username': author_username,
                'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                'likes': like_count,
                'replies': reply_count,
                'retweets': retweet_count,
                'relevance_score': relevance_score,
                'popularity_score': popularity_score,
                'total_engagement': total_engagement,
                'type': post_type,
                'url': post_url
            })
        
        # Sort by combined score: relevance (40%) + popularity (60%)
        # This ensures we get posts that are both relevant AND have traction
        posts.sort(key=lambda x: (
            x['relevance_score'] * 0.4 + 
            min(x['popularity_score'] / 1000, 1.0) * 0.6  # Normalize popularity to 0-1
        ), reverse=True)
        
        return posts[:max_results]
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            print(f"X API authentication error: {error_msg}")
            print("Please check your X_API_KEY in environment variables")
        else:
            print(f"Error getting posts for onboarding: {error_msg}")
        # Return empty list instead of crashing - allow onboarding to proceed
        return []


def get_account_feed(account_id: str, max_posts: int = 20) -> List[Dict[str, Any]]:
    """
    Get full profile feed for an account
    
    Args:
        account_id: Account/user ID
        max_posts: Maximum number of posts to fetch
    
    Returns:
        List of post dictionaries
    """
    if not client:
        return []
    
    try:
        # Get user timeline
        try:
            tweets = client.get_users_tweets(
                id=account_id,
                max_results=min(max_posts, 100),
                tweet_fields=['author_id', 'public_metrics', 'created_at', 'text', 'conversation_id'],
                user_fields=['username', 'name']
            )
        except Exception as api_error:
            error_msg = str(api_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"X API authentication error getting account feed: {error_msg}")
                print("Please check your X_API_KEY in environment variables")
            else:
                print(f"Error getting account feed: {error_msg}")
            return []
        
        if not tweets or not tweets.data:
            return []
        
        posts = []
        for tweet in tweets.data:
            metrics = tweet.public_metrics
            # Handle both dict and object metrics
            if hasattr(metrics, 'like_count'):
                like_count = getattr(metrics, 'like_count', 0)
                reply_count = getattr(metrics, 'reply_count', 0)
                retweet_count = getattr(metrics, 'retweet_count', 0)
                quote_count = getattr(metrics, 'quote_count', 0)
            elif isinstance(metrics, dict):
                like_count = metrics.get('like_count', 0)
                reply_count = metrics.get('reply_count', 0)
                retweet_count = metrics.get('retweet_count', 0)
                quote_count = metrics.get('quote_count', 0)
            else:
                like_count = 0
                reply_count = 0
                retweet_count = 0
                quote_count = 0
            
            posts.append({
                'id': tweet.id,
                'text': tweet.text,
                'author_id': tweet.author_id,
                'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                'likes': like_count,
                'replies': reply_count,
                'retweets': retweet_count,
                'quotes': quote_count
            })
        
        return posts
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            print(f"X API authentication error: {error_msg}")
            print("Please check your X_API_KEY in environment variables")
        else:
            print(f"Error getting account feed: {error_msg}")
        # Return empty list instead of crashing - allow onboarding to proceed
        return []


def get_account_details(account_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed account information
    
    Args:
        account_id: Account/user ID
    
    Returns:
        Account details dictionary
    """
    if not client:
        return None
    
    try:
        try:
            user = client.get_user(
                id=account_id,
                user_fields=['username', 'name', 'description', 'public_metrics', 'verified', 'profile_image_url', 'created_at']
            )
        except Exception as api_error:
            error_msg = str(api_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"X API authentication error getting account details: {error_msg}")
                print("Please check your X_API_KEY in environment variables")
            else:
                print(f"Error getting account details: {error_msg}")
            return None
        
        if not user or not user.data:
            return None
        
        metrics = user.data.public_metrics
        # Handle both dict and object metrics
        if hasattr(metrics, 'followers_count'):
            followers = getattr(metrics, 'followers_count', 0)
            following = getattr(metrics, 'following_count', 0)
            tweets = getattr(metrics, 'tweet_count', 0)
        elif isinstance(metrics, dict):
            followers = metrics.get('followers_count', 0)
            following = metrics.get('following_count', 0)
            tweets = metrics.get('tweet_count', 0)
        else:
            followers = 0
            following = 0
            tweets = 0
        
        return {
            'id': user.data.id,
            'username': user.data.username,
            'name': user.data.name,
            'description': user.data.description or '',
            'followers': followers,
            'following': following,
            'tweets': tweets,
            'verified': user.data.verified or False,
            'profile_image_url': getattr(user.data, 'profile_image_url', None),
            'created_at': str(user.data.created_at) if hasattr(user.data, 'created_at') else None
        }
        
    except Exception as e:
        print(f"Error getting account details: {e}")
        return None

