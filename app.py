import os
import sqlite3
import json
from datetime import datetime
from io import BytesIO
from flask import Flask, jsonify, render_template, send_file, request

# ReportLab imports for generating professional PDFs
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, Circle, String

app = Flask(__name__)
DB_NAME = "phishguard.db"

# --- INTERACTIVE GAME SCENARIOS ---

LINK_DETECTIVE_SCENARIOS = [
    {
        "id": "ld_1",
        "indicator": "Fake Domain",
        "scenario": "You receive a text message: 'Security Alert: Someone accessed your account from Dallas, TX. If this wasn't you, verify your account immediately at: http://secure-paypal-login.com/login'",
        "options": [
            {"id": "A", "text": "Safely click the link and verify my account."},
            {"id": "B", "text": "Ignore the link, log in directly via the official Paypal app/website to check for alerts."},
            {"id": "C", "text": "Reply to the message asking for more details."},
            {"id": "D", "text": "Call the number that sent the text message."}
        ],
        "correct": "B",
        "concept": "Checking official apps or websites directly is the safest way to verify account security alerts. Never trust URLs sent in unsolicited text messages.",
        "feedback": {
            "A": "Incorrect. 'secure-paypal-login.com' is a fake domain. The official PayPal domain is 'paypal.com'. Clicking this link will take you to a credential harvesting page designed to steal your password.",
            "B": "Correct! Accessing your account directly through the official website or app is the safest way to check and verify alerts, completely avoiding any phishing risk.",
            "C": "Incorrect. Replying confirms to the scammers that your phone number is active and monitored, which will lead to a flood of more targeted scams in the future.",
            "D": "Incorrect. The sender's number could be spoofed or belong directly to the scammers, who will impersonate support agents to trick you over the phone."
        }
    },
    {
        "id": "ld_2",
        "indicator": "Misspelled Domain (Typosquatting)",
        "scenario": "Netflix Subscription Expired! Update your payment method to avoid service interruption: https://www.neflix-billing.support/renew",
        "options": [
            {"id": "A", "text": "It's safe since it uses HTTPS (the lock icon is present)."},
            {"id": "B", "text": "It's safe because it starts with 'www.neflix' which is Netflix."},
            {"id": "C", "text": "It's unsafe because 'neflix' is misspelled (missing 't') and the domain is 'neflix-billing.support', not 'netflix.com'."},
            {"id": "D", "text": "It's safe because it contains the word 'billing'."}
        ],
        "correct": "C",
        "concept": "Always check the spelling of the domain name carefully. Attackers use lookalike domains (typosquatting) to impersonate trusted brands.",
        "feedback": {
            "A": "Incorrect. HTTPS only encrypts the traffic between you and the site; it does NOT guarantee that the site is legitimate. Scammers frequently buy free SSL certificates.",
            "B": "Incorrect. Typosquatting relies on users scanning the URL quickly and missing small typos like 'neflix' instead of 'netflix'.",
            "C": "Correct! The domain is misspelled (missing the letter 't' in Netflix) and points to 'neflix-billing.support' instead of Netflix's official website 'netflix.com'.",
            "D": "Incorrect. Words like 'billing' or 'support' are used in domains by scammers to build false trust."
        }
    },
    {
        "id": "ld_3",
        "indicator": "Suspicious Subdomain",
        "scenario": "Microsoft Support: Your Windows Defender license has expired. Renew now: http://microsoft.com.security-update-service.info/renew.php",
        "options": [
            {"id": "A", "text": "Safe because the main domain starts with microsoft.com."},
            {"id": "B", "text": "Unsafe because the actual domain is 'security-update-service.info', not 'microsoft.com'."},
            {"id": "C", "text": "Safe because it's a Microsoft security update file (renew.php)."},
            {"id": "D", "text": "Safe because Windows Defender is a Microsoft product."}
        ],
        "correct": "B",
        "concept": "URL subdomains are read from right to left before the forward slash. The actual domain is the text immediately before the last dot and suffix.",
        "feedback": {
            "A": "Incorrect. The presence of 'microsoft.com' at the beginning is just a subdomain of 'security-update-service.info', designed to trick you.",
            "B": "Correct! The true domain is 'security-update-service.info' (the part right before the last extension '.info'). Microsoft has no association with this domain.",
            "C": "Incorrect. Files like 'renew.php' can be named anything and hosted on any malicious server.",
            "D": "Incorrect. Scammers impersonate popular products to create a false sense of urgency and legitimacy."
        }
    },
    {
        "id": "ld_4",
        "indicator": "Misleading URL (Open Redirect)",
        "scenario": "Google Docs: You received a shared document from HR. Click to open: https://www.google.com/url?q=http://maliciousphishingsite.xyz/login",
        "options": [
            {"id": "A", "text": "Safe because the host is google.com."},
            {"id": "B", "text": "Safe because Google automatically checks all shared documents."},
            {"id": "C", "text": "Unsafe because it uses an open redirect parameter to send users to 'maliciousphishingsite.xyz'."},
            {"id": "D", "text": "Safe because the link is hosted on a secure Google Server."}
        ],
        "correct": "C",
        "concept": "Scammers exploit open redirectors on legitimate sites (like Google or tracking URLs) to send victims to malicious websites while appearing trusted.",
        "feedback": {
            "A": "Incorrect. Although it begins with 'google.com', the redirect parameter '?q=' tells the server to forward you to an external site.",
            "B": "Incorrect. Google does not block redirect links automatically if they are clicked from external platforms.",
            "C": "Correct! This URL uses a redirect parameter to redirect the user to 'maliciousphishingsite.xyz', which is a dangerous credential harvester.",
            "D": "Incorrect. The redirection mechanism is on a Google server, but the final destination is malicious."
        }
    },
    {
        "id": "ld_5",
        "indicator": "Shortened Link",
        "scenario": "FEDEX: Your parcel is on hold due to incorrect address details. Update here: https://bit.ly/3xY7zKq",
        "options": [
            {"id": "A", "text": "Safe because bit.ly is a trusted URL shortening service."},
            {"id": "B", "text": "Safe because major delivery companies use shortened URLs to save space."},
            {"id": "C", "text": "Unsafe because URL shorteners hide the real destination. You should expand the link using a checker or verify via your tracking ID directly."},
            {"id": "D", "text": "Safe because it uses HTTPS."}
        ],
        "correct": "C",
        "concept": "URL shorteners mask the actual destination domain. Always expand shortened links or check your order status on the official website.",
        "feedback": {
            "A": "Incorrect. Anyone can sign up for free on bit.ly and create a shortened link leading to any malicious page.",
            "B": "Incorrect. Official delivery notifications contain tracking numbers and direct links to their official domains (e.g. fedex.com).",
            "C": "Correct! Scammers use shortened URLs to hide malicious domain names. It is best to expand the URL using an online link checker or track it directly on the official site.",
            "D": "Incorrect. HTTPS does not protect you if the destination is a scam site designed to steal your credentials."
        }
    },
    {
        "id": "ld_6",
        "indicator": "Fake Login Pages",
        "scenario": "Facebook Security: Unusual login attempt detected. Log in to approve or reject this login: https://facebook.accounts-verify.com/login.html",
        "options": [
            {"id": "A", "text": "Safe because the word 'facebook' is present in the URL."},
            {"id": "B", "text": "Safe because it ends with 'login.html' which is standard."},
            {"id": "C", "text": "Unsafe because the official Facebook login is on facebook.com and 'accounts-verify.com' is a third-party domain."},
            {"id": "D", "text": "Safe because Facebook accounts require verification."}
        ],
        "correct": "C",
        "concept": "Legitimate login forms are always hosted on the official brand's primary domain. Check the address bar before typing passwords.",
        "feedback": {
            "A": "Incorrect. Scammers put 'facebook' as a subdomain to make it look legitimate, but the actual domain is 'accounts-verify.com'.",
            "B": "Incorrect. Any developer or scammer can name their page 'login.html'.",
            "C": "Correct! The true domain is 'accounts-verify.com'. Typing your Facebook credentials here will immediately send them to the attacker.",
            "D": "Incorrect. Official notifications should be accessed via your native app or by entering the official website URL directly in a browser tab."
        }
    },
    {
        "id": "ld_7",
        "indicator": "Impersonation Website",
        "scenario": "Apple ID: Your Apple Pay has been suspended. Please update your billing details at: https://appleid.apple.com-payment-authorization.support/",
        "options": [
            {"id": "A", "text": "Safe because it starts with appleid.apple.com."},
            {"id": "B", "text": "Unsafe because the actual domain is 'com-payment-authorization.support', which is not owned by Apple."},
            {"id": "C", "text": "Safe because it ends with a slash."},
            {"id": "D", "text": "Safe because Apple Pay requires authorization."}
        ],
        "correct": "B",
        "concept": "Scammers use hyphens to make subdomains look like a single string. Check the domain extension to see where the server is registered.",
        "feedback": {
            "A": "Incorrect. Scammers added a hyphen after 'com' to fool you. In 'apple.com-payment-authorization.support', 'apple' is not the main domain.",
            "B": "Correct! The primary domain is 'com-payment-authorization.support', which is an attacker-controlled website designed to steal Apple ID credentials.",
            "C": "Incorrect. A trailing slash has no impact on safety.",
            "D": "Incorrect. Apple does not send links to resolve Apple Pay suspensions in this manner."
        }
    },
    {
        "id": "ld_8",
        "indicator": "Official vs Fake Website/App",
        "scenario": "Chase Bank: Urgently review your statement for unauthorized charge of $1,200.00: https://chase.com.statement-review.net/login",
        "options": [
            {"id": "A", "text": "Safe because Chase is a well-known bank and the URL contains 'chase.com'."},
            {"id": "B", "text": "Unsafe because the URL points to 'statement-review.net', not 'chase.com'."},
            {"id": "C", "text": "Safe because it starts with https://chase.com."},
            {"id": "D", "text": "Safe because banks always send statements."}
        ],
        "correct": "B",
        "concept": "Look closely at the dot after 'com'. If a dot separates 'com' and the next word, 'com' is part of a subdomain, not the top-level domain.",
        "feedback": {
            "A": "Incorrect. The URL has 'chase.com.' which makes it a subdomain. The actual domain is 'statement-review.net'.",
            "B": "Correct! The main domain is 'statement-review.net', which is unaffiliated with Chase Bank.",
            "C": "Incorrect. It starts with 'https://chase.com', but the period that follows makes it a subdomain of 'statement-review.net'.",
            "D": "Incorrect. Banks send statements but do not host login portals on external domains like 'statement-review.net'."
        }
    }
]

