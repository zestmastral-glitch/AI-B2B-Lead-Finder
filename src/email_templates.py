import random

SUBJECTS = [
    "Quick question about {{business_name}}'s Google Maps leads",
    "Stop paying monthly fees for {{niche}} leads",
    "For {{business_name}}: Unlimited Google Maps scraping (No API)",
    "A better way to get {{niche}} leads (No subscriptions)",
    "Are you overpaying for B2B leads at {{business_name}}?",
]

# Minimalist style to look like a real human typed it in Gmail
BASE_STYLE = """
<style>
  body { font-family: Arial, sans-serif; line-height: 1.5; color: #222222; max-width: 600px; }
  p { margin-bottom: 14px; font-size: 14px; }
  .signature { margin-top: 30px; font-size: 13px; color: #555555; }
</style>
"""

TEMPLATES = [
    # Template 1
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hi {{business_name}} team,</p>
    <p>I was doing some research on {{niche}} businesses in the area and came across your site. Are you currently paying monthly subscriptions to find B2B leads?</p>
    <p>I built the ultimate No-API Google Maps scraper that gives you unlimited, high-quality leads completely free of ongoing API costs. It runs flawlessly on your own machine.</p>
    <p>You can check it out here: <a href="https://automaters.gumroad.com/l/gmapscraper">https://automaters.gumroad.com/l/gmapscraper</a></p>
    <p>Never worry about monthly software limits or API quotas again.</p>
    <div class="signature"><p>Best,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 2
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hey {{business_name}} team,</p>
    <p>Quick question — how are you currently sourcing your {{niche}} leads from Google Maps?</p>
    <p>Most people I talk to are paying expensive monthly subscriptions. We built a solution that lets you scrape unlimited Google Maps data with NO API costs and NO monthly fees.</p>
    <p>Grab it here and stop paying subscriptions: <a href="https://automaters.gumroad.com/l/gmapscraper">https://automaters.gumroad.com/l/gmapscraper</a></p>
    <div class="signature"><p>Cheers,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 3
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hi there,</p>
    <p>I know things are probably busy at {{business_name}}, so I'll keep this short.</p>
    <p>If your team spends hundreds of dollars a month on lead scraping APIs, you might like this tool. It's a completely free-to-run Google Maps scraper with zero monthly subscriptions.</p>
    <p>Check out the No-API Scraper here: <a href="https://automaters.gumroad.com/l/gmapscraper">https://automaters.gumroad.com/l/gmapscraper</a></p>
    <div class="signature"><p>Thanks,<br>{{sender_name}}</p></div>
    </body></html>"""
]

def get_random_subject(business_name: str, niche: str) -> str:
    sub = random.choice(SUBJECTS)
    sub = sub.replace("{{business_name}}", business_name)
    sub = sub.replace("{{niche}}", niche)
    return sub

def get_random_template() -> str:
    return random.choice(TEMPLATES)
