"""Telegram Bot Service for notifications"""
from typing import Dict, Any, Optional
import config

try:
    from telegram import Bot
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None


def send_reply_notification(opportunity: Dict[str, Any]) -> bool:
    """
    Send Telegram notification for reply opportunity
    
    Args:
        opportunity: Reply opportunity dictionary
    
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_AVAILABLE or not config.TELEGRAM_BOT_TOKEN:
        print("Telegram not configured - skipping notification")
        return False
    
    if not config.TELEGRAM_CHAT_ID:
        print("Telegram chat ID not configured")
        return False
    
    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
        original_post = opportunity.get("original_post", {})
        suggestions = opportunity.get("suggestions", [])
        
        # Format message
        message = f"🔔 New Reply Opportunity\n\n"
        message += f"From: @{original_post.get('author', 'Unknown')}\n"
        message += f"Post: {original_post.get('text', '')[:200]}...\n\n"
        message += f"💡 Reply Suggestions:\n\n"
        
        for i, suggestion in enumerate(suggestions[:3], 1):
            angle = suggestion.get("angle", "extend")
            content = suggestion.get("content", "")
            rationale = suggestion.get("rationale", "")
            
            message += f"{i}. [{angle.upper()}] {content}\n"
            message += f"   Why: {rationale[:100]}...\n\n"
        
        # Send message
        bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=None
        )
        
        return True
    
    except TelegramError as e:
        print(f"Telegram error: {e}")
        return False
    except Exception as e:
        print(f"Error sending Telegram notification: {e}")
        return False


def send_daily_summary(summary: Dict[str, Any]) -> bool:
    """
    Send daily summary via Telegram
    
    Args:
        summary: Daily summary dictionary
    
    Returns:
        True if sent successfully
    """
    if not TELEGRAM_AVAILABLE or not config.TELEGRAM_BOT_TOKEN:
        return False
    
    if not config.TELEGRAM_CHAT_ID:
        return False
    
    try:
        bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        
        message = f"📊 Daily Summary - {summary.get('date', 'Today')}\n\n"
        message += f"Targets:\n"
        targets = summary.get("targets", {})
        message += f"  • Posts: {targets.get('posts', 0)}\n"
        message += f"  • Replies: {targets.get('replies', 0)}\n"
        message += f"  • Likes: {targets.get('likes', 0)}\n\n"
        
        completed = summary.get("completed", {})
        message += f"Completed:\n"
        message += f"  • Posts: {completed.get('posts', 0)}\n"
        message += f"  • Replies: {completed.get('replies', 0)}\n"
        message += f"  • Likes: {completed.get('likes', 0)}\n"
        
        bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=message
        )
        
        return True
    
    except Exception as e:
        print(f"Error sending daily summary: {e}")
        return False

