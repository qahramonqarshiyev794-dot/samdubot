# SamDu Telegram Bot

Telegram chat bot powered by the OpenAI API.

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
   OpenAI API key in `main.env`.
5. Start the bot:

   ```powershell
   python bot.py
   ```

The `main.env` file contains secrets and is excluded from Git.

## Deploy on Render

The included `render.yaml` configures a free Python web service. Create a
Blueprint from this repository and set `TELEGRAM_BOT_TOKEN` and
`OPENAI_API_KEY` as Render environment variables; never upload `main.env`.
Render automatically registers the Telegram webhook when the service starts.
Locally, the bot continues to use polling.

Render's Free web services can sleep after 15 minutes without inbound traffic
and may take about a minute to wake. Telegram messages can therefore be delayed
while the service starts. Conversation history is kept in memory and is lost
when the service restarts or sleeps; this plan is intended for hobby use, not
production.

## Troubleshooting

OpenAI API access and billing are separate from a ChatGPT subscription. If the
bot cannot answer, check the Render logs and confirm `OPENAI_API_KEY` is valid.
A `401` or `403` means the key is invalid or lacks access; a `429` may mean the
API limit or available credit has been reached.
