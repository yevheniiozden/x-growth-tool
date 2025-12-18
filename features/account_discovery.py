"""Account Discovery Feature - Find relevant accounts based on keywords and criteria"""
from typing import List, Dict, Any, Optional
from services.x_api import client
from services.ai_service import client as ai_client
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
            # Search for tweets containing the keyword
            tweets = client.search_recent_tweets(
                query=f"{keyword} -is:retweet lang:en",
                max_results=100,
                tweet_fields=['author_id', 'public_metrics', 'created_at'],
                user_fields=['username', 'name', 'description', 'public_metrics', 'verified']
            )
            
            if not tweets.data:
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
                        followers = metrics.get('followers_count', 0)
                        
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
                            'following': metrics.get('following_count', 0),
                            'tweets': metrics.get('tweet_count', 0),
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
        print(f"Error searching accounts: {e}")
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
        
        query = " OR ".join(query_parts) + " -is:retweet lang:en"
        
        # Search for recent tweets
        tweets = client.search_recent_tweets(
            query=query,
            max_results=100,
            tweet_fields=['author_id', 'public_metrics', 'created_at', 'text', 'conversation_id'],
            user_fields=['username', 'name']
        )
        
        if not tweets.data:
            return []
        
        # Score and filter posts
        for tweet in tweets.data:
            text = tweet.text
            metrics = tweet.public_metrics
            
            # Calculate relevance score
            relevance_score = 0.0
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    relevance = keyword_relevance.get(keyword, 0.5)
                    relevance_score += relevance
            
            # Normalize score
            relevance_score = min(1.0, relevance_score / len(keywords))
            
            # Filter by engagement (for engagement-type posts)
            if post_type == 'engage':
                total_engagement = (
                    metrics.get('like_count', 0) +
                    metrics.get('reply_count', 0) +
                    metrics.get('retweet_count', 0)
                )
                if total_engagement < 10:  # Minimum engagement threshold
                    continue
            
            posts.append({
                'id': tweet.id,
                'text': text,
                'author_id': tweet.author_id,
                'author_username': getattr(tweet, 'author_username', 'unknown'),
                'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                'likes': metrics.get('like_count', 0),
                'replies': metrics.get('reply_count', 0),
                'retweets': metrics.get('retweet_count', 0),
                'relevance_score': relevance_score,
                'type': post_type
            })
        
        # Sort by relevance and engagement
        posts.sort(key=lambda x: (
            x['relevance_score'] * 0.6 + 
            (x['likes'] + x['replies']) / 1000 * 0.4
        ), reverse=True)
        
        return posts[:max_results]
        
    except Exception as e:
        print(f"Error getting posts for onboarding: {e}")
        return []

