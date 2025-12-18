# X Growth AI Tool - Feature Logic Documentation

## Overview

This document describes the complete logic flows for all features in the X Growth AI Tool, including data flows, user interactions, and system behaviors.

## Core Architecture

```
User → Authentication → Onboarding → Persona State → Features
                                              ↓
                                    Learning Loop (Continuous)
```

## 1. Authentication & User Management

### Flow
1. User registers with email/password
2. System creates user account and session token (30-day expiry)
3. User data stored in `data/users/users.json`
4. Session stored in `data/sessions.json`
5. Each user has isolated data directory: `data/users/{user_id}/`

### User Data Structure
- `user_id`: Unique identifier
- `email`: User email
- `password_hash`: Hashed password
- `x_username`: Connected X username
- `x_connected`: Boolean
- `onboarding_step`: Current step (1-4 or "complete")
- `onboarding_complete`: Boolean
- `keywords`: List of keywords
- `keyword_relevance`: Dict mapping keywords to relevance scores (0.1-1.0)
- `interactive_onboarding`: Progress tracking for phase 4

## 2. Onboarding Flow

### Step 1: Connect X Account
- User enters X username
- System searches for user via X API
- Autocomplete dropdown shows matching accounts with profile pictures
- User selects their account
- System verifies connection and stores username
- **Next**: Step 2

### Step 2: Keywords Selection
- User adds keywords using tag-based input (minimum 3 required)
- System analyzes keywords with AI:
  - Checks relevance
  - Suggests improvements
  - Identifies overlapping keywords
- User reviews analysis and continues
- Keywords saved to user profile
- **Next**: Step 3

### Step 3: Relevance Sliders
- User sees all keywords in grid layout
- Each keyword has slider (10%-100%)
- User adjusts relevance for each keyword
- Quick actions: "Low" (25%), "Medium" (50%), "High" (75%)
- "Set All to 50%" quick action
- Relevance scores saved
- **Next**: Step 4 (Interactive Onboarding)

### Step 4: Interactive Onboarding (Dashboard)
**Phase 1: Content Preference (20 posts)**
- System fetches posts based on keywords
- User sees posts one by one (embedded from X or custom design)
- User responds: "Yes, I like this" or "No, not for me"
- Progress tracked: "X of 20 completed (Y liked, Z skipped)"
- Responses update persona state incrementally

**Phase 2: Engagement Preference (10 posts)**
- System shows posts user might engage with
- User responds: "Yes, I would engage" or "No, I wouldn't"
- Progress tracked: "X of 10 completed (Y would engage)"
- Updates engagement behavior in persona state

**Phase 3: Like/Skip Preference (20 posts)**
- System shows posts for like/skip decision
- User responds: "Like" or "Skip"
- Progress tracked: "X of 20 completed (Y liked, Z skipped)"
- Updates topic affinity and engagement patterns

**Phase 4: Profile Subscription (10 profiles)**
- System shows profiles with scrollable feeds
- User sees profile info and recent posts
- User responds: "Subscribe" or "Skip this profile"
- Progress tracked: "X of 10 completed (Y subscribed, Z skipped)"
- Updates account preferences

**Skip Functionality:**
- "Skip This Phase" button available at any time
- "Skip All" button to complete onboarding with minimal setup
- Skipped phases use default persona state
- User can return to onboarding later

## 3. Persona State

### Structure
```json
{
  "topic_affinity": {
    "saas": 0.8,
    "ai": 0.9,
    "startups": 0.7,
    ...
  },
  "tone_style": {
    "sentence_length": "medium",
    "question_frequency": 0.3,
    "humor_frequency": 0.2,
    "emotional_intensity": "moderate",
    "formality": "casual",
    "contrarian_tolerance": 0.4,
    "certainty_level": "balanced"
  },
  "engagement_behavior": {
    "likes_per_day_baseline": 20,
    "replies_per_day_baseline": 5,
    "early_engagement_tendency": 0.6,
    "reply_vs_like_ratio": 0.25
  },
  "risk_sensitivity": {
    "hot_takes_comfort": 0.3,
    "safe_vs_experimental": 0.7,
    "challenge_others_tendency": 0.4
  },
  "energy_cadence": {
    "posts_per_day_tolerance": 2,
    "engagement_fatigue_signals": [],
    "preferred_posting_times": [],
    "consistency_preference": "moderate"
  }
}
```

### Learning Loop
- **Explicit Feedback**: Edits, approvals, rejections → Immediate updates
- **Behavioral Feedback**: Likes, replies, follows → Incremental updates
- **Temporal Feedback**: Speed of actions, hesitation → Pattern recognition
- **Outcome Feedback**: Performance vs baseline → Long-term adjustments

### Update Rules
- Maximum 10% change per update (prevents personality drift)
- Incremental adjustments only
- All updates are explainable

## 4. Content Intelligence