SCAM_RESPONSE_SCENARIOS = [
    {
        "id": "sr_1",
        "indicator": "Fake Bank Message",
        "scenario": "You receive a text message from a 10-digit mobile number claiming to be Chase Bank: 'Alert: Your card has been temporarily locked due to suspicious activity. Click here to reactivate: secure-link.net/chase'. What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Click the link and enter your card details to unlock it."},
            {"id": "B", "text": "Reply to the text message asking for verification."},
            {"id": "C", "text": "Delete the text message and do not click the link."},
            {"id": "D", "text": "Log in to your Chase app or call the official customer support number on the back of your physical credit card."}
        ],
        "correct": ["C", "D"],
        "concept": "Banks will never send links from standard mobile numbers to unlock cards. Only communicate via official channels.",
        "feedback": {
            "A": "Unsafe Action! Clicking and entering details gives attackers full access to your bank card.",
            "B": "Unsafe Action! Replying validates your phone number, which will invite more spam and phishing messages.",
            "C": "Safe Action! Deleting the text avoids future accidental clicks.",
            "D": "Safe Action! Calling the number on your card or logging into the official app guarantees you speak with the actual bank."
        }
    },
    {
        "id": "sr_2",
        "indicator": "OTP Request",
        "scenario": "You receive a phone call from someone claiming to be from your bank's fraud department. They say: 'We detected a suspicious transaction on your account. I've sent a 6-digit verification code to your phone. Please read it to me so we can block the transaction.' What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Give them the code quickly to prevent fraud."},
            {"id": "B", "text": "Refuse to give the code, hang up, and call the bank's official customer support number."},
            {"id": "C", "text": "Read the text message containing the code and check if it warns 'Do not share this code with anyone'."},
            {"id": "D", "text": "Ask the caller to verify their employee ID first, then give them the code."}
        ],
        "correct": ["B", "C"],
        "concept": "One-Time Passwords (OTPs) are private authorization tokens. Legitimate organizations will never call you to ask for your OTP.",
        "feedback": {
            "A": "Unsafe Action! Sharing an OTP allows the attacker to transfer money or reset your credentials.",
            "B": "Safe Action! Hanging up and calling back through verified numbers is the most secure response.",
            "C": "Safe Action! Reading the alert text will show you what action the code is authorizing (e.g. transfer of funds).",
            "D": "Unsafe Action! Scammers easily make up fake employee IDs to sound authoritative."
        }
    },
    {
        "id": "sr_3",
        "indicator": "Delivery Scam",
        "scenario": "You receive an email: 'UPS Delivery Alert: Your package could not be delivered due to an outstanding fee of $2.50. Click here to pay and reschedule delivery.' You aren't expecting a package. What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Pay the $2.50 fee because it's a small amount and you might have forgotten a package."},
            {"id": "B", "text": "Forward the email to the official UPS phishing reporting address (phish@ups.com) and delete it."},
            {"id": "C", "text": "Check the sender's email address closely (e.g., ups-support@gmail.com)."},
            {"id": "D", "text": "Click the link to see what the package contains."}
        ],
        "correct": ["B", "C"],
        "concept": "Scammers charge small fees to extract credit card data. UPS sends alerts from official domains and never requests payments to release packages.",
        "feedback": {
            "A": "Unsafe Action! The small fee is a lure. Scammers will clone your credit card details once you enter them.",
            "B": "Safe Action! Forwarding reports the threat, and deleting it mitigates the risk.",
            "C": "Safe Action! Checking the sender's address reveals it's from a free Gmail account rather than ups.com.",
            "D": "Unsafe Action! Clicking the link takes you to a fake payment gateway."
        }
    },
    {
        "id": "sr_4",
        "indicator": "WhatsApp Impersonation",
        "scenario": "You receive a WhatsApp message from an unknown number: 'Hi Mom, my phone broke and this is my new temporary number. I urgently need to pay a bill of $450. Can you transfer the money to this account? I will repay you tomorrow.' What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Immediately transfer the money because your child is in trouble."},
            {"id": "B", "text": "Call your child on their regular, known phone number to verify."},
            {"id": "C", "text": "Ask the sender a security question only your real child would know (e.g., 'What is our dog's name?')."},
            {"id": "D", "text": "Send the money but ask for a selfie first."}
        ],
        "correct": ["B", "C"],
        "concept": "Family emergency scams exploit panic. Always verify the identity of the person via a secondary, trusted communication channel.",
        "feedback": {
            "A": "Unsafe Action! Transferring funds immediately without validation leads to irreversible financial loss.",
            "B": "Safe Action! Calling their original number allows you to confirm if their phone is actually broken.",
            "C": "Safe Action! Private questions easily filter out scammers who scrape basic social media info.",
            "D": "Unsafe Action! Scammers can use stolen photos or AI filters to spoof selfies."
        }
    },
    {
        "id": "sr_5",
        "indicator": "Suspicious Attachments",
        "scenario": "You get an email from 'accounting@yourcompany.com' (you work at a small company and don't know this person) with the subject 'Overdue Invoice #89283' and a zip file attachment. What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Download the attachment and extract the files to see if it's for you."},
            {"id": "B", "text": "Delete the email immediately."},
            {"id": "C", "text": "Verify with your manager or IT department before downloading any unexpected invoice attachments."},
            {"id": "D", "text": "Open the attachment in safe mode."}
        ],
        "correct": ["B", "C"],
        "concept": "Unexpected attachments in invoice emails are common malware vectors. Always report and verify through internal IT procedures.",
        "feedback": {
            "A": "Unsafe Action! ZIP and PDF attachments from unknown senders frequently contain Trojans or ransomware.",
            "B": "Safe Action! Deleting the email completely avoids any accidental execution.",
            "C": "Safe Action! Verifying with internal resources guarantees compliance with company cybersecurity policy.",
            "D": "Unsafe Action! Opening unverified attachments on work computers poses a severe threat to the company network."
        }
    },
    {
        "id": "sr_6",
        "indicator": "Fake Prize Messages",
        "scenario": "You receive a text: 'CONGRATULATIONS! You have been selected as the 1st prize winner of a brand new iPad. Claim your prize now at bit.ly/win-ipad within 24 hours!' What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Click the link to claim the prize before the 24-hour limit expires."},
            {"id": "B", "text": "Block the number and report it as spam."},
            {"id": "C", "text": "Ignore and delete the message."},
            {"id": "D", "text": "Text back 'STOP' to opt-out."}
        ],
        "correct": ["B", "C"],
        "concept": "Fake prize scams use artificial urgency and free items to lure you. If you did not enter a raffle, you did not win one.",
        "feedback": {
            "A": "Unsafe Action! The link will prompt you for shipping fees or personal info, leading to identity theft.",
            "B": "Safe Action! Blocking the number prevents them from targeting you again.",
            "C": "Safe Action! Deleting and ignoring is a safe default response to phishing.",
            "D": "Unsafe Action! Replying 'STOP' alerts scammers that your number is active, resulting in more spam calls/messages."
        }
    },
    {
        "id": "sr_7",
        "indicator": "Account Verification Scams",
        "scenario": "You receive an email from 'no-reply@amazon-accounts-support.com' claiming: 'Suspicious activity detected. Your Amazon account has been locked. Verify your identity within 48 hours to avoid permanent suspension.' What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Click the link to verify your identity."},
            {"id": "B", "text": "Open a new browser tab, go directly to amazon.com, and check your account notifications."},
            {"id": "C", "text": "Check the email domain: 'amazon-accounts-support.com' is NOT the official 'amazon.com' domain."},
            {"id": "D", "text": "Call the support number listed in the email footer."}
        ],
        "correct": ["B", "C"],
        "concept": "Urgent security warnings are a common phishing tactic. Always check account status by logging into the official app or website directly.",
        "feedback": {
            "A": "Unsafe Action! The verification link directs you to a credential harvesting site.",
            "B": "Safe Action! Accessing your account via the official site is the only secure way to check alerts.",
            "C": "Safe Action! Senders using lookalike domains (e.g. amazon-accounts-support.com) are phishing.",
            "D": "Unsafe Action! Scammers put their own phone numbers in support footers to scam callers."
        }
    },
    {
        "id": "sr_8",
        "indicator": "Urgent Payment Requests",
        "scenario": "Your supervisor sends you an urgent email from a personal address (e.g., supervisor.companyname@gmail.com): 'I am in a meeting and need you to urgently purchase five $100 Google Play gift cards for a client. Email me the codes as soon as possible.' What should you do? (Select all safe actions)",
        "options": [
            {"id": "A", "text": "Buy the gift cards immediately because your supervisor requested it urgently."},
            {"id": "B", "text": "Call your supervisor or speak to them in person to confirm the request."},
            {"id": "C", "text": "Check with your company's finance department regarding the policy on purchasing gift cards."},
            {"id": "D", "text": "Reply to the email asking for confirmation."}
        ],
        "correct": ["B", "C"],
        "concept": "Scammers pretend to be bosses using personal accounts. Legitimate companies never instruct employees to purchase gift cards for clients.",
        "feedback": {
            "A": "Unsafe Action! Buying gift cards leads to immediate loss of funds, which cannot be refunded.",
            "B": "Safe Action! Verifying via an alternative known channel (like phone call or in person) prevents this scam.",
            "C": "Safe Action! Confirming company policies prevents compliance violations and blocks scam attempts.",
            "D": "Unsafe Action! Replying only connects you back to the scammer who will reassure you."
        }
    }
]

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database schema."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            anonymous_id TEXT NOT NULL UNIQUE
        )
    """)
    
    # 2. Quiz Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            max_score INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # 3. Learning Progress table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            activity_type TEXT NOT NULL, -- 'module', 'video', 'video_quiz'
            category TEXT NOT NULL,
            completed BOOLEAN NOT NULL CHECK (completed IN (0, 1)),
            score INTEGER,
            max_score INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # 4. Game Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            game_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            max_score INTEGER NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            time_taken INTEGER NOT NULL,
            completed_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # 5. Game Answers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            question_id TEXT NOT NULL,
            selected_answer TEXT NOT NULL,
            correct_answer TEXT NOT NULL,
            is_correct BOOLEAN NOT NULL CHECK (is_correct IN (0, 1)),
            FOREIGN KEY (session_id) REFERENCES game_sessions (id)
        )
    """)
    
    # 6. Game Feedback table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            rating INTEGER NOT NULL,
            liked_aspects TEXT,
            explanation_useful TEXT,
            difficulty TEXT,
            suggestions TEXT,
            comments TEXT,
            FOREIGN KEY (session_id) REFERENCES game_sessions (id)
        )
    """)
    
    # 7. User Badges table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            badge_name TEXT NOT NULL,
            earned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, badge_name),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # 8. User Certificates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_certificates (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            score REAL NOT NULL,
            awareness_level TEXT NOT NULL,
            completion_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    conn.commit()
    
    # Seed data if database users are empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        seed_data(conn)
        
    # Seed games data if game_sessions is empty
    cursor.execute("SELECT COUNT(*) FROM game_sessions")
    if cursor.fetchone()[0] == 0:
        seed_game_data(conn)
        
    conn.close()

def seed_data(conn):
    """Seeds the SQLite database with 4 distinct user profiles."""
    cursor = conn.cursor()
    
    users_data = [
        ("Alice Smith", "PG-USR-001"),
        ("Bob Johnson", "PG-USR-002"),
        ("Charlie Brown", "PG-USR-003"),
        ("Diana Prince", "PG-USR-004")
    ]
    
    cursor.executemany("INSERT INTO users (name, anonymous_id) VALUES (?, ?)", users_data)
    conn.commit()
    
    # ---- USER 1: Alice ----
    user1_id = 1
    quiz_results_u1 = [
        (user1_id, "phishing", 9, 10),
        (user1_id, "password_security", 10, 10),
        (user1_id, "malware", 8, 10),
        (user1_id, "social_engineering", 9, 10),
        (user1_id, "otp_scams", 10, 10),
        (user1_id, "suspicious_links", 8, 10)
    ]
    learning_u1 = [
        (user1_id, "module", "phishing", 1, None, None),
        (user1_id, "module", "password_security", 1, None, None),
        (user1_id, "module", "malware", 1, None, None),
        (user1_id, "module", "social_engineering", 1, None, None),
        (user1_id, "module", "otp_scams", 1, None, None),
        (user1_id, "module", "suspicious_links", 1, None, None),
        (user1_id, "video", "phishing", 1, None, None),
        (user1_id, "video", "password_security", 1, None, None),
        (user1_id, "video", "otp_scams", 1, None, None),
        (user1_id, "video_quiz", "phishing", 1, 5, 5),
        (user1_id, "video_quiz", "password_security", 1, 5, 5),
        (user1_id, "video_quiz", "otp_scams", 1, 4, 5)
    ]
    
    # ---- USER 2: Bob ----
    user2_id = 2
    quiz_results_u2 = [
        (user2_id, "phishing", 7, 10),
        (user2_id, "password_security", 8, 10),
        (user2_id, "malware", 6, 10),
        (user2_id, "social_engineering", 7, 10),
        (user2_id, "otp_scams", 6, 10),
        (user2_id, "suspicious_links", 7, 10)
    ]
    learning_u2 = [
        (user2_id, "module", "phishing", 1, None, None),
        (user2_id, "module", "password_security", 1, None, None),
        (user2_id, "module", "malware", 0, None, None),
        (user2_id, "module", "social_engineering", 1, None, None),
        (user2_id, "module", "otp_scams", 1, None, None),
        (user2_id, "module", "suspicious_links", 0, None, None),
        (user2_id, "video", "phishing", 1, None, None),
        (user2_id, "video", "password_security", 1, None, None),
        (user2_id, "video", "otp_scams", 0, None, None),
        (user2_id, "video_quiz", "phishing", 1, 4, 5),
        (user2_id, "video_quiz", "password_security", 1, 3, 5)
    ]
    
    # ---- USER 3: Charlie ----
    user3_id = 3
    quiz_results_u3 = [
        (user3_id, "phishing", 4, 10),
        (user3_id, "password_security", 5, 10),
        (user3_id, "malware", 3, 10),
        (user3_id, "social_engineering", 5, 10),
        (user3_id, "otp_scams", 4, 10),
        (user3_id, "suspicious_links", 3, 10)
    ]
    learning_u3 = [
        (user3_id, "module", "phishing", 1, None, None),
        (user3_id, "module", "password_security", 0, None, None),
        (user3_id, "module", "malware", 0, None, None),
        (user3_id, "module", "social_engineering", 0, None, None),
        (user3_id, "module", "otp_scams", 0, None, None),
        (user3_id, "module", "suspicious_links", 0, None, None)
    ]
    
    # ---- USER 4: Diana (New) ----
    user4_id = 4
    quiz_results_u4 = [
        (user4_id, "phishing", 8, 10)
    ]
    learning_u4 = [
        (user4_id, "module", "phishing", 1, None, None),
        (user4_id, "video", "phishing", 1, None, None),
        (user4_id, "video_quiz", "phishing", 1, 4, 5)
    ]
    
    cursor.execute("SELECT COUNT(*) FROM quiz_results")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO quiz_results (user_id, category, score, max_score)
            VALUES (?, ?, ?, ?)
        """, quiz_results_u1 + quiz_results_u2 + quiz_results_u3 + quiz_results_u4)
        
    cursor.execute("SELECT COUNT(*) FROM learning_progress")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
            INSERT INTO learning_progress (user_id, activity_type, category, completed, score, max_score)
            VALUES (?, ?, ?, ?, ?, ?)
        """, learning_u1 + learning_u2 + learning_u3 + learning_u4)
        
    conn.commit()

def seed_game_data(conn):
    """Seeds the database with game sessions and badges for Alice, Bob, and Charlie."""
    cursor = conn.cursor()
    
    # --- ALICE SMITH (user_id=1): Perfect score on both games ---
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (1, 'link_detective', 8, 8, 100.0, 'A+', 120)
    """)
    ld_session_alice = cursor.lastrowid
    
    ld_answers_alice = [
        (ld_session_alice, "ld_1", "B", "B", 1),
        (ld_session_alice, "ld_2", "C", "C", 1),
        (ld_session_alice, "ld_3", "B", "B", 1),
        (ld_session_alice, "ld_4", "C", "C", 1),
        (ld_session_alice, "ld_5", "C", "C", 1),
        (ld_session_alice, "ld_6", "C", "C", 1),
        (ld_session_alice, "ld_7", "B", "B", 1),
        (ld_session_alice, "ld_8", "B", "B", 1)
    ]
    cursor.executemany("""
        INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
        VALUES (?, ?, ?, ?, ?)
    """, ld_answers_alice)
    
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (1, 'scam_response', 8, 8, 100.0, 'A+', 150)
    """)
    sr_session_alice = cursor.lastrowid
    
    sr_answers_alice = [
        (sr_session_alice, "sr_1", json.dumps(["C", "D"]), json.dumps(["C", "D"]), 1),
        (sr_session_alice, "sr_2", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_3", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_4", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_5", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_6", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_7", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_alice, "sr_8", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1)
    ]
    cursor.executemany("""
        INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
        VALUES (?, ?, ?, ?, ?)
    """, sr_answers_alice)
    
    cursor.execute("""
        INSERT INTO game_feedback (session_id, rating, liked_aspects, explanation_useful, difficulty, suggestions, comments)
        VALUES (?, 5, 'The interactive scenarios were great!', 'Yes, extremely detailed', 'Average', 'None', 'Outstanding certificate feature')
    """, (ld_session_alice,))
    
    alice_badges = [
        (1, "cyber_detective"),
        (1, "scam_defender"),
        (1, "link_inspector"),
        (1, "threat_spotter"),
        (1, "cyber_champion"),
        (1, "security_expert")
    ]
    cursor.executemany("INSERT OR IGNORE INTO user_badges (user_id, badge_name) VALUES (?, ?)", alice_badges)
    
    cursor.execute("""
        INSERT OR IGNORE INTO user_certificates (id, user_id, score, awareness_level)
        VALUES ('PG-CERT-001', 1, 100.0, 'Cybersecurity Expert')
    """)
    
    # --- BOB JOHNSON (user_id=2): Moderate scores ---
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (2, 'link_detective', 6, 8, 75.0, 'B', 180)
    """)
    ld_session_bob = cursor.lastrowid
    
    ld_answers_bob = [
        (ld_session_bob, "ld_1", "A", "B", 0),
        (ld_session_bob, "ld_2", "A", "C", 0),
        (ld_session_bob, "ld_3", "B", "B", 1),
        (ld_session_bob, "ld_4", "C", "C", 1),
        (ld_session_bob, "ld_5", "C", "C", 1),
        (ld_session_bob, "ld_6", "C", "C", 1),
        (ld_session_bob, "ld_7", "B", "B", 1),
        (ld_session_bob, "ld_8", "B", "B", 1)
    ]
    cursor.executemany("""
        INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
        VALUES (?, ?, ?, ?, ?)
    """, ld_answers_bob)
    
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (2, 'scam_response', 5, 8, 62.5, 'C', 200)
    """)
    sr_session_bob = cursor.lastrowid
    
    sr_answers_bob = [
        (sr_session_bob, "sr_1", json.dumps(["C", "D"]), json.dumps(["C", "D"]), 1),
        (sr_session_bob, "sr_2", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_bob, "sr_3", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_bob, "sr_4", json.dumps(["A"]), json.dumps(["B", "C"]), 0),
        (sr_session_bob, "sr_5", json.dumps(["A"]), json.dumps(["B", "C"]), 0),
        (sr_session_bob, "sr_6", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_bob, "sr_7", json.dumps(["B", "C"]), json.dumps(["B", "C"]), 1),
        (sr_session_bob, "sr_8", json.dumps(["A"]), json.dumps(["B", "C"]), 0)
    ]
    cursor.executemany("""
        INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
        VALUES (?, ?, ?, ?, ?)
    """, sr_answers_bob)
    
    bob_badges = [
        (2, "cyber_detective"),
        (2, "scam_defender")
    ]
    cursor.executemany("INSERT OR IGNORE INTO user_badges (user_id, badge_name) VALUES (?, ?)", bob_badges)
    
    cursor.execute("""
        INSERT OR IGNORE INTO user_certificates (id, user_id, score, awareness_level)
        VALUES ('PG-CERT-002', 2, 68.75, 'Cybersecurity Defender')
    """)
    
    # --- CHARLIE BROWN (user_id=3): Link Detective only ---
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (3, 'link_detective', 3, 8, 37.5, 'F', 240)
    """)
    ld_session_charlie = cursor.lastrowid
    
    ld_answers_charlie = [
        (ld_session_charlie, "ld_1", "A", "B", 0),
        (ld_session_charlie, "ld_2", "A", "C", 0),
        (ld_session_charlie, "ld_3", "A", "B", 0),
        (ld_session_charlie, "ld_4", "A", "C", 0),
        (ld_session_charlie, "ld_5", "A", "C", 0),
        (ld_session_charlie, "ld_6", "C", "C", 1),
        (ld_session_charlie, "ld_7", "B", "B", 1),
        (ld_session_charlie, "ld_8", "B", "B", 1)
    ]
    cursor.executemany("""
        INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
        VALUES (?, ?, ?, ?, ?)
    """, ld_answers_charlie)
    
    cursor.execute("INSERT OR IGNORE INTO user_badges (user_id, badge_name) VALUES (3, 'cyber_detective')")
    
    conn.commit()

