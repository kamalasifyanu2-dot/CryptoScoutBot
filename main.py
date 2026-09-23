import os
import asyncio
import logging
import io
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from telegram import Bot
from google import genai

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Environment Variables
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # e.g., @your_channel_name
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not CHANNEL_ID:
    logger.error("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID environment variables!")
    exit(1)

bot = Bot(token=TOKEN)

# Initialize Gemini Client if API key is provided
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.warning(f"Could not initialize Gemini client: {e}")

def fetch_crypto_data():
    """Fetches trending and top coins from CoinGecko API."""
    try:
        # Fetch top coins by market cap
        market_url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 5,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }
        res = requests.get(market_url, params=params, timeout=10)
        top_coins = res.json() if res.status_code == 200 else []

        # Fetch trending search coins
        trending_url = "https://api.coingecko.com/api/v3/search/trending"
        trend_res = requests.get(trending_url, timeout=10)
        trending_data = trend_res.json() if trend_res.status_code == 200 else {}
        trending_coins = [item["item"]["name"] for item in trending_data.get("coins", [])[:3]]

        return top_coins, trending_coins
    except Exception as e:
        logger.error(f"Error fetching crypto data: {e}")
        return [], []

def generate_ai_commentary(top_coins):
    """Generates market summary and buy/sell signals using Gemini AI."""
    if not gemini_client or not top_coins:
        return "📊 Market update processed successfully. Stay tuned for further breakout opportunities!"
    
    try:
        coin_summary = "\n".join([
            f"- {c['name']} ({c['symbol'].upper()}): ${c['current_price']} | 24h Change: {c.get('price_change_percentage_24h', 0):.2f}%"
            for c in top_coins
        ])
        
        prompt = f"""
        You are CryptoScoutBot, a smart crypto market companion. 
        Here is the current live market data for top assets:
        {coin_summary}
        
        Write a concise, professional crypto market update for Telegram subscribers. 
        Include:
        1. A brief market sentiment overview.
        2. Quick buy/sell/hold outlook based on the data.
        3. Use engaging emojis and professional formatting. Keep it under 150 words.
        """
        
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini generation error: {e}")
        return "📈 Markets are active today. Monitor key resistance levels and trade safely!"

def create_crypto_chart(top_coins):
    """Generates an image graphic comparing 24h performance of top coins."""
    try:
        names = [c['symbol'].upper() for c in top_coins]
        changes = [c.get('price_change_percentage_24h', 0) for c in top_coins]
        
        plt.figure(figsize=(8, 4.5))
        colors = ['#10B981' if ch >= 0 else '#EF4444' for ch in changes]
        
        bars = plt.bar(names, changes, color=colors, width=0.5)
        plt.axhline(0, color='gray', linewidth=0.8, linestyle='--')
        plt.title('Cryptoscout06_ | Top 5 Assets 24h Price Change (%)', fontsize=12, fontweight='bold', color='#1F2937')
        plt.ylabel('24h Change (%)', fontsize=10)
        plt.grid(axis='y', linestyle=':', alpha=0.5)
        
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval + (0.5 if yval >= 0 else -1.5), f"{yval:.2f}%", ha='center', fontsize=9, fontweight='bold')

        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        logger.error(f"Error creating chart image: {e}")
        return None

async def post_market_update():
    """Fetches data, creates image, and broadcasts update to Telegram channel."""
    logger.info("Preparing scheduled crypto market update...")
    top_coins, trending_coins = fetch_crypto_data()
    
    if not top_coins:
        logger.warning("Skipping broadcast due to empty market data.")
        return

    ai_text = generate_ai_commentary(top_coins)
    
    trend_str = ", ".join(trending_coins) if trending_coins else "Bitcoin, Ethereum, Solana"
    
    message = (
        "🚀 **Cryptoscout06_ | Live Market Update** 🚀\n\n"
        f"{ai_text}\n\n"
        f"🔥 **Trending Searches:** {trend_str}\n\n"
        "💡 *Disclaimer: Not financial advice. Always do your own research.*\n"
        "🤖 _Powered by Cryptoscout06_Bot_"
    )
    
    photo_buffer = create_crypto_chart(top_coins)
    
    try:
        if photo_buffer:
            await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_buffer,
                caption=message,
                parse_mode="Markdown"
            )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode="Markdown"
            )
        logger.info("Successfully posted update to channel!")
    except Exception as e:
        logger.error(f"Failed to send message to channel: {e}")

async def scheduler_loop():
    """Runs the posting loop every 30 minutes."""
    # Wait 10 seconds on startup before first post
    await asyncio.sleep(10)
    while True:
        try:
            await post_market_update()
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
        
        # 30 minutes = 1800 seconds
        await asyncio.sleep(1800)

if __name__ == "__main__":
    logger.info("Starting Cryptoscout06_Bot Scheduler...")
    asyncio.run(scheduler_loop())