### Flow
1. User provides X List ID
2. System fetches list members and their recent posts
3. AI analyzes:
   - Recurring topics
   - Common hooks (first-line patterns)
   - Post length distribution
   - Tone patterns
   - Engagement patterns
   - Posting frequency
4. Returns text-based summary (not dashboard)
5. Analysis stored for reference

### Logic
- **Read-only**: Does not modify persona state
- **External signals**: Informs but doesn't dictate behavior
- **Filtered through Persona**: External trends inform, persona decides

## 5. Content Machine

### Post Generation Flow
1. User clicks "Generate Monthly Posts"
2. System:
   - Loads persona state
   - Optionally uses external signals from Content Intelligence
   - Generates ~30 posts using AI
   - Each post includes:
     - Content text
     - Rationale (why it fits persona)
     - Topic tags
     - Suggested scheduling
3. Posts stored as "draft" status

### Post Management Flow
1. User reviews generated posts in dashboard
2. User can:
   - **Edit**: Modify content
   - **Approve**: Move to "approved" status, set schedule
   - **Delete**: Remove post
3. Approved posts require:
   - Scheduled date
   - Scheduled time
4. Posts stored with scheduling info

### Posting Flow (Hybrid Approval System)
1. **Scheduling**: Approved posts have scheduled date/time
2. **Notification**: System checks every 5 minutes for ready posts
3. **Review**: User sees notification: "X posts ready to publish"
4. **Approval**: User reviews each post
5. **Posting**: User clicks "Post to X" → Explicit confirmation → Post to X API
6. **Tracking**: Post marked as "posted" with tweet_id and timestamp

### Status Flow
```
draft → (approve) → approved → (schedule) → scheduled → (post) → posted
  ↓                    ↓
(edit)              (delete)
```

## 6. Reply Guy Engine

### Monitoring Flow
1. User configures X Lists to monitor
2. System periodically checks lists for new posts
3. Detects posts not yet tracked
4. For each new post:
   - Generates 2-3 reply suggestions using AI
   - Each suggestion has:
     - Content
     - Angle (extend, challenge, question, agree)
     - Rationale (why it fits persona)
   - Filters suggestions through persona state
5. Stores as "pending" reply opportunities

### Notification Flow
1. System sends Telegram notification (if configured)
2. Notification includes:
   - Original post content
   - Author info
   - Reply suggestions
3. User receives notification

### Reply Management Flow
1. User views pending replies in dashboard
2. For each reply opportunity:
   - User sees original post
   - User sees reply suggestions
   - User can:
     - **Edit**: Modify reply content
     - **Post to X**: Post reply directly (with approval)
     - **Skip**: Mark as used without posting

### Posting Flow (Hybrid Approval System)
1. User selects reply suggestion (or edits it)
2. User clicks "Post to X"
3. System shows confirmation dialog
4. User confirms
5. System posts reply to X API (as reply to original tweet)
6. Reply marked as "used" and "posted"
7. Tweet ID stored for tracking

## 7. Daily Actions Dashboard

### Target Calculation
1. System loads persona state
2. Calculates baseline targets:
   - Posts: Based on `posts_per_day_tolerance`
   - Replies: Based on `replies_per_day_baseline`
   - Likes: Based on `likes_per_day_baseline`
   - Follows: Based on engagement patterns
3. Adjusts for:
   - Recent activity (fatigue signals)
   - Day of week patterns
   - Growth momentum
4. Returns dynamic targets

### Progress Tracking
1. System tracks today's activity:
   - Posts published
   - Replies posted
   - Likes given
   - Follows made
2. Calculates:
   - Completed vs targets
   - Remaining actions needed
   - Completion percentage
3. Updates in real-time as user takes actions

### Prioritized Actions
1. System generates prioritized list:
   - Scheduled posts ready to publish (top priority)
   - Reply opportunities (high priority)
   - Engagement suggestions (medium priority)
2. Each action includes:
   - Description
   - Rationale
   - Priority level
3. User can complete actions directly from dashboard

### Engagement Browser
1. User clicks "Browse & Engage"
2. System fetches posts based on:
   - Keywords
   - Keyword relevance
   - Persona preferences
3. Shows posts one by one (embedded from X or custom design)
4. User can:
   - **Like**: Tracks toward daily likes goal
   - **Reply**: Opens reply interface, tracks toward replies goal
   - **Skip**: Move to next post
5. Actions update daily progress in real-time
6. Shows progress: "Post X of Y"

## 8. X API Integration

### Authentication
- **twitterapi.io**: Uses `X_API_KEY` as `x-api-key` header
- **Official X API**: Uses `X_BEARER_TOKEN` or OAuth 2.0
- System auto-detects which API to use
- Falls back to HTTP client if tweepy fails

### Posting Capabilities
- **Official X API**: Full posting support via `create_tweet()`
- **twitterapi.io**: Read-only (posting not supported)
- **Hybrid System**: Requires explicit approval before each post
- **Error Handling**: Graceful degradation if posting fails