# --- HELPER FUNCTIONS ---

CATEGORIES_MAP = {
    "phishing": "Phishing",
    "password_security": "Password Security",
    "malware": "Malware",
    "social_engineering": "Social Engineering",
    "otp_scams": "OTP & Scam Awareness",
    "suspicious_links": "Suspicious Links/Attachments"
}

SAFETY_TIPS = {
    "phishing": "Verify the sender's email address and watch for urgent language before responding.",
    "password_security": "Create strong, unique passwords for each account and enable Multi-Factor Authentication (MFA).",
    "malware": "Keep your system and antivirus updated, and never download software from unverified sites.",
    "social_engineering": "Be skeptical of unsolicited requests for private or financial info, even if they seem official.",
    "otp_scams": "Never share One-Time Passwords (OTPs) with anyone. No legitimate organization will ask for them.",
    "suspicious_links": "Verify links by hovering over them, and download attachments only from trusted sources."
}

def check_and_award_badges(conn, user_id):
    """Evaluates user game completions and awards badges dynamically."""
    cursor = conn.cursor()
    cursor.execute("SELECT game_name, percentage FROM game_sessions WHERE user_id = ?", (user_id,))
    sessions = cursor.fetchall()
    
    completed_games = {row["game_name"]: row["percentage"] for row in sessions}
    
    badges_to_award = []
    
    if "link_detective" in completed_games:
        badges_to_award.append("cyber_detective")
        if completed_games["link_detective"] >= 80:
            badges_to_award.append("link_inspector")
            
    if "scam_response" in completed_games:
        badges_to_award.append("scam_defender")
        if completed_games["scam_response"] >= 80:
            badges_to_award.append("threat_spotter")
            
    if "link_detective" in completed_games and "scam_response" in completed_games:
        avg_pct = (completed_games["link_detective"] + completed_games["scam_response"]) / 2
        if avg_pct >= 85:
            badges_to_award.append("cyber_champion")
        if completed_games["link_detective"] >= 90 and completed_games["scam_response"] >= 90:
            badges_to_award.append("security_expert")
            
    for badge in badges_to_award:
        cursor.execute("""
            INSERT OR IGNORE INTO user_badges (user_id, badge_name)
            VALUES (?, ?)
        """, (user_id, badge))
        
    conn.commit()

