# X Growth AI Tool

A personal distribution operating system with a learning AI brain that adapts to your persona over time.

## Features

1. **Content Intelligence** - Analyze X Lists to extract patterns, hooks, topics, and engagement insights
2. **Content Machine** - Generate persona-aligned posts with smart scheduling
3. **Reply Guy** - Automated reply suggestions with Telegram notifications
4. **Personal Voice Memory** - Continuously learns your preferences, tone, and engagement style
5. **Daily Actions Dashboard** - "What Should I Do Today?" with prioritized actions and progress tracking

## Core Philosophy

This tool doesn't just generate content—it makes decisions the way you would, then assists execution. Everything revolves around the **Persona State**, a continuously updated representation of:
- What you care about (topics)
- How you express yourself (tone & style)
- How you engage (behavior patterns)
- Your risk tolerance
- Your energy & cadence

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required:
- **X/Twitter API**: Get keys from [Twitter Developer Portal](https://developer.twitter.com/)
- **OpenAI API**: Get key from [OpenAI Platform](https://platform.openai.com/)

Optional:
- **Telegram Bot**: For reply notifications (get token from [@BotFather](https://t.me/botfather))

### 3. Run the Application

```bash
python app.py
```

Or with uvicorn directly:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### 4. Access the Web UI

Open your browser to: `http://127.0.0.1:8000`

## Onboarding

### Phase 1: Passive Ingestion (Automatic)

On first run, the tool will:
1. Pull your last 30-60 days of X activity
2. Extract initial Persona State from:
   - Liked posts → topic affinity
   - Your posts → tone & style
   - Engagement patterns → behavior baseline

Run via API:
```bash
curl -X POST http://127.0.0.1:8000/api/onboarding/phase1?username=your_username
```

## Usage

### Content Intelligence

Analyze X Lists to understand patterns:
1. Go to "Content Intelligence" section
2. Enter a List ID
3. View AI-generated analysis of topics, hooks, tone, and engagement

### Content Machine

Generate and schedule posts:
1. Go to "Content Machine" section
2. Click "Generate Monthly Posts"
3. Review, edit, approve, or delete posts
4. Posts are scheduled based on your persona cadence

### Reply Guy

Get smart reply suggestions:
1. Configure X Lists to monitor in `data/account_lists.json`
2. Click "Check for Reply Opportunities"
3. Receive Telegram notifications with reply suggestions
4. Choose which replies to use

### Daily Actions Dashboard

Your main control center:
- See daily targets (posts, replies, likes)
- View prioritized action list
- Track progress throughout the day
- Sync actions from X API

## How It Learns

The system learns from four types of feedback:

1. **Explicit**: Edits, approvals, rejections
2. **Behavioral**: Likes, replies, follows
3. **Temporal**: Speed of actions, hesitation
4. **Outcome**: Performance vs your baseline

All updates are incremental (max 10% change per update) to prevent personality drift.

## Data Storage

All data is stored locally in JSON files:
- `data/persona_state.json` - Your persona brain
- `data/account_lists.json` - X Lists to monitor
- `data/content_schedule.json` - Scheduled posts
- `data/activity_log.json` - Daily activity tracking

## API Endpoints

### Persona State
- `GET /api/persona/state` - Get current persona
- `GET /api/persona/explanation` - Human-readable summary

### Content Intelligence
- `GET /api/content-intelligence/analyze/{list_id}` - Analyze a list
- `POST /api/content-intelligence/analyze-multiple` - Analyze multiple lists

### Content Machine
- `POST /api/content-machine/generate` - Generate posts
- `GET /api/content-machine/schedule` - Get scheduled posts
- `PUT /api/content-machine/posts/{post_id}` - Update post
- `DELETE /api/content-machine/posts/{post_id}` - Delete post
- `POST /api/content-machine/posts/{post_id}/approve` - Approve post

### Daily Actions
- `GET /api/daily-actions/targets` - Get daily targets
- `GET /api/daily-actions/prioritized` - Get prioritized actions
- `GET /api/daily-actions/progress` - Get today's progress
- `POST /api/daily-actions/track` - Track completed action
- `POST /api/daily-actions/sync` - Sync from X API

### Reply Guy
- `POST /api/reply-guy/check` - Check for opportunities
- `GET /api/reply-guy/pending` - Get pending replies
- `POST /api/reply-guy/mark-used/{post_id}` - Mark reply as used

## Important Notes

- **No Auto-Posting**: All actions require manual approval
- **Single User**: Designed for personal use
- **Privacy**: All data stored locally
- **Learning**: System improves over time based on your choices

## Troubleshooting

### X API Errors
- Ensure API keys are correct in `.env`
- Check rate limits (tool handles this automatically)
- Verify OAuth permissions

### OpenAI Errors
- Check API key is valid
- Ensure you have credits
- Check rate limits

### Telegram Notifications Not Working
- Verify bot token from @BotFather
- Get your chat ID (send message to bot, check logs)
- Add `TELEGRAM_CHAT_ID` to `.env`

## Development

This is a lean prototype built for speed and clarity. The codebase is intentionally simple with minimal abstractions to enable fast iteration.

## License

Personal use only.

