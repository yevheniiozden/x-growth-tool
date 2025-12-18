"""AI Service - OpenAI integration with persona-aware prompts"""
import openai
from typing import Dict, Any, List, Optional
import config
from core.persona_state import load_persona_state

# Initialize OpenAI client
if config.OPENAI_API_KEY:
    openai.api_key = config.OPENAI_API_KEY
    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
else:
    client = None


def _get_persona_context(user_id: Optional[str] = None) -> str:
    """Get Persona State as context string for prompts"""
    state = load_persona_state(user_id)
    
    context = f"""User's Persona Profile:

TOPIC AFFINITY (0-1 scale):
"""
    for topic, weight in sorted(state["topic_affinity"].items(), key=lambda x: x[1], reverse=True):
        context += f"- {topic}: {weight:.1%}\n"
    
    context += f"""
TONE & STYLE:
- Sentence length preference: {state['tone_style']['sentence_length']}
- Question frequency: {state['tone_style']['question_frequency']:.1%}
- Humor frequency: {state['tone_style']['humor_frequency']:.1%}
- Emotional intensity: {state['tone_style']['emotional_intensity']}
- Formality: {state['tone_style']['formality']}
- Contrarian tolerance: {state['tone_style']['contrarian_tolerance']:.1%}
- Certainty level: {state['tone_style']['certainty_level']}

ENGAGEMENT BEHAVIOR:
- Likes per day baseline: {state['engagement_behavior']['likes_per_day_baseline']}
- Replies per day baseline: {state['engagement_behavior']['replies_per_day_baseline']}
- Early engagement tendency: {state['engagement_behavior']['early_engagement_tendency']:.1%}

RISK SENSITIVITY:
- Hot takes comfort: {state['risk_sensitivity']['hot_takes_comfort']:.1%}
- Safe vs experimental: {state['risk_sensitivity']['safe_vs_experimental']:.1%}
- Challenge others tendency: {state['risk_sensitivity']['challenge_others_tendency']:.1%}
"""
    
    return context