def calculate_user_points(conn, user_id):
    """Calculates user point totals based on quiz answers, video watching, and game scores."""
    cursor = conn.cursor()
    points = 0
    
    # 1. Quizzes (10 points per correct answer)
    cursor.execute("SELECT score FROM quiz_results WHERE user_id = ?", (user_id,))
    quizzes = cursor.fetchall()
    for q in quizzes:
        points += q["score"] * 10
        
    # 2. Learning progress (20 pts module, 10 pts video, 10 pts/correct video quiz)
    cursor.execute("SELECT activity_type, completed, score FROM learning_progress WHERE user_id = ?", (user_id,))
    progress = cursor.fetchall()
    for p in progress:
        if p["activity_type"] == "module" and p["completed"] == 1:
            points += 20
        elif p["activity_type"] == "video" and p["completed"] == 1:
            points += 10
        elif p["activity_type"] == "video_quiz" and p["completed"] == 1:
            points += (p["score"] or 0) * 10
            
    # 3. Game sessions (10 pts per correct, 50 completion, bonus for accuracy)
    cursor.execute("SELECT game_name, score, percentage FROM game_sessions WHERE user_id = ?", (user_id,))
    game_sessions = cursor.fetchall()
    for gs in game_sessions:
        points += gs["score"] * 10
        points += 50 # Completion bonus
        if gs["percentage"] >= 90:
            points += 50 # Accuracy bonus
        if gs["percentage"] == 100:
            points += 100 # Perfect score bonus
            
    # 4. Badges (30 points per badge)
    cursor.execute("SELECT COUNT(*) FROM user_badges WHERE user_id = ?", (user_id,))
    badge_count = cursor.fetchone()[0]
    points += badge_count * 30
    
    return points