### Rate Limits
- System respects X API rate limits
- Automatic retry with backoff
- Error messages guide user

## 9. Data Storage

### User-Specific Data
- `data/users/{user_id}/persona_state.json`: Persona state
- `data/users/{user_id}/content_schedule.json`: Scheduled posts
- `data/users/{user_id}/onboarding_posts_phase*.json`: Cached onboarding posts
- `data/users/{user_id}/onboarding_accounts.json`: Cached onboarding accounts

### Shared Data
- `data/users/users.json`: User accounts
- `data/sessions.json`: Active sessions
- `data/reply_tracking.json`: Reply tracking (global)
- `data/pending_replies.json`: Pending reply opportunities (global)

### Ephemeral Storage Note
- On Railway, file system is ephemeral
- Data resets on each deployment
- **Long-term solution**: Migrate to PostgreSQL

## 10. Feature Interconnections

### How Features Read/Write Persona State

**Content Intelligence:**
- **Reads**: Topic weights, tone tolerance
- **Writes**: External trend signals (informational only)

**Content Machine:**
- **Reads**: Tone, topic affinity, cadence
- **Writes**: Approval/rejection signals, posting behavior

**Reply Guy:**
- **Reads**: Reply style, risk tolerance, engagement patterns
- **Writes**: Reply preference learning, engagement behavior

**Daily Actions:**
- **Reads**: Energy, cadence, recent behavior
- **Writes**: Fatigue signals, consistency updates

**Engagement Browser:**
- **Reads**: Keywords, topic affinity, engagement patterns
- **Writes**: Engagement behavior, topic preferences

**Onboarding:**
- **Reads**: Initial keywords and relevance
- **Writes**: Initial persona state, topic affinity, engagement patterns

## 11. Approval Workflows

### Content Machine Approval
```
Generate → Draft → Review → Edit (optional) → Approve → Schedule → Ready → Confirm → Post to X
```

### Reply Guy Approval
```
Monitor → Detect → Generate Suggestions → Telegram Notification → Review → Edit (optional) → Confirm → Post to X
```

### Key Principles
- **No Auto-Posting**: Every post requires explicit user approval
- **Confirmation Dialogs**: "Are you sure?" before posting
- **Edit Before Post**: User can always edit before posting
- **Transparency**: User sees exactly what will be posted

## 12. Scheduling System

### How It Works
1. User approves post and sets schedule (date + time)
2. Post stored with `scheduled_date` and `scheduled_time`
3. System checks every 5 minutes for ready posts:
   - Compares current time with scheduled time
   - Finds posts where `scheduled_datetime <= now` and `status == "approved"` and `posted == false`
4. Shows notification to user
5. User reviews and posts (with approval)

### Implementation
- Client-side polling (every 5 minutes)
- Server endpoint: `/api/content-machine/posts-ready`
- Returns list of posts ready to post
- User must explicitly approve each post before publishing

## 13. Error Handling

### X API Errors
- **401 Unauthorized**: Logs warning, returns empty data, allows onboarding to continue
- **404 Not Found**: Handles gracefully, shows placeholder content
- **Rate Limits**: Automatic retry with backoff
- **Network Errors**: Graceful degradation, user-friendly messages

### Graceful Degradation
- If X API fails during onboarding: Shows placeholder content, allows completion
- If oEmbed fails: Falls back to custom X-like design
- If posting fails: Shows error, allows retry

## 14. User Experience Flows

### First-Time User
1. Register → Login
2. Step 1: Connect X account (with autocomplete)
3. Step 2: Add keywords (tag-based, AI analysis)
4. Step 3: Set relevance (grid sliders)
5. Step 4: Interactive onboarding (4 phases, can skip)
6. Dashboard: Daily actions, engagement browser

### Returning User
1. Login
2. Dashboard shows:
   - Daily action progress
   - Ready posts to publish
   - Pending reply opportunities
   - Engagement browser
3. Can complete onboarding if skipped

### Daily Usage
1. Check dashboard for daily targets
2. Review ready posts → Post to X
3. Check pending replies → Post replies
4. Browse & Engage to complete daily goals
5. Generate new content as needed

## 15. Security & Privacy

### Authentication
- Passwords hashed with bcrypt
- Session tokens (30-day expiry)
- User-specific data isolation

### API Keys
- Stored in environment variables
- Never exposed to client
- Secure handling of credentials

### Data Privacy
- All data stored locally (or in user-specific directories)
- No data sharing between users
- User can delete their data

## 16. Future Enhancements

### Planned Improvements
- PostgreSQL migration for persistent storage
- Real-time notifications (WebSocket)
- Advanced scheduling (recurring posts)
- Analytics dashboard
- Export/import persona state
- Multi-account support

### Known Limitations
- Railway ephemeral filesystem (data resets on deploy)
- twitterapi.io doesn't support posting (needs official API)
- No real-time updates (polling-based)
- Single-user only (by design)