def extract_topics_from_text(text: str) -> Dict[str, float]:
    """
    Extract topics from text using AI
    
    Args:
        text: Text to analyze
    
    Returns:
        Dict mapping topics to weights (0-1)
    """
    if not client or not text:
        return {}
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a topic extraction assistant. Extract main topics from the given text and return them as a JSON object with topic names as keys and relevance scores (0-1) as values. Focus on topics like: AI, startups, SaaS, product, design, marketing, productivity, business, tech, etc."},
                {"role": "user", "content": f"Extract topics from this text:\n\n{text[:500]}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"Error extracting topics: {e}")
        # Fallback: simple keyword matching
        topics = {}
        text_lower = text.lower()
        topic_keywords = {
            'ai': ['ai', 'artificial intelligence', 'machine learning', 'ml'],
            'startups': ['startup', 'entrepreneur', 'founder'],
            'saas': ['saas', 'software', 'platform'],
            'product': ['product', 'feature', 'development'],
            'design': ['design', 'ui', 'ux', 'visual'],
            'marketing': ['marketing', 'growth', 'advertising'],
            'productivity': ['productivity', 'efficiency', 'workflow'],
            'business': ['business', 'company', 'revenue'],
            'tech': ['tech', 'technology', 'coding', 'developer']
        }
        
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    topics[topic] = 0.5
                    break
        
        return topics


def analyze_tone(text: str) -> Dict[str, Any]:
    """
    Analyze tone and style of text
    
    Args:
        text: Text to analyze
    
    Returns:
        Dict with tone characteristics
    """
    if not client or not text:
        return {}
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a tone analysis assistant. Analyze the tone and style of the given text and return a JSON object with: sentence_length (short/medium/long), question_frequency (0-1), humor_present (true/false), emotional_intensity (low/moderate/high), formality (casual/formal)."},
                {"role": "user", "content": f"Analyze the tone of this text:\n\n{text[:500]}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        return result
        
    except Exception as e:
        print(f"Error analyzing tone: {e}")
        # Fallback: simple heuristics
        tone = {
            "sentence_length": "medium",
            "question_frequency": text.count('?') / max(len(text.split('.')) + len(text.split('!')), 1),
            "humor_present": False,
            "emotional_intensity": "moderate",
            "formality": "casual"
        }
        
        avg_sentence_length = len(text.split()) / max(text.count('.') + text.count('!'), 1)
        if avg_sentence_length < 10:
            tone["sentence_length"] = "short"
        elif avg_sentence_length > 25:
            tone["sentence_length"] = "long"
        
        return tone


def analyze_content_patterns(posts: List[Dict[str, Any]], user_id: Optional[str] = None) -> str:
    """
    Analyze posts from X Lists to extract patterns
    
    Args:
        posts: List of post dictionaries with 'text', 'author', etc.
    
    Returns:
        Markdown-formatted analysis report
    """
    if not client:
        return "Error: OpenAI API key not configured"
    
    # Prepare posts text
    posts_text = "\n\n---\n\n".join([
        f"Author: {post.get('author', 'Unknown')}\nPost: {post.get('text', '')}"
        for post in posts[:50]  # Limit to 50 posts for token efficiency
    ])
    
    persona_context = _get_persona_context(user_id)
    
    prompt = f"""{persona_context}

Analyze the following posts from accounts the user follows. Extract patterns that align with the user's persona profile above.

Posts to analyze:
{posts_text}

Provide a comprehensive analysis in markdown format covering:
1. Top topics (prioritize those matching user's topic affinity)
2. Common hooks (first-line patterns that grab attention)
3. Post length distribution
4. Tone patterns (how do these posts match or differ from user's tone?)
5. Engagement patterns (what types of posts get engagement?)

Focus on insights that would help generate content that matches the user's persona.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert social media analyst who understands content patterns and user personas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error analyzing content: {str(e)}"


def generate_posts(count: int = 30, external_signals: Optional[str] = None, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Generate persona-aligned post ideas
    
    Args:
        count: Number of posts to generate
        external_signals: Analysis from Feature 1 (optional)
    
    Returns:
        List of post dictionaries with content, rationale, tags
    """
    if not client:
        return [{"error": "OpenAI API key not configured"}]
    
    persona_context = _get_persona_context(user_id)
    
    signals_context = ""
    if external_signals:
        signals_context = f"\n\nExternal Content Analysis:\n{external_signals}\n\nUse these insights to inform post generation."
    
    prompt = f"""{persona_context}
{signals_context}

Generate {count} post ideas that match the user's persona profile. Each post should:

1. Be 1-3 sentences maximum
2. Match the user's tone and style preferences
3. Align with topics the user cares about (prioritize high-affinity topics)
4. Respect the user's risk sensitivity level
5. Include a brief rationale explaining why it fits the persona

Format as JSON array with this structure:
[
  {{
    "content": "Post text here",
    "rationale": "Why this fits the user's persona",
    "topic_tags": ["topic1", "topic2"],
    "tone_match": "How it matches tone preferences"
  }}
]

Generate diverse post types: insights, opinions, relatable content, questions, commentary.
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert content creator who understands user personas and creates authentic, engaging social media content. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        
        import json
        content = response.choices[0].message.content
        
        # Try to parse JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # If parsing fails, try to extract JSON from text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return [{"error": "Failed to parse AI response as JSON"}]
        
        # Ensure it's a list
        if isinstance(result, dict) and "posts" in result:
            posts = result["posts"]
        elif isinstance(result, list):
            posts = result
        elif isinstance(result, dict):
            # Single post object
            posts = [result]
        else:
            posts = []
        
        # Add IDs and ensure all required fields
        for i, post in enumerate(posts):
            post["id"] = f"post_{i+1}"
            if "rationale" not in post:
                post["rationale"] = "Generated based on persona profile"
            if "topic_tags" not in post:
                post["topic_tags"] = []
            if "tone_match" not in post:
                post["tone_match"] = "Matches persona tone"
        
        return posts[:count]  # Ensure we return exactly count
    
    except Exception as e:
        return [{"error": f"Error generating posts: {str(e)}"}]


def generate_reply_suggestions(
    original_post: Dict[str, Any],
    count: int = 3,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Generate persona-aligned reply suggestions
    
    Args:
        original_post: Original post to reply to (with 'text', 'author')
        count: Number of reply suggestions (default 3)
    
    Returns:
        List of reply dictionaries with content, angle, rationale
    """
    if not client:
        return [{"error": "OpenAI API key not configured"}]
    
    persona_context = _get_persona_context(user_id)
    
    prompt = f"""{persona_context}

Original post to reply to:
Author: {original_post.get('author', 'Unknown')}
Content: {original_post.get('text', '')}

Generate {count} reply suggestions with different angles:
1. Extend (add insight or perspective)
2. Question (clarify or discuss)
3. Challenge (respectful disagreement or alternative view)
4. Personal reflection (relate to own experience)

Each reply should:
- Match the user's tone and style
- Respect the user's risk sensitivity (don't be too aggressive if risk tolerance is low)
- Be thoughtful and add value (not generic "nice post" responses)
- Be 1-2 sentences maximum

Format as JSON array:
[
  {{
    "content": "Reply text here",
    "angle": "extend|question|challenge|reflection",
    "rationale": "Why this reply fits the user's persona"
  }}
]
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert at crafting thoughtful, persona-aligned social media replies that add value to conversations. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )
        
        import json
        content = response.choices[0].message.content
        
        # Try to parse JSON
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # If parsing fails, try to extract JSON from text
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                return [{"error": "Failed to parse AI response as JSON"}]
        
        # Ensure it's a list
        if isinstance(result, dict) and "replies" in result:
            replies = result["replies"]
        elif isinstance(result, list):
            replies = result
        elif isinstance(result, dict):
            # Single reply object
            replies = [result]
        else:
            replies = []
        
        # Add IDs and ensure all required fields
        for i, reply in enumerate(replies):
            reply["id"] = f"reply_{i+1}"
            if "angle" not in reply:
                reply["angle"] = "extend"
            if "rationale" not in reply:
                reply["rationale"] = "Matches persona engagement style"
        
        return replies[:count]
    
    except Exception as e:
        return [{"error": f"Error generating replies: {str(e)}"}]


def explain_persona_alignment(content: str, content_type: str = "post", user_id: Optional[str] = None) -> str:
    """
    Generate explanation of why content aligns with persona
    
    Args:
        content: Content to explain
        content_type: 'post' or 'reply'
    
    Returns:
        Explanation text
    """
    if not client:
        return "OpenAI API key not configured"
    
    persona_context = _get_persona_context(user_id)
    
    prompt = f"""{persona_context}

{content_type.capitalize()} content:
{content}

Explain in 2-3 sentences why this content aligns with the user's persona profile. Be specific about which persona traits it activates (topics, tone, style, etc.).
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You explain content alignment with user personas clearly and concisely."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating explanation: {str(e)}"

