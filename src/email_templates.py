import random

SUBJECTS = [
    "Important: A guaranteed way to scale {{business_name}}'s revenue",
    "Private guide: Scaling {{business_name}}'s {{niche}} leads",
    "How we helped scale a {{niche}} company (Guide inside)",
    "For {{business_name}}: Your step-by-step lead generation guide",
    "Quick question about {{business_name}}'s growth",
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
    <p>I was doing some research on {{niche}} businesses in the area and came across your site. Are you currently doing manual outreach to find new clients?</p>
    <p>I built a lightweight tool that automatically finds and verifies 500+ contact emails for any city in minutes, so you don't have to waste time doing it by hand.</p>
    <p>If you're open to saving some time, just reply to this email and I'll send you a quick demo video.</p>
    <div class="signature"><p>Best,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 2
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hey {{business_name}} team,</p>
    <p>Quick question — how are you currently sourcing your {{niche}} leads?</p>
    <p>Most people I talk to are paying expensive monthly subscriptions for lead databases. I actually built a software that scrapes and verifies hundreds of local businesses directly from the web for a one-time fee of €25.</p>
    <p>Would it be helpful if I sent over a link so you can check it out?</p>
    <div class="signature"><p>Cheers,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 3
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hi there,</p>
    <p>I know things are probably busy at {{business_name}}, so I'll keep this short.</p>
    <p>If your team spends hours manually searching for {{niche}} clients, you might like a desktop tool I recently put together. It automatically builds spreadsheets of verified local leads in about 5 minutes.</p>
    <p>Let me know if you want me to send over the details.</p>
    <div class="signature"><p>Thanks,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 4
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hi {{business_name}} team,</p>
    <p>I noticed you're operating in the {{niche}} space and wanted to reach out.</p>
    <p>I've developed a lead generation software that bypasses the expensive monthly databases by scraping and verifying contacts in real-time. It's just a flat €25 once.</p>
    <p>Are you open to a quick chat to see if it would save you time?</p>
    <div class="signature"><p>Regards,<br>{{sender_name}}</p></div>
    </body></html>""",

    # Template 5
    """<!DOCTYPE html><html><head><meta charset="UTF-8">""" + BASE_STYLE + """</head><body>
    <p>Hey,</p>
    <p>Are you overpaying for {{niche}} lead lists?</p>
    <p>I found a way for {{business_name}} to completely automate prospecting without paying per-lead. I built a tool that scrapes, verifies, and emails contacts for a single one-time payment.</p>
    <p>Reply back if you're interested and I'll share the info.</p>
    <div class="signature"><p>Best,<br>{{sender_name}}</p></div>
    </body></html>"""
]

def get_random_subject(business_name: str, niche: str) -> str:
    sub = random.choice(SUBJECTS)
    sub = sub.replace("{{business_name}}", business_name)
    sub = sub.replace("{{niche}}", niche)
    return sub

def get_random_template() -> str:
    return random.choice(TEMPLATES)
