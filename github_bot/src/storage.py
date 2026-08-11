import sqlite3
import os
import csv
import datetime
from src.logger import get_logger

logger = get_logger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'leads.db')

def _get_connection():
    """Returns a new SQLite connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    """Create tables if not exist, create data/ dir."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_found TEXT NOT NULL,
            business_name TEXT,
            website TEXT UNIQUE NOT NULL,
            emails TEXT,
            verified_emails TEXT,
            phone TEXT,
            country TEXT,
            screenshot_path TEXT,
            email_verification_status TEXT DEFAULT 'unverified',
            status TEXT DEFAULT 'new',
            emailed_at TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_sends (
            date TEXT UNIQUE NOT NULL,
            count INTEGER DEFAULT 0
        )
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
    finally:
        conn.close()

def add_lead(business_name: str, website: str, emails: str, phone: str, country: str, verified_emails: str = None, verification_status: str = 'unverified') -> bool:
    """Returns False if website already exists (dedup)."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        date_found = datetime.date.today().isoformat()
        
        cursor.execute('''
        INSERT INTO leads (date_found, business_name, website, emails, phone, country, verified_emails, email_verification_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date_found, business_name, website, emails, phone, country, verified_emails, verification_status))
        
        conn.commit()
        logger.debug(f"Added lead: {business_name} ({website})")
        return True
    except sqlite3.IntegrityError:
        logger.debug(f"Lead with website {website} already exists. Skipping.")
        return False
    except Exception as e:
        logger.error(f"Error adding lead {website}: {e}")
        return False
    finally:
        conn.close()

def update_verification(website: str, verified_emails: str, verification_status: str):
    """Update after verification."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE leads 
        SET verified_emails = ?, email_verification_status = ?
        WHERE website = ?
        ''', (verified_emails, verification_status, website))
        conn.commit()
        logger.debug(f"Updated verification for {website}")
    except Exception as e:
        logger.error(f"Error updating verification for {website}: {e}")
    finally:
        conn.close()

def mark_emailed(website: str):
    """Set status='emailed', emailed_at=now."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        emailed_at = datetime.datetime.now().isoformat()
        cursor.execute('''
        UPDATE leads 
        SET status = 'emailed', emailed_at = ?
        WHERE website = ?
        ''', (emailed_at, website))
        conn.commit()
        logger.debug(f"Marked {website} as emailed")
    except Exception as e:
        logger.error(f"Error marking {website} as emailed: {e}")
    finally:
        conn.close()

def mark_failed(website: str):
    """Set status='failed'."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE leads 
        SET status = 'failed'
        WHERE website = ?
        ''', (website,))
        conn.commit()
        logger.debug(f"Marked {website} as failed")
    except Exception as e:
        logger.error(f"Error marking {website} as failed: {e}")
    finally:
        conn.close()

def _dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_unsent_leads() -> list[dict]:
    """WHERE status='new' AND email_verification_status IN ('valid', 'catch_all') AND verified_emails IS NOT NULL AND verified_emails != ''"""
    conn = _get_connection()
    conn.row_factory = _dict_factory
    try:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM leads 
        WHERE status = 'new' 
        AND email_verification_status IN ('valid', 'catch_all')
        AND verified_emails IS NOT NULL 
        AND verified_emails != ''
        ''')
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching unsent leads: {e}")
        return []
    finally:
        conn.close()

def get_unverified_leads() -> list[dict]:
    """WHERE email_verification_status = 'unverified'"""
    conn = _get_connection()
    conn.row_factory = _dict_factory
    try:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM leads 
        WHERE email_verification_status = 'unverified'
        ''')
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching unverified leads: {e}")
        return []
    finally:
        conn.close()

def get_all_leads() -> list[dict]:
    """Get all leads."""
    conn = _get_connection()
    conn.row_factory = _dict_factory
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM leads')
        return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error fetching all leads: {e}")
        return []
    finally:
        conn.close()

def get_today_send_count() -> int:
    """From daily_sends table for today's date."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        today = datetime.date.today().isoformat()
        cursor.execute('SELECT count FROM daily_sends WHERE date = ?', (today,))
        row = cursor.fetchone()
        if row:
            return row[0]
        return 0
    except Exception as e:
        logger.error(f"Error fetching today send count: {e}")
        return 0
    finally:
        conn.close()

def increment_send_count():
    """Upsert today's count."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        today = datetime.date.today().isoformat()
        
        cursor.execute('SELECT count FROM daily_sends WHERE date = ?', (today,))
        row = cursor.fetchone()
        
        if row:
            cursor.execute('UPDATE daily_sends SET count = count + 1 WHERE date = ?', (today,))
        else:
            cursor.execute('INSERT INTO daily_sends (date, count) VALUES (?, 1)', (today,))
            
        conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing send count: {e}")
    finally:
        conn.close()

def export_csv(filepath='data/results.csv'):
    """Write all leads to CSV."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM leads')
        rows = cursor.fetchall()
        
        full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Business Name', 'Website', 'Emails', 'Verified Emails', 'Verification Status', 'Phone', 'Country', 'Status'])
            
            for row in rows:
                writer.writerow([
                    row['date_found'],
                    row['business_name'],
                    row['website'],
                    row['emails'],
                    row['verified_emails'],
                    row['email_verification_status'],
                    row['phone'],
                    row['country'],
                    row['status']
                ])
        logger.info(f"Successfully exported leads to {filepath}")
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
    finally:
        conn.close()
