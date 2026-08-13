import os
import requests
import tweepy
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Load environment variables (These will be pulled securely from GitHub Secrets)
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PROMO_LINK = os.getenv("PROMO_LINK", "https://your-promo-link.com")
HASHTAGS = os.getenv("HASHTAGS", "#SaaS #LeadGeneration #B2B #AI")

def generate_tweet():
    prompt = (
        "You are a savvy tech founder building a B2B Lead Generation AI tool. "
        "Write a short, engaging tweet (max 150 characters) about the power of automated lead generation, finding clients, or cold outreach. "
        "Keep it highly conversational, professional but slightly hyped. Do NOT include any links or hashtags, just the text."
    )

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://github.com/zestmastral-glitch/AI-B2B-Lead-Finder",
            },
            json={
                "model": "liquid/lfm-40b:free", # Using a free model on OpenRouter
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        response.raise_for_status()
        data = response.json()
        tweet_text = data['choices'][0]['message']['content'].strip()
        
        # Remove quotes if the AI accidentally added them
        if tweet_text.startswith('"') and tweet_text.endswith('"'):
            tweet_text = tweet_text[1:-1]
        return tweet_text
    except Exception as e:
        logging.error(f"Error generating tweet from OpenRouter: {e}")
        return None

def main():
    if not all([TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET, OPENROUTER_API_KEY]):
        logging.error("Missing one or more required API keys in environment variables.")
        return

    # Generate tweet
    logging.info("Generating tweet via OpenRouter...")
    base_text = generate_tweet()
    if not base_text:
        logging.error("Failed to generate tweet. Exiting.")
        return
    
    # Construct final tweet with spacing
    final_tweet = f"{base_text}\n\n👉 {PROMO_LINK}\n\n{HASHTAGS}"
    
    # Enforce Twitter limit (280 characters)
    if len(final_tweet) > 280:
        logging.warning("Tweet generated is too long! Truncating base text.")
        available_space = 280 - len(f"\n\n👉 {PROMO_LINK}\n\n{HASHTAGS}") - 3
        base_text = base_text[:available_space] + "..."
        final_tweet = f"{base_text}\n\n👉 {PROMO_LINK}\n\n{HASHTAGS}"
        
    logging.info(f"Final Tweet Content:\n{final_tweet}")

    # Authenticate with Twitter API v2
    try:
        client = tweepy.Client(
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET
        )
        
        logging.info("Posting tweet...")
        response = client.create_tweet(text=final_tweet)
        logging.info(f"Tweet posted successfully! ID: {response.data['id']}")
    except Exception as e:
        logging.error(f"Failed to post tweet: {e}")

if __name__ == "__main__":
    main()