def determine_level(points):
    """Returns level numerical value, level title, progress within level, and points required for next level."""
    if points >= 1500:
        return 5, "Cyber Expert", points - 1500, 999999
    elif points >= 1000:
        return 4, "Security Defender", points - 1000, 500
    elif points >= 600:
        return 3, "Cyber Detective", points - 600, 400
    elif points >= 300:
        return 2, "Cyber Learner", points - 300, 300
    else:
        return 1, "Beginner", points, 300

def get_gamification_profile_db(conn, user_id):
    """Generates user stats for gamification dashboard."""
    points = calculate_user_points(conn, user_id)
    level_num, level_name, level_progress, next_level_points = determine_level(points)
    
    cursor = conn.cursor()
    cursor.execute("SELECT badge_name FROM user_badges WHERE user_id = ?", (user_id,))
    earned_badges = [row["badge_name"] for row in cursor.fetchall()]
    
    all_badges = [
        {"id": "cyber_detective", "name": "Cyber Detective", "icon": "🕵️", "desc": "Complete Link Detective"},
        {"id": "scam_defender", "name": "Scam Defender", "icon": "🛡️", "desc": "Complete Scam Response"},
        {"id": "link_inspector", "name": "Link Inspector", "icon": "🔗", "desc": "Spot links with >=80% accuracy"},
        {"id": "threat_spotter", "name": "Threat Spotter", "icon": "🚨", "desc": "Identify scams with >=80% accuracy"},
        {"id": "cyber_champion", "name": "Cyber Champion", "icon": "🏆", "desc": "Achieve high overall average (>=85%)"},
        {"id": "security_expert", "name": "Security Expert", "icon": "⭐", "desc": "Complete all games with >=90% score"}
    ]
    
    badges_list = []
    for b in all_badges:
        badges_list.append({
            "id": b["id"],
            "name": b["name"],
            "icon": b["icon"],
            "desc": b["desc"],
            "earned": b["id"] in earned_badges
        })
        
    cursor.execute("SELECT DISTINCT game_name FROM game_sessions WHERE user_id = ?", (user_id,))
    completed_games = [row["game_name"] for row in cursor.fetchall()]
    
    return {
        "points": points,
        "level_num": level_num,
        "level_name": level_name,
        "level_progress": level_progress,
        "next_level_points": next_level_points,
        "progress_percent": min(100, round((level_progress / next_level_points) * 100)) if next_level_points > 0 and level_num < 5 else 100,
        "badges": badges_list,
        "completed_games": completed_games,
        "certificate_unlocked": len(completed_games) >= 2
    }

def calculate_grade_info(percentage):
    """Calculates grades, awareness levels, risk levels, and custom notes."""
    if percentage >= 90:
        return "A+", "Excellent", "Low", "Excellent investigation skills! You correctly identified most phishing indicators."
    elif percentage >= 80:
        return "A", "Very Good", "Low", "Great job! You have a high capacity to spot online deception."
    elif percentage >= 70:
        return "B", "Good", "Medium", "Good work! You spotted key indicators, but stay cautious of subtle traps."
    elif percentage >= 60:
        return "C", "Average", "Medium", "Average performance. Be more careful of urgent claims and misspelled URLs."
    elif percentage >= 50:
        return "D", "Needs Improvement", "High", "You need more practice identifying suspicious links and urgent scam messages."
    else:
        return "F", "Requires More Practice", "High", "Vulnerable to security threats! Please review the modules and try again."

