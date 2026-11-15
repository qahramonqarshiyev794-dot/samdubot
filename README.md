# SamDu Telegram Bot

Telegram chat bot powered by the Google Gemini API.

## Setup

1. Install Python 3.13 or later.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Copy `main.env.example` to `main.env` and set your Telegram bot token and
   Gemini API key in `main.env`.
5. Start the bot:

   ```powershell
   python bot.py
   ```

The `main.env` file contains secrets and is excluded from Git.

## Deploy on Render

The included `render.yaml` configures a free Python web service. Create a
Blueprint from this repository and set `TELEGRAM_BOT_TOKEN` and
`GEMINI_API_KEY` as Render environment variables; never upload `main.env`.
Render automatically registers the Telegram webhook when the service starts.
Locally, the bot continues to use polling.

Render's Free web services can sleep after 15 minutes without inbound traffic
and may take about a minute to wake. Telegram messages can therefore be delayed
while the service starts. Conversation history is kept in memory and is lost
when the service restarts or sleeps; this plan is intended for hobby use, not
production.
