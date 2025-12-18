# Quick Start Guide

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

**Required:**
- `X_API_KEY` - From Twitter Developer Portal
- `X_API_SECRET` - From Twitter Developer Portal  
- `X_ACCESS_TOKEN` - From Twitter Developer Portal
- `X_ACCESS_TOKEN_SECRET` - From Twitter Developer Portal
- `X_BEARER_TOKEN` - From Twitter Developer Portal
- `OPENAI_API_KEY` - From OpenAI Platform

**Optional:**
- `TELEGRAM_BOT_TOKEN` - From @BotFather on Telegram
- `TELEGRAM_CHAT_ID` - Your Telegram chat ID

## 3. Run Onboarding (Phase 1)

This will analyze your X activity and create your initial Persona State:

```bash
# Via API (after starting server)
curl -X POST "http://127.0.0.1:8000/api/onboarding/phase1?username=your_username"

# Or via Python
python -c "from onboarding import run_onboarding_phase1; run_onboarding_phase1('your_username')"
```

## 4. Start the Server

```bash
python app.py
```

Or:

```bash
python run.py
```

Or with uvicorn directly:

```bash
uvicorn app:app --reload
```

## 5. Open the Web UI

Navigate to: `http://127.0.0.1:8000`

## First Steps

1. **Check Persona State**: Go to "Persona State" section to see your initial profile
2. **Analyze a List**: Add an X List ID and analyze it in "Content Intelligence"
3. **Generate Posts**: Use "Content Machine" to generate your first batch of posts
4. **Check Dashboard**: See your daily targets in "Dashboard"

## Getting X List IDs

1. Go to X (Twitter)
2. Create or open a List
3. The List ID is in the URL: `https://twitter.com/i/lists/123456789` → ID is `123456789`

## Getting Telegram Chat ID

1. Create a bot with @BotFather
2. Start a chat with your bot
3. Send a message
4. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
5. Find `"chat":{"id":123456789}` → that's your chat ID

## Troubleshooting

**Import errors?**
- Make sure you're in the project directory
- Check that all dependencies are installed: `pip install -r requirements.txt`

**API errors?**
- Verify your API keys in `.env`
- Check that keys don't have extra spaces
- For X API: Ensure you have the right permissions (read-only is fine)

**Port already in use?**
- Change `PORT` in `.env` or edit `app.py`/`run.py`