def get_overall_report_data(conn, user_id):
    """Aggregates user data across all games to output to overall report dashboard."""
    cursor = conn.cursor()
    cursor.execute("SELECT name, anonymous_id FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        return None
        
    cursor.execute("SELECT game_name, score, max_score, percentage, grade, time_taken, completed_date FROM game_sessions WHERE user_id = ?", (user_id,))
    sessions = cursor.fetchall()
    
    total_games = len(sessions)
    total_questions = sum(row["max_score"] for row in sessions)
    correct_answers = sum(row["score"] for row in sessions)
    overall_percentage = round((correct_answers / total_questions * 100) if total_questions > 0 else 0)
    
    grade, awareness_level, risk_level, feedback_msg = calculate_grade_info(overall_percentage)
    
    strengths = []
    weak_areas = []
    
    completed_games_names = []
    for s in sessions:
        completed_games_names.append(s["game_name"])
        game_label = "Link Detective" if s["game_name"] == "link_detective" else "Scam Response"
        if s["percentage"] >= 80:
            strengths.append(f"{game_label} ({s['percentage']:.0f}% accuracy)")
        else:
            weak_areas.append(f"{game_label} ({s['percentage']:.0f}% accuracy)")
            
    if "link_detective" not in completed_games_names:
        weak_areas.append("Link Detective (Not Attempted)")
    if "scam_response" not in completed_games_names:
        weak_areas.append("Scam Response Challenge (Not Attempted)")
        
    recommended_modules = []
    if "Link Detective" in "".join(weak_areas):
        recommended_modules.append("Suspicious Links/Attachments Module")
        recommended_modules.append("Phishing Identification Module")
    if "Scam Response" in "".join(weak_areas):
        recommended_modules.append("OTP & Scam Awareness Module")
        recommended_modules.append("Social Engineering Module")
        
    if not recommended_modules:
        recommended_modules.append("Advanced Security Operations")
        recommended_modules.append("Corporate Threat Deflection")
        
    tips = []
    if "link_detective" not in completed_games_names or any(s["game_name"] == "link_detective" and s["percentage"] < 80 for s in sessions):
        tips.append("Analyze URL domains right-to-left to spot spoofed subdomains.")
        tips.append("Look closely at spelling in links (e.g., 'neflix' instead of 'netflix').")
    if "scam_response" not in completed_games_names or any(s["game_name"] == "scam_response" and s["percentage"] < 80 for s in sessions):
        tips.append("Hang up on fraud callers and dial your bank's official number directly.")
        tips.append("Never share OTPs (One-Time Passwords) with anyone, under any circumstances.")
        
    if not tips:
        tips.append("Maintain high vigilance and review security standards quarterly.")
        tips.append("Test your skills by attempting the games regularly.")
        
    gamification = get_gamification_profile_db(conn, user_id)
    
    return {
        "user_id": user_id,
        "name": user["name"],
        "anonymous_id": user["anonymous_id"],
        "total_games_completed": total_games,
        "total_questions_attempted": total_questions,
        "overall_score": correct_answers,
        "overall_percentage": overall_percentage,
        "average_accuracy": overall_percentage,
        "grade": grade,
        "awareness_level": awareness_level,
        "risk_level": risk_level,
        "feedback_msg": feedback_msg,
        "points": gamification["points"],
        "level_num": gamification["level_num"],
        "level_name": gamification["level_name"],
        "badges": [b for b in gamification["badges"] if b["earned"]],
        "strengths": strengths if strengths else ["No strong domains yet (earn by scoring >=80% in games)"],
        "weak_areas": weak_areas,
        "recommended_modules": recommended_modules,
        "safety_tips": tips,
        "certificate_unlocked": gamification["certificate_unlocked"]
    }

def analyze_user_data(user_id):
    """Retrieves SQLite records and computes statistics for the main dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None
    
    cursor.execute("SELECT category, score, max_score FROM quiz_results WHERE user_id = ?", (user_id,))
    quizzes = cursor.fetchall()
    
    cursor.execute("SELECT activity_type, category, completed, score, max_score FROM learning_progress WHERE user_id = ?", (user_id,))
    progress = cursor.fetchall()
    
    conn.close()
    
    category_scores = {cat_id: {"name": cat_name, "score": 0, "max_score": 0, "percent": 0, "attempts": 0} 
                       for cat_id, cat_name in CATEGORIES_MAP.items()}
    
    for quiz in quizzes:
        cat = quiz["category"]
        if cat in category_scores:
            category_scores[cat]["score"] += quiz["score"]
            category_scores[cat]["max_score"] += quiz["max_score"]
            category_scores[cat]["attempts"] += 1
            
    for cat, info in category_scores.items():
        if info["attempts"] > 0:
            info["percent"] = round((info["score"] / info["max_score"]) * 100)
            
    total_percentage_sum = sum(info["percent"] for info in category_scores.values())
    overall_percentage = round(total_percentage_sum / len(CATEGORIES_MAP))
    
    total_score = sum(quiz["score"] for quiz in quizzes)
    total_max_score = sum(quiz["max_score"] for quiz in quizzes)
    
    if overall_percentage >= 85:
        awareness_level = "Excellent"
    elif overall_percentage >= 70:
        awareness_level = "Good"
    elif overall_percentage >= 50:
        awareness_level = "Developing"
    else:
        awareness_level = "Beginner"
        
    if overall_percentage >= 80:
        risk_level = "Low"
        risk_emoji = "🟢"
    elif overall_percentage >= 60:
        risk_level = "Medium"
        risk_emoji = "🟡"
    else:
        risk_level = "High"
        risk_emoji = "🔴"
        
    strengths = []
    weak_areas = []
    
    for cat_id, info in category_scores.items():
        if info["percent"] >= 75 and info["attempts"] > 0:
            strengths.append({"category": cat_id, "name": info["name"], "percent": info["percent"]})
        else:
            weak_areas.append({"category": cat_id, "name": info["name"], "percent": info["percent"], "attempted": info["attempts"] > 0})
            
    tips = []
    for wa in weak_areas:
        tips.append(SAFETY_TIPS[wa["category"]])
        
    if not tips:
        tips.append("Excellent job! Continue staying updated on new phishing techniques and digital security trends.")
        tips.append("Maintain high vigilance when accessing accounts from public networks.")
        
    completed_modules = sum(1 for p in progress if p["activity_type"] == "module" and p["completed"] == 1)
    completed_videos = sum(1 for p in progress if p["activity_type"] == "video" and p["completed"] == 1)
    
    video_quizzes = [p for p in progress if p["activity_type"] == "video_quiz"]
    video_quiz_avg = 0
    if video_quizzes:
        video_quiz_avg = round((sum(q["score"] for q in video_quizzes) / sum(q["max_score"] for q in video_quizzes)) * 100)
        
    completed_items = completed_modules + completed_videos
    learning_overall_progress = round((completed_items / 9) * 100)
    
    report_date = datetime.now().strftime("%B %d, %Y")
    
    return {
        "user_id": user["id"],
        "name": user["name"],
        "anonymous_id": user["anonymous_id"],
        "overall_percentage": overall_percentage,
        "total_score": total_score,
        "total_max_score": total_max_score,
        "awareness_level": awareness_level,
        "risk_level": risk_level,
        "risk_emoji": risk_emoji,
        "category_scores": list(category_scores.values()),
        "strengths": strengths,
        "weak_areas": weak_areas,
        "safety_tips": tips[:5],
        "learning_progress": {
            "completed_modules": completed_modules,
            "total_modules": 6,
            "completed_videos": completed_videos,
            "total_videos": 3,
            "video_quiz_avg": video_quiz_avg,
            "overall_progress": learning_overall_progress
        },
        "report_date": report_date
    }

# --- CONTROLLERS / WEB ROUTES ---

@app.route("/")
def index():
    return render_template("report.html")

@app.route("/games")
def games_dashboard():
    return render_template("games.html")

# --- API ENDPOINTS ---

@app.route("/api/users")
def get_users():
    """Returns list of users to populate the Simulator Panel."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, anonymous_id FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@app.route("/api/report-data/<int:user_id>")
def get_report_data(user_id):
    """JSON API to retrieve report details dynamically."""
    data = analyze_user_data(user_id)
    if not data:
        return jsonify({"error": "User not found"}), 404
    return jsonify(data)

@app.route("/api/game-config/<game_name>")
def get_game_config(game_name):
    """API returning the static configurations and scenarios of each game."""
    if game_name == "link_detective":
        safe_scenarios = []
        for s in LINK_DETECTIVE_SCENARIOS:
            safe_scenarios.append({
                "id": s["id"],
                "indicator": s["indicator"],
                "scenario": s["scenario"],
                "options": s["options"]
            })
        return jsonify(safe_scenarios)
    elif game_name == "scam_response":
        safe_scenarios = []
        for s in SCAM_RESPONSE_SCENARIOS:
            safe_scenarios.append({
                "id": s["id"],
                "indicator": s["indicator"],
                "scenario": s["scenario"],
                "options": s["options"]
            })
        return jsonify(safe_scenarios)
    else:
        return jsonify({"error": "Game not found"}), 404

@app.route("/api/submit-game", methods=["POST"])
def submit_game():
    """Submits answers, records session, evaluates scores, awards badges, and returns feedback."""
    req_data = request.json
    if not req_data:
        return jsonify({"error": "Missing payload"}), 400
        
    user_id = req_data.get("user_id")
    game_name = req_data.get("game_name")
    user_answers = req_data.get("answers", {})
    time_taken = req_data.get("time_taken", 60)
    
    if not user_id or not game_name:
        return jsonify({"error": "Missing parameters"}), 400
        
    scenarios = LINK_DETECTIVE_SCENARIOS if game_name == "link_detective" else SCAM_RESPONSE_SCENARIOS
    max_score = len(scenarios)
    score = 0
    detailed_answers = []
    
    for s in scenarios:
        q_id = s["id"]
        user_select = user_answers.get(q_id)
        correct_ans = s["correct"]
        
        is_correct = False
        if isinstance(correct_ans, str):
            is_correct = (user_select == correct_ans)
        elif isinstance(correct_ans, list):
            if isinstance(user_select, list):
                is_correct = (sorted(user_select) == sorted(correct_ans))
            else:
                is_correct = False
                
        if is_correct:
            score += 1
            
        detailed_answers.append({
            "question_id": q_id,
            "scenario": s["scenario"],
            "indicator": s["indicator"],
            "selected": user_select,
            "correct": correct_ans,
            "is_correct": is_correct,
            "options": s["options"],
            "concept": s["concept"],
            "feedback": s["feedback"]
        })
        
    percentage = (score / max_score) * 100
    grade, awareness_level, risk_level, feedback_msg = calculate_grade_info(percentage)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO game_sessions (user_id, game_name, score, max_score, percentage, grade, time_taken)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, game_name, score, max_score, percentage, grade, time_taken))
    
    session_id = cursor.lastrowid
    
    for ans in detailed_answers:
        cursor.execute("""
            INSERT INTO game_answers (session_id, question_id, selected_answer, correct_answer, is_correct)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session_id,
            ans["question_id"],
            json.dumps(ans["selected"]),
            json.dumps(ans["correct"]),
            1 if ans["is_correct"] else 0
        ))
        
    conn.commit()
    check_and_award_badges(conn, user_id)
    
    cursor.execute("SELECT DISTINCT game_name FROM game_sessions WHERE user_id = ?", (user_id,))
    completed_games = [row["game_name"] for row in cursor.fetchall()]
    if len(completed_games) >= 2:
        cursor.execute("SELECT id FROM user_certificates WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            import uuid
            cert_id = f"PG-CERT-{user_id:03d}-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT OR IGNORE INTO user_certificates (id, user_id, score, awareness_level)
                VALUES (?, ?, ?, ?)
            """, (cert_id, user_id, percentage, "Cybersecurity Specialist"))
            conn.commit()
            
    conn.close()
    
    return jsonify({
        "session_id": session_id,
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "grade": grade,
        "awareness_level": awareness_level,
        "risk_level": risk_level,
        "feedback_msg": feedback_msg,
        "time_taken": time_taken,
        "results": detailed_answers
    })

