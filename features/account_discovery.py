"""Account Discovery Feature - Find relevant accounts based on keywords and criteria"""
from typing import List, Dict, Any, Optional
from services.x_api import client
from services.ai_service import expand_keywords_semantically, generate_search_queries, analyze_post_relevance
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
        # OPTIMIZATION: Combine all keywords into single OR query instead of multiple searches
        # This reduces API calls from N (one per keyword) to 1
        if not keywords:
            return accounts
        
        # Build combined query: (keyword1 OR keyword2 OR keyword3) -is:retweet lang:en
        keyword_query = " OR ".join(keywords[:5])  # Limit to 5 keywords to avoid query length issues
        combined_query = f"({keyword_query}) -is:retweet lang:en"
        
        try:
            # Single search call for all keywords
            tweets = client.search_recent_tweets(
                query=combined_query,
                max_results=min(100, max_results * 3),  # Get more tweets to filter from
                tweet_fields=['author_id', 'public_metrics', 'created_at'],
                user_fields=['username', 'name', 'description', 'public_metrics', 'verified']
            )
        except Exception as api_error:
            # Handle 401 Unauthorized and other API errors gracefully
            error_msg = str(api_error)
            if "401" in error_msg or "Unauthorized" in error_msg:
                print(f"X API authentication error for combined keyword search: {error_msg}")
                print("Please check your X_API_KEY in environment variables")
            else:
                print(f"Error searching for combined keywords: {error_msg}")
            return accounts
        
        if not tweets or not tweets.data:
            return accounts
        
        # Get unique authors from all tweets
        author_ids = set()
        author_keyword_map = {}  # Track which keywords matched for each author
        
        for tweet in tweets.data:
            if tweet.author_id:
                author_id = str(tweet.author_id)
                author_ids.add(author_id)
                
                # Track which keywords this tweet matches
                tweet_text = (tweet.text or '').lower()
                for keyword in keywords:
                    if keyword.lower() in tweet_text:
                        if author_id not in author_keyword_map:
                            author_keyword_map[author_id] = []
                        if keyword not in author_keyword_map[author_id]:
                            author_keyword_map[author_id].append(keyword)
        
        # Fetch user details for authors in batches
        if author_ids:
            user_ids_list = list(author_ids)
            # Process in batches of 100 to avoid API limits
            for i in range(0, len(user_ids_list), 100):
                batch_ids = user_ids_list[i:i+100]
                try:
                    users = client.get_users(ids=batch_ids, user_fields=[
                        'username', 'name', 'description', 'public_metrics', 'verified', 'profile_image_url'
                    ])
                    
                    users_data = None
                    if hasattr(users, 'data'):
                        users_data = users.data
                    elif isinstance(users, list):
                        users_data = users
                    elif hasattr(users, 'users'):
                        users_data = users.users
                    
                    if users_data:
                        for user in users_data:
                            user_id = str(user.id if hasattr(user, 'id') else (user.get('id') if isinstance(user, dict) else ''))
                            if not user_id:
                                continue
                            
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
                            engagement_rate = 0.02  # Placeholder
                            
                            if engagement_rate < min_engagement_rate:
                                continue
                            
                            # Check if account already in results
                            if any(acc.get('id') == user_id for acc in accounts):
                                continue
                            
                            # Calculate relevance score based on matched keywords
                            matched_keywords = author_keyword_map.get(user_id, keywords[:1])  # Fallback to first keyword
                            relevance_score = 0.0
                            for keyword in matched_keywords:
                                score = _calculate_relevance(user, keyword, keywords)
                                relevance_score = max(relevance_score, score)  # Use highest score
                            
                            accounts.append({
                                'id': user_id,
                                'username': user.username if hasattr(user, 'username') else (user.get('username') if isinstance(user, dict) else ''),
                                'name': (user.name if hasattr(user, 'name') else (user.get('name') if isinstance(user, dict) else '')) or (user.username if hasattr(user, 'username') else ''),
                                'description': user.description if hasattr(user, 'description') else (user.get('description') if isinstance(user, dict) else ''),
                                'followers': followers,
                                'following': following_count,
                                'tweets': tweet_count,
                                'verified': user.verified if hasattr(user, 'verified') else (user.get('verified') or user.get('isBlueVerified', False) if isinstance(user, dict) else False),
                                'profile_image_url': user.profile_image_url if hasattr(user, 'profile_image_url') else (user.get('profile_image_url') or user.get('profilePicture', '') if isinstance(user, dict) else ''),
                                'relevance_score': relevance_score,
                                'matched_keywords': matched_keywords
                            })
                except Exception as e:
                    print(f"Error fetching user batch: {e}")
                    continue
        
        # Sort by relevance score
        accounts.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        # Remove duplicates and limit results
        seen = set()
        unique_accounts = []
        for acc in accounts:
            acc_id = acc.get('id')
            if acc_id and acc_id not in seen:
                seen.add(acc_id)
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
    all_tweets = []  # Collect tweets from all queries
    
    try:
        # Step 1: Expand keywords semantically and generate search queries
        print(f"Expanding {len(keywords)} keywords semantically...")
        expansion = expand_keywords_semantically(keywords)
        context = expansion.get("context", "")
        
        print(f"Generating AI-optimized search queries...")
        search_queries = generate_search_queries(keywords, context)
        print(f"Generated {len(search_queries)} search queries")
        
        # Step 2: Execute multiple search queries and combine results
        for i, query in enumerate(search_queries):
            try:
                print(f"Executing search query {i+1}/{len(search_queries)}: {query[:80]}...")
                tweets = client.search_recent_tweets(
                    query=query,
                    max_results=60,  # Increased to get more results per query
                    tweet_fields=['author_id', 'public_metrics', 'created_at', 'text', 'conversation_id'],
                    user_fields=['username', 'name']
                )
                
                if tweets and tweets.data:
                    tweet_list = list(tweets.data)
                    print(f"Query {i+1} returned {len(tweet_list)} tweets")
                    all_tweets.extend(tweet_list)
                else:
                    print(f"Query {i+1} returned no tweets (tweets={tweets}, data={tweets.data if tweets else None})")
            except Exception as api_error:
                error_msg = str(api_error)
                if "401" in error_msg or "Unauthorized" in error_msg:
                    print(f"X API authentication error for query {i+1}: {error_msg}")
                    print("Please check your X_API_KEY in environment variables")
                else:
                    print(f"Error executing query {i+1}: {error_msg}")
                    import traceback
                    traceback.print_exc()
                continue
        
        # Deduplicate tweets by ID
        seen_tweet_ids = set()
        tweet_list = []
        for tweet in all_tweets:
            tweet_id = tweet.id if hasattr(tweet, 'id') else (tweet.get('id') if isinstance(tweet, dict) else None)
            if tweet_id and str(tweet_id) not in seen_tweet_ids:
                seen_tweet_ids.add(str(tweet_id))
                tweet_list.append(tweet)
        
        print(f"Total unique tweets after combining queries: {len(tweet_list)}")
        
        if not tweet_list:
            print("No tweets found from any search query")
            return []
        
        # First, collect all author IDs to fetch usernames in bulk
        author_ids_to_fetch = []
        for tweet in tweet_list:
            author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
            if author_id and str(author_id) not in author_ids_to_fetch:
                author_ids_to_fetch.append(str(author_id))
        
        print(f"Found {len(author_ids_to_fetch)} unique author IDs to fetch")
        
        # Fetch usernames in bulk if we have author IDs - CRITICAL for embedding
        author_usernames = {}
        author_data = {}  # Store full author data for later use
        if author_ids_to_fetch:
            try:
                # Batch fetch users (limit to 100 per batch to avoid API limits)
                for i in range(0, len(author_ids_to_fetch), 100):
                    batch_ids = author_ids_to_fetch[i:i+100]
                    users_response = client.get_users(ids=batch_ids)
                    users_data = None
                    if hasattr(users_response, 'data'):
                        users_data = users_response.data
                    elif isinstance(users_response, list):
                        users_data = users_response
                    elif hasattr(users_response, 'users'):
                        users_data = users_response.users
                    
                    if users_data:
                        for user in users_data:
                            user_id = user.id if hasattr(user, 'id') else (user.get('id') if isinstance(user, dict) else None)
                            username = user.username if hasattr(user, 'username') else (user.get('username') if isinstance(user, dict) else None)
                            if user_id and username:
                                author_usernames[str(user_id)] = username
                                author_data[str(user_id)] = {
                                    'username': username,
                                    'name': user.name if hasattr(user, 'name') else (user.get('name') if isinstance(user, dict) else username),
                                    'profile_image': user.profile_image_url if hasattr(user, 'profile_image_url') else (user.get('profile_image_url') or user.get('profilePicture', '')),
                                    'verified': user.verified if hasattr(user, 'verified') else (user.get('verified') or user.get('isBlueVerified', False))
                                }
                print(f"Fetched usernames for {len(author_usernames)} authors")
            except Exception as e:
                print(f"Error fetching author usernames: {e}")
                import traceback
                traceback.print_exc()
        
        # Score and filter posts
        filtered_by_engagement = 0
        filtered_by_username = 0
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
            
            # Calculate relevance score using AI semantic analysis
            # First try AI-based semantic relevance
            try:
                semantic_relevance = analyze_post_relevance(text, keywords)
            except Exception as e:
                print(f"Error in AI relevance analysis: {e}")
                semantic_relevance = 0.0
            
            # Also calculate keyword-based relevance as fallback/boost
            keyword_relevance_score = 0.0
            for keyword in keywords:
                if keyword.lower() in text.lower():
                    relevance = keyword_relevance.get(keyword, 0.5)
                    keyword_relevance_score += relevance
            
            # Normalize keyword relevance
            keyword_relevance_score = min(1.0, keyword_relevance_score / len(keywords)) if keywords else 0.0
            
            # Combine semantic and keyword relevance (70% semantic, 30% keyword)
            relevance_score = (semantic_relevance * 0.7) + (keyword_relevance_score * 0.3)
            
            # Calculate total engagement
            total_engagement = like_count + reply_count + retweet_count
            
            # Prioritize posts with significant traction - minimum engagement thresholds
            # LOWERED thresholds to ensure we get posts - can be adjusted later
            min_engagement = {
                'like': 10,      # Lowered from 50 to 10 - posts for liking should have at least 10 likes
                'reply': 20,     # Posts for replying should have at least 20 total engagement
                'engage': 30,    # Lowered from 100 to 30 - posts for engagement should have at least 30 total engagement
                'default': 5     # Lowered from 30 to 5 - default minimum for other types
            }.get(post_type, 5)
            
            if total_engagement < min_engagement:
                filtered_by_engagement += 1
                continue
            
            # Get post URL for embedding - CRITICAL: ensure we have valid username
            tweet_id = tweet.id if hasattr(tweet, 'id') else (tweet.get('id') if isinstance(tweet, dict) else None)
            author_id = tweet.author_id if hasattr(tweet, 'author_id') else (tweet.get('author_id') if isinstance(tweet, dict) else None)
            
            # Get username from our fetched data - this is the key fix
            author_username = 'unknown'
            author_name = 'Unknown'
            author_profile_image = ''
            author_verified = False
            
            if author_id and str(author_id) in author_usernames:
                author_username = author_usernames[str(author_id)]
                if str(author_id) in author_data:
                    author_name = author_data[str(author_id)].get('name', author_username)
                    author_profile_image = author_data[str(author_id)].get('profile_image', '')
                    author_verified = author_data[str(author_id)].get('verified', False)
            
            # Skip posts without valid usernames - they can't be embedded
            if author_username == 'unknown' or not tweet_id:
                filtered_by_username += 1
                if filtered_by_username <= 3:  # Log first few for debugging
                    print(f"Filtered post: author_username={author_username}, tweet_id={tweet_id}, author_id={author_id}")
                continue
            
            post_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
            
            # Calculate popularity score (weighted engagement)
            # Likes are most important, then replies, then retweets
            popularity_score = (like_count * 1.0) + (reply_count * 1.5) + (retweet_count * 0.8)
            
            # Calculate quality score based on content signals
            quality_score = 0.0
            # Check for threads (conversation_id indicates potential thread)
            if hasattr(tweet, 'conversation_id') and tweet.conversation_id:
                conversation_id = tweet.conversation_id if hasattr(tweet, 'conversation_id') else (tweet.get('conversation_id') if isinstance(tweet, dict) else None)
                if conversation_id and str(conversation_id) == str(tweet_id):
                    quality_score += 0.2  # Original thread starter
            
            # Check for detailed/educational content (longer posts)
            if len(text.split()) > 50:
                quality_score += 0.2
            
            # Verified authors get quality boost
            if author_verified:
                quality_score += 0.1
            
            # High engagement relative to account size (if we had follower data, would calculate engagement rate)
            # For now, just boost posts with very high engagement
            if total_engagement > 500:
                quality_score += 0.1
            
            quality_score = min(1.0, quality_score)
            
            posts.append({
                'id': str(tweet_id),
                'text': text,
                'author_id': str(author_id) if author_id else None,
                'author_username': author_username,
                'author_name': author_name,
                'author_profile_image': author_profile_image,
                'author_verified': author_verified,
                'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                'likes': like_count,
                'replies': reply_count,
                'retweets': retweet_count,
                'relevance_score': relevance_score,
                'popularity_score': popularity_score,
                'quality_score': quality_score,
                'total_engagement': total_engagement,
                'type': post_type,
                'url': post_url  # Always valid URL since we skip posts without usernames
            })
        
        print(f"Filtered {filtered_by_engagement} posts by engagement threshold, {filtered_by_username} posts by missing username")
        print(f"Added {len(posts)} posts after filtering")
        
        if not posts:
            return []
        
        # Calculate final scores for diverse selection
        # Normalize popularity score (divide by max to get 0-1 range)
        max_popularity = max((p['popularity_score'] for p in posts), default=1.0)
        for post in posts:
            post['normalized_popularity'] = min(1.0, post['popularity_score'] / max_popularity) if max_popularity > 0 else 0.0
        
        # Calculate combined score: relevance (35%) + popularity (40%) + quality (25%)
        for post in posts:
            post['combined_score'] = (
                post['relevance_score'] * 0.35 +
                post['normalized_popularity'] * 0.40 +
                post['quality_score'] * 0.25
            )
        
        # Sort by combined score
        posts.sort(key=lambda x: x['combined_score'], reverse=True)
        
        # Implement diverse selection strategy:
        # 30% highly relevant (top relevance scores)
        # 30% highly popular (top popularity scores)
        # 40% balanced (top combined scores)
        total_needed = max_results
        highly_relevant_count = int(total_needed * 0.3)
        highly_popular_count = int(total_needed * 0.3)
        balanced_count = total_needed - highly_relevant_count - highly_popular_count
        
        # Sort by different criteria
        by_relevance = sorted(posts, key=lambda x: x['relevance_score'], reverse=True)
        by_popularity = sorted(posts, key=lambda x: x['normalized_popularity'], reverse=True)
        by_combined = sorted(posts, key=lambda x: x['combined_score'], reverse=True)
        
        # Select diverse mix
        selected_posts = []
        seen_ids = set()
        
        # Add highly relevant posts
        for post in by_relevance[:highly_relevant_count]:
            if post['id'] not in seen_ids:
                selected_posts.append(post)
                seen_ids.add(post['id'])
        
        # Add highly popular posts
        for post in by_popularity[:highly_popular_count]:
            if post['id'] not in seen_ids:
                selected_posts.append(post)
                seen_ids.add(post['id'])
        
        # Fill remaining with balanced posts
        for post in by_combined:
            if len(selected_posts) >= total_needed:
                break
            if post['id'] not in seen_ids:
                selected_posts.append(post)
                seen_ids.add(post['id'])
        
        # Sort final selection by combined score
        selected_posts.sort(key=lambda x: x['combined_score'], reverse=True)
        posts = selected_posts[:max_results]
        
        print(f"Selected {len(posts)} posts using diverse selection strategy (relevance: {highly_relevant_count}, popularity: {highly_popular_count}, balanced: {balanced_count})")
        
        # Verify all posts have URLs (they should all have URLs since we skip posts without usernames)
        posts_with_urls = [p for p in posts if p.get('url')]
        if len(posts_with_urls) < len(posts):
            print(f"Warning: {len(posts) - len(posts_with_urls)} posts missing URLs, filtering them out")
        
        print(f"Returning {len(posts_with_urls)} posts with URLs for onboarding (type: {post_type}, requested: {max_results})")
        return posts_with_urls
        
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