@app.route("/api/submit-feedback", methods=["POST"])
def submit_feedback():
    """Submits user feedback survey for a specific game session."""
    req_data = request.json
    if not req_data:
        return jsonify({"error": "Missing payload"}), 400
        
    session_id = req_data.get("session_id")
    rating = req_data.get("rating")
    liked_aspects = req_data.get("liked_aspects")
    explanation_useful = req_data.get("explanation_useful")
    difficulty = req_data.get("difficulty")
    suggestions = req_data.get("suggestions")
    comments = req_data.get("comments")
    
    if not session_id or rating is None:
        return jsonify({"error": "Missing parameters"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO game_feedback (session_id, rating, liked_aspects, explanation_useful, difficulty, suggestions, comments)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (session_id, rating, liked_aspects, explanation_useful, difficulty, suggestions, comments))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Feedback submitted successfully!"})

@app.route("/api/gamification-data/<int:user_id>")
def get_gamification_data(user_id):
    """Retrieves user points, badges, levels, and completed games."""
    conn = get_db_connection()
    data = get_gamification_profile_db(conn, user_id)
    conn.close()
    return jsonify(data)

@app.route("/api/overall-report/<int:user_id>")
def get_overall_report(user_id):
    """Retrieves aggregated statistics and recommendations for the overall report."""
    conn = get_db_connection()
    data = get_overall_report_data(conn, user_id)
    conn.close()
    if not data:
        return jsonify({"error": "User not found"}), 404
    return jsonify(data)

@app.route("/download-pdf/<int:user_id>")
def download_pdf(user_id):
    """Generates and streams a professional PDF Score Card using ReportLab."""
    data = analyze_user_data(user_id)
    if not data:
        return "User not found", 404
        
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        leftMargin=36, 
        rightMargin=36,
        topMargin=36, 
        bottomMargin=36
    )
    
    NAVY_DARK = colors.HexColor("#0f172a")
    NAVY_CARD = colors.HexColor("#1e293b")
    ACCENT_BLUE = colors.HexColor("#3b82f6")
    TEXT_MUTED = colors.HexColor("#64748b")
    BORDER_LIGHT = colors.HexColor("#cbd5e1")
    
    styles = getSampleStyleSheet()
    
    styles['Normal'].textColor = colors.HexColor("#334155")
    styles['Normal'].fontSize = 9
    styles['Normal'].leading = 12
    
    title_style = ParagraphStyle(
        'PDFTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.white,
        alignment=1,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'PDFSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor("#94a3b8"),
        alignment=1,
        spaceAfter=12
    )
    
    section_title_style = ParagraphStyle(
        'PDFSectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=NAVY_DARK,
        spaceBefore=10,
        spaceAfter=4
    )
    
    card_title_style = ParagraphStyle(
        'PDFCardTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=colors.white,
        alignment=1
    )
    
    story = []
    
    banner_data = [
        [Paragraph("PHISHGUARD AWARENESS SCORECARD", title_style)],
        [Paragraph("Personalized Cybersecurity Assessment & Performance Report", subtitle_style)]
    ]
    banner_table = Table(banner_data, colWidths=[540])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY_DARK),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 16),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 10))
    
    meta_text = f"""
    <b>Report Date:</b> {data['report_date']}<br/>
    <b>User ID:</b> {data['anonymous_id']}<br/>
    <b>Assessment Status:</b> Completed<br/>
    <b>Platform:</b> PhishGuard Awareness System
    """
    
    risk_color_hex = "#15803d" if data['risk_level'] == "Low" else "#a16207" if data['risk_level'] == "Medium" else "#b91c1c"
    
    score_card_content = f"""
    <font size="11"><b>OVERALL AWARENESS</b></font><br/>
    <font size="32" color="white"><b>{data['overall_percentage']}%</b></font><br/>
    <font size="11"><b>Level:</b> {data['awareness_level']}</font><br/>
    <font size="11"><b>Risk:</b> <font color="{risk_color_hex}"><b>{data['risk_level']}</b></font></font>
    """
    
    meta_p = Paragraph(meta_text, styles['Normal'])
    score_p = Paragraph(score_card_content, card_title_style)
    
    info_table_data = [
        [meta_p, score_p]
    ]
    info_table = Table(info_table_data, colWidths=[300, 240])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (1,0), (1,0), NAVY_CARD),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (1,0), (1,0), 2, ACCENT_BLUE),
        ('PADDING', (1,0), (1,0), 12),
        ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (0,0), (0,0), 12),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("Category-wise Cybersecurity Performance", section_title_style))
    
    table_header_style = ParagraphStyle(
        'PDFTableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )
    
    category_rows = [
        [
            Paragraph("Cybersecurity Category", table_header_style), 
            Paragraph("Score (%)", table_header_style), 
            Paragraph("Status", table_header_style)
        ]
    ]
    
    for cat in data["category_scores"]:
        score_val = cat["percent"]
        if score_val >= 80:
            status_text = "<b>Strong</b>"
            status_color_hex = "#15803d"
        elif score_val >= 50:
            status_text = "<b>Developing</b>"
            status_color_hex = "#a16207"
        else:
            status_text = "<b>Critical Need</b>"
            status_color_hex = "#b91c1c"
            
        status_p = Paragraph(f'<font color="{status_color_hex}">{status_text}</font>', styles['Normal'])
        cat_p = Paragraph(f"<b>{cat['name']}</b>", styles['Normal'])
        score_p = Paragraph(f"<b>{score_val}%</b>", styles['Normal'])
        
        category_rows.append([cat_p, score_p, status_p])
        
    category_table = Table(category_rows, colWidths=[280, 110, 150])
    category_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY_DARK),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_LIGHT),
    ]))
    story.append(category_table)
    story.append(Spacer(1, 10))
    
    strengths_html = "<br/>".join([f"• <b>{s['name']}</b> ({s['percent']}%)" for s in data["strengths"]]) if data["strengths"] else "No specific strengths identified yet."
    weak_html = "<br/>".join([f"• <b>{w['name']}</b> ({w['percent']}%)" for w in data["weak_areas"]]) if data["weak_areas"] else "No critical weak areas. Outstanding job!"
    
    strength_box_content = f"""
    <font color="#15803d"><b>STRENGTHS</b></font><br/><br/>
    <font size="8.5">{strengths_html}</font>
    """
    
    weak_box_content = f"""
    <font color="#b91c1c"><b>WEAK AREAS (NEEDS ATTENTION)</b></font><br/><br/>
    <font size="8.5">{weak_html}</font>
    """
    
    strength_p = Paragraph(strength_box_content, styles['Normal'])
    weak_p = Paragraph(weak_box_content, styles['Normal'])
    
    analysis_data = [
        [strength_p, weak_p]
    ]
    
    analysis_table = Table(analysis_data, colWidths=[265, 265])
    analysis_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#f0fdf4")),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#fef2f2")),
        ('BOX', (0,0), (0,0), 1, colors.HexColor("#bbf7d0")),
        ('BOX', (1,0), (1,0), 1, colors.HexColor("#fecaca")),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    
    story.append(analysis_table)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("Personalized Safety Recommendations", section_title_style))
    
    tips_items = []
    for tip in data["safety_tips"]:
        tips_items.append(f"• {tip}")
        
    tips_text = "<br/>".join(tips_items)
    tips_p = Paragraph(f'<font size="8.5">{tips_text}</font>', styles['Normal'])
    
    tips_table = Table([[tips_p]], colWidths=[540])
    tips_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#eff6ff")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#dbeafe")),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(tips_table)
    story.append(Spacer(1, 12))
    
    footer_text = """
    <font color="#64748b" size="7.5">
    This score card is automatically compiled from raw user assessments, interactive simulation metrics, and learning completions in the PhishGuard database. To verify authenticity or review source logs, please reference client database records with anonymized identifier: <b>{anon}</b>.
    </font>
    """.format(anon=data['anonymous_id'])
    
    footer_p = Paragraph(footer_text, styles['Normal'])
    
    divider = Drawing(540, 2)
    divider.add(Rect(0, 0, 540, 1.5, fillColor=ACCENT_BLUE, strokeColor=None))
    
    story.append(divider)
    story.append(Spacer(1, 6))
    story.append(footer_p)
    
    doc.build(story)
    buffer.seek(0)
    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f"PhishGuard_ScoreCard_{data['anonymous_id']}.pdf", 
        mimetype="application/pdf"
    )

@app.route("/download-certificate/<int:user_id>")
def download_certificate(user_id):
    """Generates and streams a professional landscape certificate of Cybersecurity Awareness."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return "User not found", 404
        
    cursor.execute("SELECT DISTINCT game_name FROM game_sessions WHERE user_id = ?", (user_id,))
    completed = [row["game_name"] for row in cursor.fetchall()]
    
    if len(completed) < 2:
        conn.close()
        return "Certificate locked! You must complete both games to generate a certificate.", 403
        
    cursor.execute("SELECT score, max_score, percentage FROM game_sessions WHERE user_id = ?", (user_id,))
    sessions = cursor.fetchall()
    
    total_q = sum(row["max_score"] for row in sessions)
    correct_q = sum(row["score"] for row in sessions)
    avg_percentage = (correct_q / total_q * 100) if total_q > 0 else 0
    
    cursor.execute("SELECT * FROM user_certificates WHERE user_id = ?", (user_id,))
    cert = cursor.fetchone()
    
    if cert:
        cert_id = cert["id"]
        completion_date = datetime.strptime(cert["completion_date"], "%Y-%m-%d %H:%M:%S").strftime("%B %d, %Y") if " " in cert["completion_date"] else cert["completion_date"]
    else:
        import uuid
        cert_id = f"PG-CERT-{user_id:03d}-{uuid.uuid4().hex[:6].upper()}"
        completion_date = datetime.now().strftime("%B %d, %Y")
        
        cursor.execute("""
            INSERT OR IGNORE INTO user_certificates (id, user_id, score, awareness_level)
            VALUES (?, ?, ?, ?)
        """, (cert_id, user_id, avg_percentage, "Specialist"))
        conn.commit()
        
    conn.close()
    
    awareness_lbl = "Cybersecurity Specialist" if avg_percentage >= 90 else "Cybersecurity Defender" if avg_percentage >= 70 else "Cybersecurity Practitioner"
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    NAVY_DARK = colors.HexColor("#090d16")
    GOLD = colors.HexColor("#d4af37")
    WHITE = colors.white
    SLATE = colors.HexColor("#94a3b8")
    
    story = []
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CertTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        textColor=GOLD,
        alignment=1,
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CertSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        textColor=SLATE,
        alignment=1,
        spaceAfter=20
    )
    
    name_style = ParagraphStyle(
        'CertName',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=32,
        textColor=WHITE,
        alignment=1,
        spaceAfter=20
    )
    
    body_style = ParagraphStyle(
        'CertBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor("#cbd5e1"),
        alignment=1,
        spaceAfter=25
    )
    
    meta_style = ParagraphStyle(
        'CertMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=SLATE,
        alignment=1
    )
    
    def draw_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY_DARK)
        canvas.rect(0, 0, 792, 612, fill=1, stroke=0)
        
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(3)
        canvas.rect(27, 27, 738, 558, fill=0, stroke=1)
        
        canvas.setStrokeColor(colors.HexColor("#1e293b"))
        canvas.setLineWidth(1)
        canvas.rect(34, 34, 724, 544, fill=0, stroke=1)
        
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1)
        
        canvas.line(40, 560, 100, 560)
        canvas.line(40, 560, 40, 500)
        
        canvas.line(752, 560, 692, 560)
        canvas.line(752, 560, 752, 500)
        
        canvas.line(40, 52, 100, 52)
        canvas.line(40, 52, 40, 112)
        
        canvas.line(752, 52, 692, 52)
        canvas.line(752, 52, 752, 112)
        
        path = canvas.beginPath()
        path.moveTo(376, 520)
        path.lineTo(416, 520)
        path.lineTo(416, 490)
        path.arcTo(376, 460, 416, 490, 396, 465)
        path.lineTo(376, 490)
        path.close()
        canvas.setFillColor(colors.HexColor("#1e293b"))
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(2)
        canvas.drawPath(path, fill=1, stroke=1)
        
        canvas.setFillColor(GOLD)
        canvas.circle(396, 495, 4, fill=1, stroke=0)
        
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(SLATE)
        canvas.drawCentredString(396, 40, f"Certificate Verification ID: {cert_id}  |  PhishGuard Academic Security Platform")
        
        canvas.restoreState()
        
    story.append(Spacer(1, 100))
    story.append(Paragraph("CERTIFICATE OF CYBERSECURITY AWARENESS", title_style))
    story.append(Paragraph("THIS CERTIFICATE IS PROUDLY PRESENTED TO", subtitle_style))
    story.append(Paragraph(user["name"].upper(), name_style))
    
    desc_text = f"""
    for successfully completing the <b>PhishGuard Social Engineering & Security awareness simulations</b>, 
    demonstrating critical investigative skills in identifying suspicious hyperlinks, lookalike domains, 
    spoofed web pages, and demonstrating correct defense behaviors in the face of urgent, malicious scams.
    """
    story.append(Paragraph(desc_text, body_style))
    
    meta_rows = [
        [
            Paragraph(f"<b>Completion Date:</b> {completion_date}", meta_style),
            Paragraph(f"<b>Average Score:</b> {avg_percentage:.1f}%", meta_style),
            Paragraph(f"<b>Awareness Level:</b> {awareness_lbl}", meta_style)
        ]
    ]
    meta_table = Table(meta_rows, colWidths=[200, 200, 200])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 40))
    
    sig_rows = [
        [
            Paragraph("_____________________________<br/><b>Simulation Director</b><br/><font size='8' color='#64748b'>PhishGuard Security Lab</font>", meta_style),
            Spacer(1, 20),
            Paragraph("_____________________________<br/><b>System Administrator</b><br/><font size='8' color='#64748b'>Academic Evaluation Board</font>", meta_style)
        ]
    ]
    sig_table = Table(sig_rows, colWidths=[250, 100, 250])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(sig_table)
    
    doc.build(story, onFirstPage=draw_bg)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"PhishGuard_Certificate_{user['anonymous_id']}.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
