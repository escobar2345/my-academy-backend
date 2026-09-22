
"""
BOI RSU — AI-Powered Tech Education Platform
=============================================
Features:
- Student registration & enrollment
- Career roadmap generation
- Textbook PDF generation per course
- Quiz generation after every topic
- Live Jitsi class management
- AI voice teaching via Deepgram
- Attendance tracking
- Assignment management
- Daily WhatsApp check-ins & motivation
- Progress tracking & reports
- Certificate generation
- Paystack payment integration

Author: BOI RSU AI System
"""

import os
import sys
import json
import requests
import subprocess
import time
import random
from datetime import datetime, date, timedelta
from pathlib import Path

# PostgreSQL database access (replaces Supabase). pgdb provides a pooled
# psycopg2 connection + the chain-style query client used below (pgdb.py).
try:
    # Make pgdb.py importable no matter how this module was loaded (direct
    # run, api_server import, or the main app's service container).
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here not in sys.path:
        sys.path.insert(0, _here)
    import pgdb as _pgdb
    db = _pgdb.pg
    print("[OK] PostgreSQL database configured: " + _pgdb._mask(_pgdb.DATABASE_URL))
except ImportError:
    db = None
    print("[WARN] pgdb/psycopg2 not available. Install with: pip install psycopg2-binary")

try:
    from fpdf import FPDF
except ImportError:  # pragma: no cover - optional dependency in test environments
    FPDF = None

try:
    import qrcode
except ImportError:  # pragma: no cover - optional dependency in test environments
    qrcode = None

try:
    from roadmap_helper import fetch_roadmap
except Exception:  # pragma: no cover - optional import in dynamic loader contexts
    def fetch_roadmap(_slug):
        return None

try:
    import schedule
except ImportError:  # pragma: no cover - optional dependency in test environments
    schedule = None

try:
    from youtube import get_boi_course_videos
except Exception:  # pragma: no cover - optional integration dependency
    get_boi_course_videos = None

# ============================================================
# CONFIGURATION
# ============================================================

def _load_env_file():
    """
    Load backend/.env (and .env.local) into os.environ at import time.

    Without this, PAYSTACK_SECRET_KEY / DATABASE_URL etc.
    stay empty even though they are filled in inside backend/.env - which
    is exactly why the app kept saying keys were "not configured" right
    after they had been pasted into the file. Only variables that are not
    already set in the real environment are applied (real env wins).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, ".env.local"),
        os.path.join(here, ".env"),
        os.path.abspath(os.path.join(here, "..", "..", ".env")),
        os.path.join(os.getcwd(), ".env.local"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except Exception as e:
            print(f"[WARN] Could not parse env file {path}: {e}")
        break


_load_env_file()

DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
ADMIN_PHONE = os.environ.get("BOIRSU_ADMIN_PHONE", "")
GOOGLE_FORM_URL = os.environ.get("GOOGLE_FORM_URL", "https://forms.google.com")
DEEPGRAM_VOICE = "aura-orion-en"  # Professional male voice

# PostgreSQL database (the old PostgreSQL configuration block is gone).
# DATABASE_URL is read inside pgdb.py from backend/.env or the real
# environment; `db` is the shared chain-style query client from pgdb.

BASE_DIR = Path(os.path.expanduser("~/.openclaw-boirsu/workspace"))
STUDENTS_DIR = BASE_DIR / "students"
COURSES_DIR = BASE_DIR / "courses"
ASSIGNMENTS_DIR = BASE_DIR / "assignments"
CERTS_DIR = BASE_DIR / "certificates"
REPORTS_DIR = BASE_DIR / "reports"
NOTES_DIR = BASE_DIR / "notes"
TEXTBOOKS_DIR = BASE_DIR / "textbooks"
TIMETABLES_DIR = BASE_DIR / "timetables"

for d in [STUDENTS_DIR, COURSES_DIR, ASSIGNMENTS_DIR,
          CERTS_DIR, REPORTS_DIR, NOTES_DIR, TEXTBOOKS_DIR, TIMETABLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# CAREER ROADMAPS
# ============================================================

CAREER_ROADMAPS = {
    "frontend-developer": {
        "title": "Frontend Developer",
        "duration": "6 months",
        "description": "Build beautiful, interactive websites and web apps",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Web Foundations",
                "topics": ["HTML5 Fundamentals", "CSS3 & Flexbox",
                           "CSS Grid", "Responsive Design",
                           "Basic JavaScript"],
                "project": "Build your first portfolio website"
            },
            {
                "month": 2,
                "title": "JavaScript Mastery",
                "topics": ["JavaScript ES6+", "DOM Manipulation",
                           "Events & Forms", "Fetch API",
                           "Local Storage"],
                "project": "Build a weather app using an API"
            },
            {
                "month": 3,
                "title": "React Basics",
                "topics": ["React Fundamentals", "Components & Props",
                           "State & Hooks", "React Router",
                           "Context API"],
                "project": "Build a todo app with React"
            },
            {
                "month": 4,
                "title": "Advanced React & Next.js",
                "topics": ["Next.js Framework", "Server Side Rendering",
                           "API Routes", "Authentication",
                           "Deployment on Vercel"],
                "project": "Build a full ecommerce frontend"
            },
            {
                "month": 5,
                "title": "Styling & Tools",
                "topics": ["Tailwind CSS", "Framer Motion",
                           "Git & GitHub", "VS Code Mastery",
                           "Browser DevTools"],
                "project": "Rebuild your portfolio with animations"
            },
            {
                "month": 6,
                "title": "Job Preparation",
                "topics": ["Portfolio Building", "Resume Writing",
                           "Interview Preparation", "Freelancing Basics",
                           "Salary Negotiation"],
                "project": "Complete 3 client projects"
            }
        ]
    },
    "backend-developer": {
        "title": "Backend Developer",
        "duration": "6 months",
        "description": "Build powerful server-side applications and APIs",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Python Fundamentals",
                "topics": ["Python Basics", "Data Types & Variables",
                           "Functions & Modules", "OOP Concepts",
                           "File Handling"],
                "project": "Build a student grade calculator"
            },
            {
                "month": 2,
                "title": "Web Frameworks",
                "topics": ["Flask Basics", "Django Introduction",
                           "REST APIs", "HTTP Methods",
                           "JSON & XML"],
                "project": "Build a REST API for a blog"
            },
            {
                "month": 3,
                "title": "Databases",
                "topics": ["SQL Basics", "PostgreSQL",
                           "MongoDB", "ORM with SQLAlchemy",
                           "Database Design"],
                "project": "Build a database for an ecommerce app"
            },
            {
                "month": 4,
                "title": "Authentication & Security",
                "topics": ["JWT Authentication", "OAuth2",
                           "Password Hashing", "CORS & Security Headers",
                           "Rate Limiting"],
                "project": "Build a secure user authentication system"
            },
            {
                "month": 5,
                "title": "Cloud & Deployment",
                "topics": ["AWS Basics", "Docker Introduction",
                           "CI/CD Pipelines", "Environment Variables",
                           "Server Management"],
                "project": "Deploy your API to AWS"
            },
            {
                "month": 6,
                "title": "Job Preparation",
                "topics": ["System Design", "API Documentation",
                           "Code Reviews", "Technical Interviews",
                           "Portfolio Building"],
                "project": "Build a complete backend for a real app"
            }
        ]
    },
    "data-scientist": {
        "title": "Data Scientist",
        "duration": "6 months",
        "description": "Analyse data and build machine learning models",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Python for Data Science",
                "topics": ["Python Basics", "NumPy",
                           "Pandas", "Data Cleaning",
                           "Jupyter Notebooks"],
                "project": "Analyse a real Nigerian dataset"
            },
            {
                "month": 2,
                "title": "Data Visualisation",
                "topics": ["Matplotlib", "Seaborn",
                           "Plotly", "Tableau Basics",
                           "Storytelling with Data"],
                "project": "Create an interactive data dashboard"
            },
            {
                "month": 3,
                "title": "Statistics & Mathematics",
                "topics": ["Descriptive Statistics", "Probability",
                           "Hypothesis Testing", "Regression Analysis",
                           "Statistical Thinking"],
                "project": "Statistical analysis of business data"
            },
            {
                "month": 4,
                "title": "Machine Learning",
                "topics": ["Supervised Learning", "Unsupervised Learning",
                           "Scikit-learn", "Model Evaluation",
                           "Feature Engineering"],
                "project": "Build a price prediction model"
            },
            {
                "month": 5,
                "title": "Deep Learning & AI",
                "topics": ["Neural Networks", "TensorFlow & Keras",
                           "Computer Vision Basics", "NLP Basics",
                           "Model Deployment"],
                "project": "Build an image classification model"
            },
            {
                "month": 6,
                "title": "Job Preparation",
                "topics": ["Kaggle Competitions", "Portfolio Projects",
                           "Interview Preparation", "Data Science Tools",
                           "Business Communication"],
                "project": "Complete end-to-end data science project"
            }
        ]
    },
    "cybersecurity": {
        "title": "Cybersecurity Professional",
        "duration": "6 months",
        "description": "Protect systems and networks from cyber threats",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Networking Fundamentals",
                "topics": ["TCP/IP Protocol", "OSI Model",
                           "DNS & HTTP", "Firewalls & VPNs",
                           "Network Scanning"],
                "project": "Set up a home lab network"
            },
            {
                "month": 2,
                "title": "Linux & Command Line",
                "topics": ["Linux Basics", "File System & Permissions",
                           "Bash Scripting", "Process Management",
                           "Log Analysis"],
                "project": "Automate security tasks with bash scripts"
            },
            {
                "month": 3,
                "title": "Ethical Hacking",
                "topics": ["Reconnaissance", "Vulnerability Scanning",
                           "Exploitation Basics", "Social Engineering",
                           "Kali Linux"],
                "project": "Complete a CTF challenge"
            },
            {
                "month": 4,
                "title": "Web Security",
                "topics": ["OWASP Top 10", "SQL Injection",
                           "XSS & CSRF", "Burp Suite",
                           "Web Application Pentesting"],
                "project": "Find vulnerabilities in a test web app"
            },
            {
                "month": 5,
                "title": "Security Tools & Frameworks",
                "topics": ["Metasploit", "Wireshark",
                           "Nmap", "SIEM Tools",
                           "Incident Response"],
                "project": "Complete a full penetration test"
            },
            {
                "month": 6,
                "title": "Certifications & Career",
                "topics": ["CompTIA Security+", "CEH Preparation",
                           "Bug Bounty Hunting", "Security Reports",
                           "Interview Preparation"],
                "project": "Submit a bug bounty report"
            }
        ]
    },
    "mobile-developer": {
        "title": "Mobile App Developer",
        "duration": "6 months",
        "description": "Build iOS and Android apps with Flutter",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Flutter Basics",
                "topics": ["Dart Language", "Flutter Setup",
                           "Widgets & Layouts", "Stateful vs Stateless",
                           "Hot Reload"],
                "project": "Build a calculator app"
            },
            {
                "month": 2,
                "title": "UI & Navigation",
                "topics": ["Material Design", "Custom Widgets",
                           "Navigation & Routing", "Animations",
                           "Responsive UI"],
                "project": "Build a beautiful social media UI"
            },
            {
                "month": 3,
                "title": "State Management",
                "topics": ["Provider", "Riverpod",
                           "BLoC Pattern", "GetX",
                           "Local State vs Global State"],
                "project": "Build a shopping cart app"
            },
            {
                "month": 4,
                "title": "Backend Integration",
                "topics": ["REST APIs with Dart", "Firebase",
                           "Authentication", "Cloud Firestore",
                           "Push Notifications"],
                "project": "Build a real-time chat app"
            },
            {
                "month": 5,
                "title": "Native Features",
                "topics": ["Camera & Gallery", "GPS & Maps",
                           "Local Storage", "Payments Integration",
                           "App Permissions"],
                "project": "Build a delivery tracking app"
            },
            {
                "month": 6,
                "title": "Publishing & Career",
                "topics": ["App Store Publishing", "Google Play Publishing",
                           "App Monetisation", "Performance Optimisation",
                           "Freelancing"],
                "project": "Publish your app to both stores"
            }
        ]
    },
    "ui-ux-designer": {
        "title": "UI/UX Designer",
        "duration": "6 months",
        "description": "Design beautiful and user-friendly digital products",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Design Fundamentals",
                "topics": ["Design Principles", "Colour Theory",
                           "Typography", "Layout & Grids",
                           "Design Thinking"],
                "project": "Redesign a bad app interface"
            },
            {
                "month": 2,
                "title": "Figma Mastery",
                "topics": ["Figma Interface", "Components & Variants",
                           "Auto Layout", "Prototyping",
                           "Design Systems"],
                "project": "Build a complete design system"
            },
            {
                "month": 3,
                "title": "User Research",
                "topics": ["User Interviews", "Personas",
                           "User Journey Maps", "Wireframing",
                           "Information Architecture"],
                "project": "Complete a UX research project"
            },
            {
                "month": 4,
                "title": "Advanced UI Design",
                "topics": ["Micro Interactions", "Motion Design",
                           "Dark Mode Design", "Accessibility",
                           "Mobile First Design"],
                "project": "Design a full mobile app"
            },
            {
                "month": 5,
                "title": "Portfolio & Branding",
                "topics": ["Portfolio Design", "Case Studies",
                           "Behance & Dribbble", "Personal Branding",
                           "Client Communication"],
                "project": "Complete 3 real client projects"
            },
            {
                "month": 6,
                "title": "Job Preparation",
                "topics": ["Design Interviews", "Whiteboard Challenges",
                           "Freelancing Rates", "Contract Templates",
                           "Salary Negotiation"],
                "project": "Build your complete portfolio"
            }
        ]
    },
    "graphic-design-branding": {
        "title": "Graphic Design & Branding",
        "duration": "10 weeks (2.5 months)",
        "description": "Logos, posters and complete brand systems with Adobe & Canva",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Design Foundations & Tools",
                "topics": ["Design Principles", "Colour Theory",
                           "Typography", "Photoshop Essentials",
                           "Canva for Fast Delivery"],
                "project": "Design a full social-media kit"
            },
            {
                "month": 2,
                "title": "Logo & Identity Design",
                "topics": ["Logo Design Process", "Brand Marks & Monograms",
                           "Illustrator Essentials", "Mockups & Presentation",
                           "Brand Guidelines"],
                "project": "Deliver a complete brand identity"
            },
            {
                "month": 3,
                "title": "Print, Brand Systems & Clients",
                "topics": ["Poster & Flyer Design", "Print Production Basics",
                           "Brand Systems at Scale", "Client Briefs & Revisions",
                           "Pricing & Freelancing"],
                "project": "Ship a 5-piece campaign for a real brief"
            }
        ]
    },
    "seo-content-writing": {
        "title": "SEO & Content Writing",
        "duration": "10 weeks (2.5 months)",
        "description": "Rank pages, write blogs that convert and earn in USD",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Writing & SEO Foundations",
                "topics": ["Grammar & Clarity", "How Search Works",
                           "Keyword Research", "Search Intent",
                           "On-Page SEO"],
                "project": "Publish an SEO-optimised article"
            },
            {
                "month": 2,
                "title": "Content That Converts",
                "topics": ["Blog Structure", "Headlines & Hooks",
                           "Long-form Guides", "Copywriting Basics",
                           "Content Calendars"],
                "project": "Write a 2,000-word pillar guide"
            },
            {
                "month": 3,
                "title": "Earning With Content",
                "topics": ["Technical SEO Basics", "Link Building",
                           "Analytics & Search Console", "Freelance Platforms",
                           "Client Pricing"],
                "project": "Deliver a full content plan for a client"
            }
        ]
    }
}


def get_career_roadmap(slug: str) -> dict:
    """Return a career roadmap dict. If a built-in roadmap exists, return it.
    Otherwise attempt to fetch content from roadmap.sh and return a minimal
    roadmap structure that includes the fetched markdown under `roadmap_md`.
    """
    if not slug:
        return {}
    slug_key = slug.replace("_", "-").replace(" ", "-").lower()
    if slug_key in CAREER_ROADMAPS:
        return CAREER_ROADMAPS[slug_key]

    md = fetch_roadmap(slug_key)
    if not md:
        return {}

    # Minimal structured roadmap using fetched markdown as a description
    return {
        "title": slug_key.replace("-", " ").title(),
        "duration": "Varies",
        "description": f"Roadmap imported from roadmap.sh for {slug_key}",
        "roadmap_md": md,
        "monthly_plan": []
    }

# ============================================================
# QUIZ BANK PER TOPIC
# ============================================================

def generate_quiz(topic, course):
    """Generate 10 quiz questions for a topic."""
    quizzes = {
        "HTML5 Fundamentals": [
            {
                "q": "What does HTML stand for?",
                "options": ["A) Hyper Text Markup Language",
                           "B) High Tech Modern Language",
                           "C) Hyper Transfer Markup Logic",
                           "D) Home Tool Markup Language"],
                "answer": "A",
                "explanation": "HTML stands for Hyper Text Markup Language"
            },
            {
                "q": "Which tag is used for the largest heading?",
                "options": ["A) <h6>", "B) <heading>",
                           "C) <h1>", "D) <head>"],
                "answer": "C",
                "explanation": "<h1> is the largest heading tag in HTML"
            },
            {
                "q": "What tag creates a paragraph?",
                "options": ["A) <para>", "B) <p>",
                           "C) <paragraph>", "D) <text>"],
                "answer": "B",
                "explanation": "The <p> tag creates a paragraph in HTML"
            },
            {
                "q": "Which attribute adds a link to an image?",
                "options": ["A) src", "B) href",
                           "C) link", "D) url"],
                "answer": "A",
                "explanation": "The src attribute specifies the image source"
            },
            {
                "q": "What tag creates an unordered list?",
                "options": ["A) <ol>", "B) <list>",
                           "C) <ul>", "D) <li>"],
                "answer": "C",
                "explanation": "<ul> creates an unordered (bullet) list"
            },
            {
                "q": "Which tag is used for a hyperlink?",
                "options": ["A) <link>", "B) <a>",
                           "C) <href>", "D) <url>"],
                "answer": "B",
                "explanation": "The <a> anchor tag is used for hyperlinks"
            },
            {
                "q": "What does the alt attribute do?",
                "options": [
                    "A) Changes image size",
                    "B) Provides alternative text for images",
                    "C) Links to another page",
                    "D) Adds a border"],
                "answer": "B",
                "explanation": "alt provides alternative text when image fails to load"
            },
            {
                "q": "Which tag creates a table row?",
                "options": ["A) <td>", "B) <th>",
                           "C) <tr>", "D) <table>"],
                "answer": "C",
                "explanation": "<tr> creates a table row"
            },
            {
                "q": "What tag creates a line break?",
                "options": ["A) <break>", "B) <lb>",
                           "C) <newline>", "D) <br>"],
                "answer": "D",
                "explanation": "<br> creates a line break in HTML"
            },
            {
                "q": "Which tag makes text bold?",
                "options": ["A) <bold>", "B) <b>",
                           "C) <strong> or <b>", "D) <thick>"],
                "answer": "C",
                "explanation": "Both <strong> and <b> make text bold"
            }
        ],
        "Python Basics": [
            {
                "q": "How do you print 'Hello World' in Python?",
                "options": [
                    "A) echo 'Hello World'",
                    "B) print('Hello World')",
                    "C) console.log('Hello World')",
                    "D) System.out.println('Hello World')"],
                "answer": "B",
                "explanation": "print() is the Python function for output"
            },
            {
                "q": "Which symbol is used for comments in Python?",
                "options": ["A) //", "B) /* */",
                           "C) #", "D) --"],
                "answer": "C",
                "explanation": "# is used for single line comments in Python"
            },
            {
                "q": "What is the correct way to declare a variable?",
                "options": ["A) var x = 5", "B) int x = 5",
                           "C) x = 5", "D) declare x = 5"],
                "answer": "C",
                "explanation": "Python uses dynamic typing — just write x = 5"
            },
            {
                "q": "Which of these is a string?",
                "options": ["A) 42", "B) 3.14",
                           "C) True", "D) 'Hello'"],
                "answer": "D",
                "explanation": "Strings are enclosed in quotes in Python"
            },
            {
                "q": "What does len() do?",
                "options": [
                    "A) Converts to lowercase",
                    "B) Returns the length of an object",
                    "C) Deletes a variable",
                    "D) Creates a list"],
                "answer": "B",
                "explanation": "len() returns the number of items in an object"
            },
            {
                "q": "How do you create a list in Python?",
                "options": [
                    "A) list = (1, 2, 3)",
                    "B) list = {1, 2, 3}",
                    "C) list = [1, 2, 3]",
                    "D) list = <1, 2, 3>"],
                "answer": "C",
                "explanation": "Lists use square brackets [] in Python"
            },
            {
                "q": "What is the output of 2 ** 3?",
                "options": ["A) 6", "B) 8",
                           "C) 9", "D) 23"],
                "answer": "B",
                "explanation": "** is the exponent operator — 2 to the power of 3 = 8"
            },
            {
                "q": "Which keyword starts a function?",
                "options": ["A) function", "B) func",
                           "C) def", "D) define"],
                "answer": "C",
                "explanation": "def keyword is used to define functions in Python"
            },
            {
                "q": "What does input() do?",
                "options": [
                    "A) Displays output",
                    "B) Gets user input from keyboard",
                    "C) Reads a file",
                    "D) Creates a variable"],
                "answer": "B",
                "explanation": "input() reads text entered by the user"
            },
            {
                "q": "Which operator checks equality?",
                "options": ["A) =", "B) !=",
                           "C) ==", "D) >="],
                "answer": "C",
                "explanation": "== checks if two values are equal"
            }
        ]
    }

    # Return quiz for topic or generate generic ones
    if topic in quizzes:
        return quizzes[topic]
    else:
        return generate_generic_quiz(topic)


def generate_generic_quiz(topic):
    """Generate generic quiz questions for any topic."""
    return [
        {
            "q": f"What is the main purpose of {topic}?",
            "options": [
                "A) To make code faster",
                "B) To organise and structure information",
                "C) To connect to the internet",
                "D) To display graphics"],
            "answer": "B",
            "explanation": f"{topic} helps organise and structure information effectively"
        },
        {
            "q": f"Which of these is a key concept in {topic}?",
            "options": [
                "A) Random guessing",
                "B) Structure and organisation",
                "C) Ignoring best practices",
                "D) Avoiding documentation"],
            "answer": "B",
            "explanation": "Structure and organisation are fundamental to all tech topics"
        }
    ]


# ============================================================
# CLASS TEXTBOOKS - W3Schools-style material per class/video
# ============================================================
# After each class, the AI learning system turns the YouTube video the
# cohort just watched into a reference-first "textbook" and files it here.
# Format follows the W3Schools template:
#   chapter-based sidebar navigation -> micro-lesson pages, each with a short
#   plain-language intro, one live example immediately (code, or an image for
#   non-technical topics), a "Try it Yourself" editable sandbox, progressive
#   sub-examples (basic -> edge cases -> variations), a Note/Tip callout, and
#   an end-of-page Exercise + quiz link for reinforcement.

TEXTBOOK_SCHEMA_VERSION = "w3schools-v1"


def _textbooks_index_path():
    """Index of every generated class textbook (lightweight library rows)."""
    os.makedirs(TEXTBOOKS_DIR, exist_ok=True)
    return os.path.join(str(TEXTBOOKS_DIR), "class_textbooks.json")


def _textbook_file_path(tb_id):
    """Full textbook body lives in its own file so the index stays small."""
    os.makedirs(TEXTBOOKS_DIR, exist_ok=True)
    safe = "".join(c for c in str(tb_id) if c.isalnum() or c in "-_")[:80]
    return os.path.join(str(TEXTBOOKS_DIR), f"class_textbook_{safe}.json")


def _json_file_load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _json_file_save(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"[ERROR] Could not write {path}: {e}")
        return False


# ============================================================
# CLASS TIMETABLES � weekly schedules published by a teacher
# One row per course; sessions are {day, time, subject} rows.
# ============================================================

def _class_timetables_path():
    """Index of teacher-published class timetables, one row per course."""
    os.makedirs(TIMETABLES_DIR, exist_ok=True)
    return os.path.join(str(TIMETABLES_DIR), "class_timetables.json")


def save_class_timetable(course, title, sessions, teacher=""):
    """Upsert the weekly timetable for a course. `sessions` is a list of
    {day, time, subject} rows; returns the stored row (or None)."""
    course_key = str(course or "").strip().lower()
    if not course_key or not isinstance(sessions, list) or not sessions:
        return None
    rows = _json_file_load(_class_timetables_path()) or []
    if not isinstance(rows, list):
        rows = []
    rows = [r for r in rows
            if isinstance(r, dict)
            and str(r.get("course", "")).strip().lower() != course_key]
    row = {
        "course": course,
        "title": str(title or "Weekly class schedule")[:120],
        "teacher": str(teacher or "")[:80],
        "sessions": sessions,
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
    rows.insert(0, row)
    _json_file_save(_class_timetables_path(), rows)
    return row


def load_class_timetable(course):
    """The published timetable for a course, or None when the teacher has not
    published one yet."""
    course_key = str(course or "").strip().lower()
    if not course_key:
        return None
    rows = _json_file_load(_class_timetables_path()) or []
    if not isinstance(rows, list):
        return None
    for r in rows:
        if isinstance(r, dict) and str(r.get("course", "")).strip().lower() == course_key:
            return r
    return None


def _normalise_lesson(raw, idx):
    """Coerce one model-produced lesson into the canonical W3Schools shape."""
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or f"Lesson {idx + 1}").strip()
    intro = str(raw.get("intro") or raw.get("summary") or "").strip()
    ex = raw.get("example") if isinstance(raw.get("example"), dict) else {}
    img = raw.get("example_image") if isinstance(raw.get("example_image"), dict) else {}
    example = None
    if ex.get("code"):
        example = {"lang": str(ex.get("lang") or "code"), "code": str(ex.get("code")),
                   "caption": str(ex.get("caption") or "")}
    elif img.get("url"):
        # Non-technical courses show a picture instead of live code.
        example = {"lang": "image", "url": str(img.get("url")),
                   "caption": str(img.get("caption") or "")}
    try_it = raw.get("try_it") if isinstance(raw.get("try_it"), dict) else {}
    variations = []
    for v in (raw.get("variations") or [])[:6]:
        if isinstance(v, str):
            variations.append({"label": "Variation", "text": v})
        elif isinstance(v, dict):
            variations.append({
                "label": str(v.get("label") or "Variation"),
                "code": str(v.get("code") or ""),
                "lang": str(v.get("lang") or "code"),
                "text": str(v.get("text") or ""),
            })
    exercise = raw.get("exercise") if isinstance(raw.get("exercise"), dict) else {}

    # ---- document-designer blocks ---------------------------------------
    # The combined author prompt also asks for the deep teaching text, a
    # line-by-line walkthrough of every example, a second example, a
    # "Common Mistakes" list and a "Key Points" summary. They are carried
    # through here so the dashboard reader and the downloaded PDF can show
    # them. Books generated before this change simply carry empty values and
    # render exactly as they did before.
    def _text_list(value, limit=10):
        if isinstance(value, str):
            value = [value]
        out = []
        for item in (value or [])[:limit]:
            if isinstance(item, str):
                txt = item.strip()
            elif isinstance(item, dict):
                txt = str(item.get("text") or item.get("point")
                          or item.get("mistake") or "").strip()
            else:
                txt = ""
            if txt:
                out.append(txt)
        return out

    second = raw.get("second_example") if isinstance(raw.get("second_example"), dict) else {}
    second_example = None
    if second.get("code"):
        second_example = {
            "lang": str(second.get("lang") or (example or {}).get("lang") or "code"),
            "code": str(second.get("code")),
            "caption": str(second.get("caption") or ""),
        }
    elif second.get("url"):
        # Non-technical courses show a picture instead of live code.
        second_example = {"lang": "image", "url": str(second.get("url")),
                          "caption": str(second.get("caption") or "")}

    return {
        "lesson_num": int(raw.get("lesson_num") or idx + 1),
        "title": title[:160],
        "intro": intro,
        "content": str(raw.get("content") or "").strip(),
        "example": example,
        "example_explanation": str(raw.get("example_explanation") or "").strip(),
        "second_example": second_example,
        "second_example_explanation": str(raw.get("second_example_explanation") or "").strip(),
        "common_mistakes": _text_list(raw.get("common_mistakes")),
        "key_points": _text_list(raw.get("key_points")),
        "try_it": {
            "lang": str(try_it.get("lang") or (example or {}).get("lang") or "code"),
            "starter": str(try_it.get("starter") or (example or {}).get("code") or ""),
            "task": str(try_it.get("task") or ""),
        },
        "variations": variations,
        "note": str(raw.get("note") or "").strip(),
        "tip": str(raw.get("tip") or "").strip(),
        "exercise": {
            "prompt": str(exercise.get("prompt") or ""),
            "hint": str(exercise.get("hint") or ""),
        },
    }


def _normalise_textbook(tb):
    """Validate/repair a whole textbook dict; returns (clean, lesson_count)."""
    if not isinstance(tb, dict):
        return None, 0
    chapters = []
    n = 0
    for ch in (tb.get("chapters") or [])[:10]:
        if not isinstance(ch, dict):
            continue
        lessons = []
        for i, ls in enumerate((ch.get("lessons") or [])[:12]):
            clean = _normalise_lesson(ls, i)
            if clean:
                lessons.append(clean)
        n += len(lessons)
        if lessons:
            chapters.append({
                "chapter": str(ch.get("chapter") or "Chapter"),
                "overview": str(ch.get("overview") or "").strip(),
                "lessons": lessons,
            })
    if not chapters:
        return None, 0
    out = dict(tb)
    out["chapters"] = chapters
    out["format"] = TEXTBOOK_SCHEMA_VERSION

    # ---- document-designer extras ---------------------------------------
    # Cover / table of contents / introduction / practice section /
    # conclusion / glossary are stored as-is, only reshaped into what the
    # dashboard reader and the PDF writer can safely render.
    out["subtitle"] = str(tb.get("subtitle") or "").strip()
    out["cover"] = tb.get("cover") if isinstance(tb.get("cover"), dict) else {}
    out["toc"] = [{"chapter": str(row.get("chapter") or "").strip(),
                   "page": int(row.get("page") or 0)}
                  for row in (tb.get("toc") or [])[:20]
                  if isinstance(row, dict)]
    out["introduction"] = str(tb.get("introduction") or "").strip()
    out["conclusion"] = str(tb.get("conclusion") or "").strip()

    practice = tb.get("practice_section")
    practice = practice if isinstance(practice, dict) else {}

    def _practice_rows(key):
        rows = []
        for i, row in enumerate((practice.get(key) or [])[:40], 1):
            if isinstance(row, dict):
                rows.append({"number": int(row.get("number") or i),
                             "prompt": str(row.get("prompt") or "").strip(),
                             "answer": str(row.get("answer") or "").strip()})
            elif isinstance(row, str) and row.strip():
                rows.append({"number": i, "prompt": row.strip(), "answer": ""})
        return rows

    out["practice_section"] = {"exercises": _practice_rows("exercises"),
                               "answers": _practice_rows("answers")}

    glossary = []
    for entry in (tb.get("glossary") or [])[:60]:
        if isinstance(entry, dict):
            term = str(entry.get("term") or "").strip()
            if term:
                glossary.append({
                    "term": term,
                    "definition": str(entry.get("definition")
                                      or entry.get("meaning") or "").strip(),
                })
        elif isinstance(entry, str) and entry.strip():
            glossary.append({"term": entry.strip(), "definition": ""})
    out["glossary"] = glossary
    return out, n


def _textbook_row(tb, lesson_count=None):
    """Shape a textbook exactly like studentdashboard.vue's `docs` entries."""
    tb_id = str(tb.get("id") or "")
    chapters = tb.get("chapters") or []
    lessons = sum(len(c.get("lessons", [])) for c in chapters)
    words = 0
    for c in chapters:
        for l in c.get("lessons", []):
            words += len(str(l.get("intro", "")).split())
            words += len(str(l.get("content", "")).split())
            words += len(str(((l.get("example") or {}).get("code")) or "").split())
            words += len(str(l.get("example_explanation", "")).split())
            words += len(str(l.get("note", "")).split())
    video = tb.get("source_video") or {}
    title = tb.get("title") or f"Textbook � {video.get('title') or tb.get('course') or 'Class'}"
    return {
        "id": tb_id,
        "kind": "textbook",
        "title": title[:180],
        "tag": "Textbook",
        "pages": max(1, lesson_count if lesson_count is not None else lessons),
        "size": f"{max(words / 500.0, 0.1):.1f} MB",
        "updated": tb.get("created_label") or "",
        "hue": tb.get("hue") or "teal",
        "big": "W3",
        "ai": True,
        "course": tb.get("course") or "",
        "career_path": tb.get("career_path") or "",
        "video_title": video.get("title") or "",
        "video_url": video.get("url") or "",
        "class_number": tb.get("class_number"),
        "chapters": len(chapters),
        "lessons": lessons,
        "minutes": tb.get("minutes") or 15,
    }


def save_class_textbook(textbook):
    """
    Store (or replace) the textbook generated after a class.

    Dedupe key: course + source video + class number, so re-running the same
    class refreshes its book instead of duplicating it. Returns library row.
    """
    tb, lesson_count = _normalise_textbook(textbook)
    if not tb:
        print("[WARN] class textbook rejected - no usable chapters/lessons")
        return None

    video = tb.get("source_video") or {}
    seed = ("|".join([
        str(tb.get("course", "")),
        str(video.get("video_id") or video.get("url") or video.get("title", "")),
        str(tb.get("class_number", "")),
    ]))
    import hashlib
    tb_id = tb.get("id") or ("tb_" + hashlib.md5(seed.encode("utf-8")).hexdigest()[:12])
    tb["id"] = tb_id
    if not tb.get("created_at"):
        tb["created_at"] = datetime.now().isoformat(timespec="seconds")
    tb["created_label"] = datetime.now().strftime("%d %b %Y")

    if not _json_file_save(_textbook_file_path(tb_id), tb):
        return None

    index = _json_file_load(_textbooks_index_path()) or []
    if not isinstance(index, list):
        index = []
    row = _textbook_row(tb, lesson_count)
    index = [r for r in index if isinstance(r, dict) and r.get("id") != tb_id]
    index.insert(0, row)
    _json_file_save(_textbooks_index_path(), index)

    video_label = video.get("title") or tb.get("course") or "class"
    print(f"[YES] Textbook saved: {row['title'][:60]} "
          f"({len(tb['chapters'])} chapters / {row['lessons']} lessons) from {str(video_label)[:50]}")
    return row


def get_class_textbook(tb_id):
    """Full textbook body for the dashboard reader, or None."""
    if not tb_id:
        return None
    return _json_file_load(_textbook_file_path(tb_id))


def get_textbook_library(course="", career_path="", limit=60):
    """
    Library rows for the student dashboard, newest first.
    Optional filters match the stored course / career path (substring).
    """
    index = _json_file_load(_textbooks_index_path()) or []
    if not isinstance(index, list):
        return []
    course_n = (course or "").strip().lower()
    career_n = (career_path or "").strip().lower()
    rows = []
    for r in index:
        if not isinstance(r, dict):
            continue
        if course_n and course_n not in str(r.get("course", "")).lower():
            continue
        if career_n and career_n not in str(r.get("career_path", "")).lower():
            continue
        rows.append(r)
    return rows[:max(1, int(limit))]


# ============================================================
# ACCOUNTS & PAYMENTS - student login + Paystack verification
# ============================================================

def _hash_password(password, salt_hex=None):
    """PBKDF2-SHA256 (120k iterations). Returns (salt_hex, hash_hex)."""
    import hashlib
    import hmac as _hmac  # noqa: F401 (kept alongside hashlib for clarity)
    if salt_hex is None:
        salt_hex = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 120_000)
    return salt_hex, digest.hex()


def set_student_password(student_id, password):
    """Store a hashed login password on the student record."""
    password = str(password or "")
    if len(password) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters."}
    students = load_students()
    student = students.get(student_id)
    if not student:
        return {"ok": False, "error": f"Unknown student {student_id}"}
    salt_hex, hash_hex = _hash_password(password)
    student["password_salt"] = salt_hex
    student["password_hash"] = hash_hex
    student["credentials_updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_students(students)
    print(f"[YES] Login password saved for {student_id}")
    return {"ok": True}


def verify_student_login(email, password):
    """
    Check email+password against stored records.
    Returns the full student dict on success, None on any failure.
    """
    import hmac as _hmac
    email_n = str(email or "").strip().lower()
    if not email_n or not password:
        return None
    students = load_students()
    student = next((s for s in students.values()
                    if str(s.get("email", "")).strip().lower() == email_n), None)
    if not student or not student.get("password_hash") or not student.get("password_salt"):
        return None
    try:
        _, candidate = _hash_password(str(password), student["password_salt"])
    except Exception:
        return None
    if _hmac.compare_digest(candidate, str(student["password_hash"])):
        return student
    return None


def verify_paystack_payment(student_id, reference, months=0, kind=""):
    """
    Ask Paystack whether a transaction reference really succeeded, then:

      - always record the payment + mark the student financially active;
      - when `months` > 0 (school-fee payments) extend `access_paid_through`
        by that many months - the dashboard lock checks exactly this window;
      - references are remembered, so re-verifying the same one (e.g. the
        silent reconcile-on-load) never double-extends access.
    """
    reference = str(reference or "").strip()
    if not PAYSTACK_SECRET_KEY:
        return {"verified": False, "error": "PAYSTACK_SECRET_KEY not configured"}
    if not reference:
        return {"verified": False, "error": "payment reference required"}

    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
            timeout=20,
        )
        data = response.json() if response.status_code == 200 else {}
        status = str((data.get("data") or {}).get("status") or "").lower()
    except Exception as e:
        return {"verified": False, "error": f"Paystack unreachable: {str(e)[:120]}"}

    if response.status_code != 200 or status != "success":
        return {"verified": False,
                "error": f"Paystack says this reference is '{status or 'unknown'}'"}

    students = load_students()
    touched = []
    target = students.get(student_id)
    if target:
        target["payment_status"] = "paid"
        touched.append(target)
    else:
        meta = ((data.get("data") or {}).get("customer") or {})
        email = str(meta.get("email") or "").strip().lower()
        if email:
            for s in students.values():
                if str(s.get("email", "")).strip().lower() == email:
                    s["payment_status"] = "paid"
                    touched.append(s)
                    if not student_id:
                        student_id = s.get("student_id")
    if not touched:
        return {"verified": False,
                "error": "No student record matched this payment yet"}

    # Seed from the local payment mirror (PostgreSQL may lack the access/payment
    # columns, so the last window + refs live locally). Keeps re-verify
    # idempotent and lets a second payment stack instead of restarting.
    _overlay_local_payment(touched)

    already = False
    for s in touched:
        refs = s.setdefault("verified_refs", [])
        if reference in refs:
            already = True          # reconcile re-check: do NOT double-extend
        else:
            refs.append(reference)

    months = max(0, int(months or 0))
    amount_paid = ((data.get("data") or {}).get("amount") or 0) / 100.0
    for s in touched:
        if months > 0 and not already:
            grant_monthly_access(s, months, reference, amount=amount_paid)
        s["last_payment_kind"] = kind or ("monthly-fees" if months > 0 else "payment")
        s["last_payment_at"] = datetime.now().isoformat(timespec="seconds")
    save_students(students)
    # Mirror access/payment fields locally � the PostgreSQL table may not have
    # these columns yet (see save_students warnings); without this mirror the
    # granted window is dropped on the next read and roadmap/dashboard re-lock.
    try:
        _mirror_payment_local(touched)
    except Exception as e:
        print(f"[WARN] local payment mirror failed: {e}")

    return {"verified": True, "payment_status": "paid",
            "students_updated": len(touched),
            "amount": (data.get("data") or {}).get("amount"),
            "reference": reference,
            "access": get_access_state(touched[0])}


def verify_paystack_book_purchase(student_id, reference, textbook_id):
    """
    Verify a Paystack reference as a LIBRARY TEXTBOOK purchase (the admin/
    partner-priced PDFs, kind 'textbook').

    Same secret-key truth check as verify_paystack_payment, then:

      - the paid amount must cover the book's current price;
      - the textbook row gains the buyer in `purchased_by` (idempotent — a
        re-verified reference can never charge or unlock twice);
      - the student record gains a `book_purchases` entry (mirrored locally
        alongside the other payment fields);
      - returns the refreshed textbook row so the dashboard can unlock it.

    Free books (price 0) never need this — they are served unlocked.
    """
    reference = str(reference or "").strip()
    textbook_id = str(textbook_id or "").strip()
    if not PAYSTACK_SECRET_KEY:
        return {"verified": False, "error": "PAYSTACK_SECRET_KEY not configured"}
    if not reference or not textbook_id:
        return {"verified": False, "error": "payment reference and textbook id required"}

    try:
        response = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"},
            timeout=20,
        )
        data = response.json() if response.status_code == 200 else {}
        status = str((data.get("data") or {}).get("status") or "").lower()
    except Exception as e:
        return {"verified": False, "error": f"Paystack unreachable: {str(e)[:120]}"}

    if response.status_code != 200 or status != "success":
        return {"verified": False,
                "error": f"Paystack says this reference is '{status or 'unknown'}'"}

    index = _json_file_load(_textbooks_index_path()) or []
    if not isinstance(index, list):
        index = []
    row = next((r for r in index if isinstance(r, dict) and r.get("id") == textbook_id), None)
    if row is None:
        return {"verified": False, "error": "unknown textbook"}

    price = max(0, int(row.get("price") or 0))
    amount_paid = ((data.get("data") or {}).get("amount") or 0) / 100.0
    if amount_paid + 0.5 < price:
        return {"verified": False,
                "error": f"amount paid (₦{amount_paid:.0f}) is short of the book price (₦{price})"}

    # Resolve the buyer: explicit student id wins, else match the Paystack email.
    students = load_students()
    student = students.get(student_id)
    if student is None:
        email = str(((data.get("data") or {}).get("customer") or {}).get("email") or "").strip().lower()
        if email:
            student = next((s for s in students.values()
                            if str(s.get("email", "")).strip().lower() == email), None)
    if student is None:
        return {"verified": False, "error": "No student record matched this payment"}

    student_id = student.get("student_id") or student_id
    buyers = row.setdefault("purchased_by", [])
    if student_id not in buyers:
        buyers.append(student_id)
    purchases = row.setdefault("purchases", [])
    purchases.append({
        "student_id": student_id,
        "reference": reference,
        "amount": round(amount_paid, 2),
        "currency": "NGN",
        "purchased_at": datetime.now().isoformat(timespec="seconds"),
    })
    if len(purchases) > 500:
        del purchases[:-500]
    index = [r for r in index if not (isinstance(r, dict) and r.get("id") == textbook_id)]
    index.insert(0, row)
    _json_file_save(_textbooks_index_path(), index)

    # Idempotency on the student side: remember the reference so the silent
    # reconcile-on-load never double-records this purchase.
    refs = student.setdefault("verified_refs", [])
    if reference not in refs:
        refs.append(reference)
    history = student.setdefault("book_purchases", [])
    if not any(p.get("reference") == reference for p in history):
        history.append({
            "textbook_id": textbook_id,
            "title": row.get("title") or "",
            "reference": reference,
            "amount": round(amount_paid, 2),
            "currency": "NGN",
            "purchased_at": datetime.now().isoformat(timespec="seconds"),
        })
    if len(history) > 60:
        del history[:-60]
    student["last_payment_kind"] = "textbook"
    student["last_payment_at"] = datetime.now().isoformat(timespec="seconds")
    save_students(students)
    try:
        _mirror_payment_local([student])
    except Exception as e:
        print(f"[WARN] local payment mirror failed: {e}")

    print(f"[YES] Textbook '{textbook_id}' unlocked for {student_id} "
          f"(₦{amount_paid:.0f}, ref {reference})")
    return {"verified": True, "purchased": True, "reference": reference,
            "amount": round(amount_paid, 2), "textbook": row}


# ---- Monthly school-fee access model -------------------------------

# ---- Monthly school-fee access model -------------------------------
# Students pay MONTHLY for dashboard access; the price depends on the
# course they are doing. Access = an `access_paid_through` date on the
# record; the dashboard stays locked while today >= that date.

COURSE_MONTHLY_FEES = {
    "default": 50000,
    "frontend-developer": 45000,
    "backend-developer": 55000,
    "full-stack web development": 55000,
    "mobile-developer": 50000,
    "ui-ux-designer": 40000,
    "graphic design": 35000,
    "graphic-design-branding": 35000,
    "seo-content-writing": 30000,
    "data-scientist": 60000,
    "data analysis": 45000,
    "cloud computing": 60000,
    "devops": 60000,
    "cybersecurity": 65000,
}


def get_monthly_fee(course_key=""):
    """Monthly fee (NGN) for a course slug/name; falls back to the default."""
    k = str(course_key or "").strip().lower()
    if not k:
        return COURSE_MONTHLY_FEES["default"]
    for slug, fee in COURSE_MONTHLY_FEES.items():
        if slug != "default" and (slug in k or k in slug):
            return fee
    return COURSE_MONTHLY_FEES["default"]


def _first_of_month_shifted(d, months):
    """Exclusive access boundary: the 1st of the month `months` ahead of d."""
    total = d.month - 1 + max(0, int(months))
    year = d.year + total // 12
    month = (total % 12) + 1
    return date(year, month, 1)


def grant_monthly_access(student, months, reference="", amount=0.0):
    """Extend `access_paid_through` by `months` full months from whichever is
    later: today or the current paid-through date. Logs the fee payment."""
    months = max(1, int(months or 1))
    today = date.today()
    through_iso = str(student.get("access_paid_through") or "").strip()
    base = today
    if through_iso:
        try:
            existing = date.fromisoformat(through_iso[:10])
            if existing > today:
                base = existing
        except Exception:
            pass
    new_through = _first_of_month_shifted(base, months)
    student["access_paid_through"] = new_through.isoformat()

    history = student.setdefault("fee_payments", [])
    history.append({
        "month": today.strftime("%Y-%m"),
        "months_covered": months,
        "amount": round(float(amount or 0), 2),
        "currency": "NGN",
        "reference": reference,
        "paid_at": datetime.now().isoformat(timespec="seconds"),
        "paid_through": new_through.isoformat(),
    })
    if len(history) > 60:
        del history[:-60]
    print(f"[YES] Monthly access extended for {student.get('student_id')}: "
          f"+{months} month(s) -> paid through {new_through.isoformat()}")


def get_access_state(student):
    """Everything the dashboard lock needs, computed server-side."""
    course_key = student.get("career_path") or student.get("course_name") or ""
    fee = get_monthly_fee(course_key)
    through_iso = str(student.get("access_paid_through") or "").strip()
    through = None
    if through_iso:
        try:
            through = date.fromisoformat(through_iso[:10])
        except Exception:
            through = None
    today = date.today()
    active = bool(through and through > today)
    days_left = (through - today).days if active else 0
    return {
        "locked": not active,
        "paid_through": through.isoformat() if through else "",
        "days_left": days_left,
        "monthly_fee": fee,
        "currency": "NGN",
        "months_paid": len(student.get("fee_payments") or []),
    }


# Fields that must survive even while the PostgreSQL students table lacks their
# columns (access window, payment refs/history, per-day schedule).
_PAYMENT_LOCAL_KEYS = (
    "access_paid_through",
    "fee_payments",
    "book_purchases",
    "verified_refs",
    "last_payment_kind",
    "last_payment_at",
    "preferred_daily_times",
)


def _overlay_local_payment(students_list):
    """Overlay locally-mirrored payment/access fields onto PostgreSQL records."""
    try:
        store = _students_file_load()
    except Exception:
        return
    if not store:
        return
    for s in students_list or []:
        if not isinstance(s, dict):
            continue
        local = store.get(s.get("student_id"))
        if not isinstance(local, dict):
            continue
        for key in _PAYMENT_LOCAL_KEYS:
            if not s.get(key) and local.get(key):
                s[key] = local[key]


_ATTENDANCE_LOCAL_KEYS = (
    "classes_attended", "classes_missed", "total_classes",
    "attendance_rate", "attendance_records",
)


def _overlay_local_attendance(student):
    """Overlay locally-recorded attendance fields onto a PostgreSQL record.

    mark_attendance() falls back to the local JSON store whenever PostgreSQL's
    row-level security blocks inserts. While that happens, the source of truth
    for attendance lives locally � so reads must merge it back in or the
    dashboard/roadmap would keep showing 0 classes and never auto-complete.
    """
    try:
        store = _students_file_load()
    except Exception:
        return
    if not isinstance(student, dict):
        return
    local = store.get(student.get("student_id"))
    if not isinstance(local, dict):
        return
    for key in _ATTENDANCE_LOCAL_KEYS:
        lv = local.get(key)
        if lv is None:
            continue
        sv = student.get(key)
        if key == "attendance_records":
            if isinstance(lv, list) and len(lv) >= len(sv or []):
                student[key] = lv
        else:
            # Counters: trust the larger value over a stale PostgreSQL copy.
            try:
                if sv is None or (float(lv) > float(sv)):
                    student[key] = lv
            except (TypeError, ValueError):
                student[key] = lv


def _mirror_payment_local(students_list):
    """Persist payment/access fields to the local JSON store as a backup."""
    store = _students_file_load()
    changed = False
    for s in students_list or []:
        if not isinstance(s, dict) or not s.get("student_id"):
            continue
        row = store.get(s["student_id"])
        if not isinstance(row, dict):
            row = {"student_id": s["student_id"]}
        for key in _PAYMENT_LOCAL_KEYS:
            if s.get(key) not in (None, "", []):
                row[key] = s[key]
                changed = True
        for key in ("name", "email", "career_path", "course_name"):
            if s.get(key) and not row.get(key):
                row[key] = s[key]
                changed = True
        if s.get("payment_status"):
            row["payment_status"] = s["payment_status"]
            changed = True
        store[s["student_id"]] = row
    if changed:
        _students_file_save(store)


# ============================================================
# STUDENT MANAGEMENT - POSTGRESQL
# ============================================================

def _students_file_path():
    """Local JSON store used whenever PostgreSQL is not configured/available."""
    os.makedirs(STUDENTS_DIR, exist_ok=True)
    return os.path.join(str(STUDENTS_DIR), "students.json")


def _students_file_load():
    try:
        with open(_students_file_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _students_file_save(students):
    try:
        os.makedirs(STUDENTS_DIR, exist_ok=True)
        tmp = _students_file_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(students, fh, indent=2, default=str)
        os.replace(tmp, _students_file_path())
    except Exception as e:
        print(f"[ERROR] Could not write local students store: {e}")


def load_students():
    """Load all students: PostgreSQL when configured, local JSON otherwise."""
    if db:
        try:
            response = db.table("students").select("*").execute()
            students = {}
            for row in response.data:
                student_id = row.get("student_id")
                students[student_id] = row
            return students
        except Exception as e:
            print(f"[ERROR] Failed to load students from PostgreSQL: {e}")
    return _students_file_load()


_table_columns_cache = None


def _students_table_columns():
    """Column names of the PostgreSQL students table, fetched once per process.

    save_students() writes whole student dicts, and some fields live only in
    memory (last_payment_at, verified_refs, fee_payments, credentials_updated_at,
    ...). If any key is not a real table column, PostgREST rejects the write and
    the WHOLE save used to fall back to the local JSON file � which login never
    reads (it reads PostgreSQL), so students ended up enrolled but unable to sign
    in. Filtering each payload to real columns keeps saves alive; a warning
    lists what was dropped so the matching columns can be added to the table.
    """
    global _table_columns_cache
    if _table_columns_cache is None:
        try:
            probe = db.table("students").select("*").limit(1).execute()
            rows = probe.data or []
            if rows:
                _table_columns_cache = set(rows[0].keys())
            else:
                # Table exists but is empty — read the real column names from
                # the information schema so saves are never filtered to {}.
                from pgdb import _run
                cols = _run(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'students'"
                )
                _table_columns_cache = {c["column_name"] for c in (cols or [])}
        except Exception as e:
            print(f"[WARN] Could not read students table columns: {e}")
            _table_columns_cache = set()
    return _table_columns_cache


def save_students(students):
    """Save all students: PostgreSQL upserts when configured, else local JSON."""
    if db:
        columns = _students_table_columns()
        failed_ids = []
        for student_id, student_data in students.items():
            try:
                # Keep only real table columns � in-memory-only fields must
                # never abort the save (that silently lost passwords/payments).
                payload = student_data
                if columns:
                    dropped = [k for k in student_data if k not in columns]
                    if dropped:
                        payload = {k: v for k, v in student_data.items()
                                   if k in columns}
                        print(f"[WARN] save_students({student_id}): not table "
                              f"columns, skipped: {dropped} � add them in "
                              f"PostgreSQL to persist them")
                existing = db.table("students").select("student_id").eq("student_id", student_id).execute()

                if existing.data:
                    # Update existing student
                    db.table("students").update(payload).eq("student_id", student_id).execute()
                else:
                    # Insert new student
                    db.table("students").insert(payload).execute()
            except Exception as e:
                failed_ids.append(student_id)
                print(f"[ERROR] save_students({student_id}) failed: {e}")
        if not failed_ids:
            return
        # Partial failure: PostgreSQL is reachable but some rows failed � log
        # loudly and keep PostgreSQL as the source of truth (no silent local
        # diversion, which previously caused the "cannot sign in" split-brain).
        # Total failure (PostgreSQL itself unreachable) still uses the local file.
        if len(failed_ids) < len(students):
            print(f"[ERROR] {len(failed_ids)}/{len(students)} student(s) failed "
                  f"to save to PostgreSQL: {failed_ids} � retry the action.")
            return
        print("[ERROR] All student saves failed � PostgreSQL unreachable; "
              "falling back to the local JSON store.")
    _students_file_save(students)


def enroll_student(name, phone, email, career_path, experience_level="beginner",
                   course_name="", track="", goals=None, duration_months=None,
                   class_minutes=60, extra_fields=None,
                   preferred_time="", preferred_daily_times=None):
    """
    Enroll a new student after payment confirmation.

    Works with PostgreSQL when configured, and falls back to the local JSON
    store otherwise, so registration never silently loses an applicant.
    Extra submitted details arrive via keyword args / extra_fields and are
    stored on the record so the dashboard can show the real person.
    """
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Enrolling student: {name}...")

    intake_month = date.today().strftime("%Y-%m")
    students = load_students()

    count = len(students)
    student_id = f"STU{count + 1:04d}"
    while student_id in students:
        count += 1
        student_id = f"STU{count + 1:04d}"

    # Classmates in the same course and intake month -> group class
    classmates = [sid for sid, s in students.items()
                  if isinstance(s, dict)
                  and s.get("career_path") == career_path
                  and s.get("intake_month") == intake_month
                  and s.get("payment_status") == "paid"]
    class_type = "group" if classmates else "1-on-1"
    class_group = intake_month + "-" + career_path

    student = {
        "student_id": student_id,
        "name": name,
        "phone": phone,
        "email": email,
        "career_path": career_path,
        "course_name": course_name or career_path,
        "experience_level": experience_level,
        "track": track or "",
        # Daily live classes run Mon-Sun at the hour the student chose on the
        # registration form (WAT). The dashboard timetable builds around this.
        "preferred_time": preferred_time or "18:00",
        # Per-day class times the student chose at registration
        # ( {"Monday":"18:00","Tuesday":"14:00","Wednesday":"","Saturday":"09:00",...} ).
        # Days left blank / "none" have no class.
        "preferred_daily_times": preferred_daily_times if isinstance(preferred_daily_times, dict) else None,
        "goals": list(goals or []),
        "duration_months": int(duration_months) if duration_months else None,
        "class_minutes": int(class_minutes or 60),
        "intake_month": intake_month,
        "class_type": class_type,
        "class_group": class_group,
        "enrolled_date": datetime.now().isoformat(),
        "payment_status": "paid",
        "current_month": 1,
        "current_topic_index": 0,
        "classes_attended": 0,
        "classes_missed": 0,
        "total_classes": 0,
        "assignments_submitted": 0,
        "assignments_missed": 0,
        "avg_quiz_score": 0,
        "avg_assignment_score": 0,
        "overall_grade": "N/A",
        "last_interaction": datetime.now().isoformat(),
        "mood": "excited",
        "personal_notes": "",
        "certificate_issued": False,
    }
    for key, value in (extra_fields or {}).items():
        if value not in (None, "", []):
            student[key] = value

    if db:
        try:
            db.table("students").insert(student).execute()
            for classmate_id in classmates:
                db.table("students").update({"class_type": "group"}).eq(
                    "student_id", classmate_id).execute()
        except Exception as e:
            print(f"[ERROR] Enrollment failed: {e}")
            # Resilient fallback: if PostgreSQL rejects the record (e.g. the
            # `preferred_daily_times` column has not been added to the schema
            # yet, or PostgreSQL is unreachable), persist locally and return the
            # student anyway so a fresh registration is never lost.
            # get_student() already falls back to this same local store when
            # PostgreSQL has no record.
            try:
                students[student_id] = student
                for classmate_id in classmates:
                    mate = students.get(classmate_id)
                    if isinstance(mate, dict):
                        mate["class_type"] = "group"
                _students_file_save(students)
            except Exception as e2:
                print(f"[ERROR] Local fallback also failed: {e2}")
                return None
    else:
        students[student_id] = student
        for classmate_id in classmates:
            mate = students.get(classmate_id)
            if isinstance(mate, dict):
                mate["class_type"] = "group"
        save_students(students)

    print(f"[YES] Student enrolled: {student_id}")
    print(f"   Name:        {name}")
    print(f"   Career Path: {career_path}")
    print(f"   Course:      {student.get('course_name')}")
    print(f"   Class Type:  {class_type}")
    print(f"   Classmates:  {len(classmates)}")

    return student


def get_student(student_id):
    """Get a student by ID: PostgreSQL when configured, local JSON otherwise."""
    if db:
        try:
            response = db.table("students").select("*").eq("student_id", student_id).execute()
            if response.data and len(response.data) > 0:
                student = response.data[0]

                # Load related records
                attendance_resp = db.table("attendance_records").select("*").eq("student_id", student_id).execute()
                quiz_resp = db.table("quiz_records").select("*").eq("student_id", student_id).execute()
                assignment_resp = db.table("assignment_records").select("*").eq("student_id", student_id).execute()

                student["attendance_records"] = attendance_resp.data if attendance_resp.data else []
                student["quiz_records"] = quiz_resp.data if quiz_resp.data else []
                student["assignment_records"] = assignment_resp.data if assignment_resp.data else []

                # Cross-store merge: while the PostgreSQL schema lacks the newer
                # columns, those fields live only in the local JSON store.
                # Overlay them so the dashboard/roadmap always receive the
                # student's per-day schedule AND paid access window no matter
                # which store won.
                try:
                    _overlay_local_payment([student])
                except Exception:
                    pass
                try:
                    _overlay_local_attendance(student)
                except Exception:
                    pass

                return student
        except Exception as e:
            print(f"[ERROR] Failed to get student {student_id} from PostgreSQL: {e}")

    # Local fallback (also used when PostgreSQL errors)
    record = _students_file_load().get(student_id)
    if record:
        record = dict(record)
        record.setdefault("attendance_records", [])
        record.setdefault("quiz_records", [])
        record.setdefault("assignment_records", [])
        _overlay_local_attendance(record)
        return record
    return None


def get_student_by_phone(phone):
    """Get a student by phone number from PostgreSQL."""
    if not db:
        return None
    
    try:
        response = db.table("students").select("*").eq("phone", phone).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None
    except Exception as e:
        print(f"[ERROR] Failed to get student by phone {phone}: {e}")
        return None


def update_student(student_id, updates):
    """Update student record in PostgreSQL."""
    if not db:
        return None
    
    try:
        updates["last_interaction"] = datetime.now().isoformat()
        response = db.table("students").update(updates).eq("student_id", student_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"[ERROR] Failed to update student {student_id}: {e}")
        return None


def get_class_group(career_path, intake_month):
    """Get all students in a class group from PostgreSQL."""
    if not db:
        return []
    
    try:
        response = db.table("students").select("*").eq(
            "career_path", career_path
        ).eq("intake_month", intake_month).eq("payment_status", "paid").execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"[ERROR] Failed to get class group: {e}")
        return []


def _write_text_fallback(output_path: Path, title: str, body: str) -> str:
    output_path.write_text(body, encoding="utf-8")
    return str(output_path)


# ============================================================
# CAREER ROADMAP PDF GENERATION
# ============================================================

def generate_roadmap_pdf(student_id):
    """
    Generate a beautiful career roadmap PDF for a student.
    """
    student = get_student(student_id)
    if not student:
        print(f"[NO] Student {student_id} not found")
        return None

    career_path = student["career_path"]
    filename = f"roadmap_{student_id}_{career_path}.pdf"
    filepath = REPORTS_DIR / filename

    if FPDF is None:
        body = f"BOI RSU Career Roadmap\nStudent: {student['name']}\nCareer Path: {career_path}\n\n"
        roadmap = CAREER_ROADMAPS.get(career_path, {})
        if roadmap:
            body += f"Title: {roadmap.get('title', career_path)}\nDuration: {roadmap.get('duration', 'N/A')}\n\n"
            for month in roadmap.get('monthly_plan', []):
                body += f"Month {month.get('month')}: {month.get('title')}\n"
                for topic in month.get('topics', []):
                    body += f"- {topic}\n"
                body += f"Project: {month.get('project')}\n\n"
        return _write_text_fallback(filepath.with_suffix('.txt'), "BOI RSU Roadmap", body)

    roadmap = CAREER_ROADMAPS.get(career_path)
    if not roadmap:
        print(f"[NO] Roadmap not found for {career_path}")
        return None

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Generating roadmap PDF for {student['name']}...")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cover Page
    pdf.add_page()
    pdf.set_fill_color(20, 20, 60)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_y(60)
    pdf.cell(0, 15, "BOI RSU", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "TECH EDUCATION PLATFORM", ln=True, align="C")

    pdf.set_y(120)
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 15, "CAREER ROADMAP", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, roadmap["title"].upper(), ln=True, align="C")

    pdf.set_y(180)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, f"Prepared for: {student['name']}", ln=True, align="C")
    pdf.cell(0, 10, f"Duration: {roadmap['duration']}", ln=True, align="C")
    pdf.cell(0, 10,
             f"Start Date: {date.today().strftime('%B %d, %Y')}",
             ln=True, align="C")
    pdf.cell(0, 10,
             f"Expected Completion: "
             f"{(date.today() + timedelta(days=180)).strftime('%B %d, %Y')}",
             ln=True, align="C")

    # Introduction Page
    pdf.add_page()
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(20, 20, 60)

    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, f"Your Journey to Becoming a", ln=True)
    pdf.cell(0, 15, roadmap["title"], ln=True)
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 8, roadmap["description"])
    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(20, 20, 60)
    pdf.cell(0, 10, "What You Will Achieve:", ln=True)
    pdf.ln(3)

    achievements = [
        "Master all core concepts in your chosen career path",
        "Build real projects for your portfolio",
        "Learn industry best practices",
        "Be job-ready in 6 months",
        "Earn a BOI RSU certificate"
    ]

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    for achievement in achievements:
        pdf.cell(10, 8, "-")
        pdf.cell(0, 8, achievement, ln=True)
    pdf.ln(10)

    # Monthly Plan Pages
    for month_plan in roadmap["monthly_plan"]:
        pdf.add_page()

        # Month header
        pdf.set_fill_color(20, 20, 60)
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_y(8)
        pdf.cell(0, 12,
                 f"MONTH {month_plan['month']}: "
                 f"{month_plan['title'].upper()}",
                 ln=True, align="C")
        pdf.ln(20)

        # Topics
        pdf.set_text_color(20, 20, 60)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Topics Covered This Month:", ln=True)
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 12)
        pdf.set_text_color(60, 60, 60)
        for i, topic in enumerate(month_plan["topics"], 1):
            pdf.set_fill_color(240, 240, 255)
            pdf.cell(8, 8, f"{i}.", fill=False)
            pdf.cell(0, 8, topic, ln=True)
        pdf.ln(10)

        # Project
        pdf.set_fill_color(255, 245, 200)
        pdf.rect(10, pdf.get_y(), 190, 30, 'F')
        pdf.set_text_color(100, 70, 0)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "  Month Project:", ln=True)
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 8, f"  {month_plan['project']}", ln=True)
        pdf.ln(15)

        # Schedule for the month
        pdf.set_text_color(20, 20, 60)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Weekly Schedule:", ln=True)
        pdf.ln(3)

        weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]
        topics_per_week = len(month_plan["topics"]) // 4 + 1

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        for i, week in enumerate(weeks):
            start = i * topics_per_week
            end = start + topics_per_week
            week_topics = month_plan["topics"][start:end]
            if week_topics:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(30, 7, f"{week}:")
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(0, 7, ", ".join(week_topics), ln=True)

    # Completion & Certificate Page
    pdf.add_page()
    pdf.set_fill_color(20, 100, 20)
    pdf.rect(0, 0, 210, 50, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(15)
    pdf.cell(0, 15, "COURSE COMPLETION", ln=True, align="C")

    pdf.set_y(60)
    pdf.set_text_color(20, 20, 60)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Upon completing this roadmap you will receive:", ln=True)
    pdf.ln(5)

    completions = [
        "BOI RSU Certificate of Completion",
        "Digital badge for LinkedIn profile",
        "Portfolio review and feedback",
        "Career guidance and job referrals",
        "Access to BOI RSU alumni network",
        "1 month free access to advanced courses"
    ]

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    for item in completions:
        pdf.cell(10, 8, "+")
        pdf.cell(0, 8, item, ln=True)

    # Save PDF
    pdf.output(str(filepath))

    print(f"[YES] Roadmap PDF generated: {filename}")
    return str(filepath)


# ============================================================
# TEXTBOOK PDF GENERATION
# ============================================================

def generate_textbook_pdf_legacy(career_path, month_number):
    """
    Generate a detailed textbook PDF for a course month.
    """
    roadmap = CAREER_ROADMAPS.get(career_path)
    if not roadmap:
        return None

    month_plan = roadmap["monthly_plan"][month_number - 1]
    filename = f"textbook_{career_path}_month{month_number}.pdf"
    filepath = TEXTBOOKS_DIR / filename

    if FPDF is None:
        body = f"BOI RSU Textbook\nCareer Path: {career_path}\nMonth: {month_number}\nTitle: {month_plan['title']}\n\nTopics:\n"
        for topic in month_plan.get('topics', []):
            body += f"- {topic}\n"
        body += f"\nProject: {month_plan.get('project')}\n"
        return _write_text_fallback(filepath.with_suffix('.txt'), "BOI RSU Textbook", body)

    # ---- AI-WRITTEN BOOK (expert technical-writer pipeline) ----
    # textbook_ai asks the tutor model chain to actually write the month and
    # renders it to the A4 layout spec (cover, real TOC page numbers, chapter
    # per page, shaded code boxes, header/footer). It returns None on any
    # failure (no key, unreachable model, unusable output, BOIRSU_AI_TEXTBOOK=0)
    # and the template path below still produces a book, so this never breaks.
    try:
        import textbook_ai
        ai_path = textbook_ai.build_ai_textbook(
            career_path, month_number, filepath,
            roadmap=roadmap, month_plan=month_plan)
        if ai_path:
            return ai_path
    except Exception as exc:
        print(f"[boirsu] AI textbook path failed ({str(exc)[:140]}); "
              f"continuing with the template generator.")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Generating textbook for Month {month_number}: "
          f"{month_plan['title']}...")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Core PDF fonts (Helvetica) only encode latin-1. Roadmap titles, topics
    # and AI quiz text routinely contain em dashes / curly quotes, which used
    # to kill generation mid-book with FPDFUnicodeEncodingException. Route
    # EVERY string entering cell()/multi_cell() through a latin-1-safe shim.
    def _pdf_safe(s):
        return s.encode("latin-1", "replace").decode("latin-1") if isinstance(s, str) else s

    _raw_cell, _raw_multi_cell = pdf.cell, pdf.multi_cell

    def _safe_cell(*args, **kwargs):
        args = tuple(_pdf_safe(x) if isinstance(x, str) else x for x in args)
        kwargs = {k: _pdf_safe(v) if isinstance(v, str) else v for k, v in kwargs.items()}
        return _raw_cell(*args, **kwargs)

    def _safe_multi_cell(*args, **kwargs):
        args = tuple(_pdf_safe(x) if isinstance(x, str) else x for x in args)
        kwargs = {k: _pdf_safe(v) if isinstance(v, str) else v for k, v in kwargs.items()}
        return _raw_multi_cell(*args, **kwargs)

    pdf.cell = _safe_cell
    pdf.multi_cell = _safe_multi_cell

    # Cover
    pdf.add_page()
    pdf.set_fill_color(10, 50, 100)
    pdf.rect(0, 0, 210, 297, 'F')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_y(50)
    pdf.cell(0, 15, "BOI RSU TECH EDUCATION", ln=True, align="C")

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, roadmap["title"].upper(), ln=True, align="C")

    pdf.set_y(120)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 15,
             f"MONTH {month_number} TEXTBOOK",
             ln=True, align="C")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, month_plan["title"].upper(), ln=True, align="C")

    pdf.set_y(200)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8,
             f"Published: {date.today().strftime('%B %Y')}",
             ln=True, align="C")
    pdf.cell(0, 8, "DevSphere AI Learning Platform",
             ln=True, align="C")

    # Table of Contents
    pdf.add_page()
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(10, 50, 100)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 15, "TABLE OF CONTENTS", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    for i, topic in enumerate(month_plan["topics"], 1):
        pdf.cell(10, 8, f"{i}.")
        pdf.cell(0, 8, topic, ln=True)
    pdf.ln(5)
    pdf.cell(0, 8,
             f"{len(month_plan['topics']) + 1}. "
             f"Month Project: {month_plan['project']}",
             ln=True)
    pdf.cell(0, 8,
             f"{len(month_plan['topics']) + 2}. Quiz & Practice Questions",
             ln=True)

    # Chapter for each topic
    for i, topic in enumerate(month_plan["topics"], 1):
        pdf.add_page()

        # Chapter header
        pdf.set_fill_color(10, 50, 100)
        pdf.rect(0, 0, 210, 35, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_y(8)
        pdf.cell(0, 10, f"Chapter {i}", ln=True, align="C")
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, topic, ln=True, align="C")
        pdf.ln(15)

        pdf.set_text_color(10, 50, 100)

        # Introduction
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Introduction", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 7,
            f"In this chapter we will explore {topic} in detail. "
            f"This is a fundamental concept in {roadmap['title']} "
            f"that you will use throughout your career. "
            f"By the end of this chapter you will have a solid "
            f"understanding of {topic} and be able to apply it "
            f"confidently in real projects.")
        pdf.ln(8)

        # Learning Objectives
        pdf.set_text_color(10, 50, 100)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Learning Objectives", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        objectives = [
            f"Understand the core concepts of {topic}",
            f"Apply {topic} in practical examples",
            f"Identify common mistakes and how to avoid them",
            f"Connect {topic} to other concepts you have learned",
            f"Build confidence using {topic} in real projects"
        ]

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        for obj in objectives:
            pdf.cell(8, 7, "-")
            pdf.cell(0, 7, obj, ln=True)
        pdf.ln(8)

        # Core Concepts
        pdf.set_text_color(10, 50, 100)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Core Concepts", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 7,
            f"{topic} is one of the most important concepts in "
            f"{roadmap['title']}. Understanding it deeply will "
            f"help you build better, more efficient solutions. "
            f"Professionals in this field use {topic} daily and "
            f"mastering it will set you apart from others.")
        pdf.ln(8)

        # Key Terms
        pdf.set_text_color(10, 50, 100)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 10, "Key Terms & Definitions", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        key_terms = [
            f"{topic} — The main concept covered in this chapter",
            "Implementation — How you apply the concept in code",
            "Best Practice — The recommended way to use the concept",
            "Use Case — Real world scenarios where this is applied",
            "Common Error — Mistakes beginners often make"
        ]
        for term in key_terms:
            pdf.set_font("Helvetica", "B", 11)
            parts = term.split(" — ")
            pdf.cell(0, 7, f"- {parts[0]}", ln=True)
            if len(parts) > 1:
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(8, 6, "")
                pdf.cell(0, 6, parts[1], ln=True)
        pdf.ln(8)

        # Practice Section
        pdf.set_fill_color(240, 248, 255)
        pdf.rect(10, pdf.get_y(), 190, 35, 'F')
        pdf.set_text_color(10, 50, 100)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "  Practice Exercise", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 7,
            f"  Try to apply what you learned about {topic} "
            f"by completing the exercises given in class. "
            f"Practice is the only way to truly master this concept.")
        pdf.ln(15)

        # Quiz for this topic
        pdf.add_page()
        pdf.set_fill_color(20, 80, 20)
        pdf.rect(0, 0, 210, 30, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_y(8)
        pdf.cell(0, 12, f"Chapter {i} Quiz — {topic}", ln=True, align="C")
        pdf.ln(15)

        pdf.set_text_color(10, 50, 100)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8,
                 "Answer these questions to test your understanding:",
                 ln=True)
        pdf.ln(5)

        quiz = generate_quiz(topic, career_path)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(60, 60, 60)

        for j, q in enumerate(quiz[:5], 1):
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(10, 50, 100)
            pdf.multi_cell(0, 7, f"Q{j}. {q['q']}")
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(60, 60, 60)
            for opt in q["options"]:
                pdf.cell(8, 6, "")
                pdf.cell(0, 6, opt, ln=True)
            pdf.ln(3)

        # Answer Key
        pdf.ln(5)
        pdf.set_fill_color(255, 250, 220)
        pdf.rect(10, pdf.get_y(), 190, 8, 'F')
        pdf.set_text_color(100, 70, 0)
        pdf.set_font("Helvetica", "B", 11)
        answers = " | ".join([f"Q{j}: {q['answer']}"
                              for j, q in enumerate(quiz[:5], 1)])
        pdf.cell(0, 8, f"  Answers: {answers}", ln=True)

    # Project Page
    pdf.add_page()
    pdf.set_fill_color(200, 50, 50)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_y(12)
    pdf.cell(0, 15, "MONTH PROJECT", ln=True, align="C")
    pdf.ln(20)

    pdf.set_text_color(10, 50, 100)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, month_plan["project"], ln=True)
    pdf.ln(5)

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 7,
        f"This month's project will test everything you have learned "
        f"about {month_plan['title']}. Take your time, do your research, "
        f"and build something you are proud of. "
        f"Your project will be reviewed by the AI teacher and you will "
        f"receive detailed feedback to help you improve.")
    pdf.ln(10)

    requirements = [
        "Complete all topics before starting the project",
        "Apply concepts learned throughout the month",
        "Write clean, well-organised code or designs",
        "Submit via WhatsApp before the deadline",
        "Include a brief explanation of what you built"
    ]

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(10, 50, 100)
    pdf.cell(0, 8, "Requirements:", ln=True)
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    for req in requirements:
        pdf.cell(8, 7, "-")
        pdf.cell(0, 7, req, ln=True)

    # Save textbook
    pdf.output(str(filepath))

    print(f"[YES] Textbook generated: {filename}")
    return str(filepath)


# ============================================================
# CERTIFICATE GENERATION
# ============================================================

def generate_certificate(student_id):
    """Generate a completion certificate for a student."""
    student = get_student(student_id)
    if not student:
        return None

    career_path = student["career_path"]
    filename = f"certificate_{student_id}_{career_path}.pdf"
    filepath = CERTS_DIR / filename

    if FPDF is None:
        body = f"BOI RSU Certificate\nStudent: {student['name']}\nCareer Path: {career_path}\nGrade: {student.get('overall_grade', 'A')}\n"
        return _write_text_fallback(filepath.with_suffix('.txt'), "BOI RSU Certificate", body)
    roadmap = CAREER_ROADMAPS.get(career_path, {})

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Generating certificate for {student['name']}...")

    pdf = FPDF(orientation='L')
    pdf.add_page()

    # Background
    pdf.set_fill_color(245, 245, 220)
    pdf.rect(0, 0, 297, 210, 'F')

    # Border
    pdf.set_draw_color(10, 50, 100)
    pdf.set_line_width(3)
    pdf.rect(10, 10, 277, 190)
    pdf.set_line_width(1)
    pdf.rect(13, 13, 271, 184)

    # Header
    pdf.set_text_color(10, 50, 100)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_y(25)
    pdf.cell(0, 15, "BOI RSU TECH EDUCATION", ln=True, align="C")

    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 8, "Certificate of Completion", ln=True, align="C")

    # Body
    pdf.set_y(65)
    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10, "This is to certify that", ln=True, align="C")

    pdf.set_text_color(10, 50, 100)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(0, 15, student["name"].upper(), ln=True, align="C")

    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Helvetica", "", 14)
    pdf.cell(0, 10,
             "has successfully completed the course",
             ln=True, align="C")

    pdf.set_text_color(200, 50, 50)
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12,
             roadmap.get("title", career_path).upper(),
             ln=True, align="C")

    pdf.set_text_color(60, 60, 60)
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8,
             f"Duration: {roadmap.get('duration', '6 months')} | "
             f"Grade: {student.get('overall_grade', 'A')} | "
             f"Attendance: {student.get('classes_attended', 0)} classes",
             ln=True, align="C")

    # Date and signature
    pdf.set_y(160)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(80, 8,
             f"Date: {date.today().strftime('%B %d, %Y')}",
             align="C")
    pdf.cell(137, 8,
             f"Student ID: {student_id}",
             ln=True, align="C")

    pdf.set_y(175)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(148, 8, "_________________________", align="C")
    pdf.cell(149, 8, "_________________________", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(148, 6, "BOI RSU Director", align="C")
    pdf.cell(149, 6, "AI Programme Coordinator", ln=True, align="C")

    # Save certificate
    pdf.output(str(filepath))

    # Update student record
    update_student(student_id, {"certificate_issued": True})

    print(f"[YES] Certificate generated: {filename}")
    return str(filepath)


# ============================================================
# JITSI CLASS MANAGEMENT
# ============================================================

def create_jitsi_room(career_path, intake_month, class_number):
    """
    Create a Jitsi meeting room for a class.
    Returns the meeting URL.
    """
    room_name = (f"BOIRSU-{career_path}-{intake_month}-"
                 f"Class{class_number}").replace(" ", "-")
    jitsi_url = f"https://meet.jit.si/{room_name}"

    print(f"\n[YES] Jitsi Room Created: {jitsi_url}")
    return jitsi_url


def mark_attendance(student_id, class_number, attended, joined_at=None):
    """Mark attendance for a student.

    Tries PostgreSQL first (insert into `attendance_records` + bump the student
    counters). If that fails � the table's row-level security policy may block
    inserts (42501), PostgreSQL may be offline, or the column set differs � it
    falls back to the local JSON store so a class is NEVER lost and the
    roadmap auto-completion (which reads `classes_attended`) keeps working.
    Returns the updated student record (from whichever store succeeded).
    """
    student = get_student(student_id)
    if not student:
        return {"ok": False, "error": "unknown student"}
    joined_at = joined_at or datetime.now().isoformat()
    today = date.today().isoformat()
    attendance_record = {
        "student_id": student_id,
        "class_number": int(class_number),
        "attended": bool(attended),
        "joined_at": joined_at,
        "date": today,
    }

    def _apply_local():
        store = _students_file_load()
        rec = store.get(student_id)
        if not isinstance(rec, dict):
            rec = dict(student)
            store[student_id] = rec
        rec.setdefault("attendance_records", []).append(attendance_record)
        if attended:
            rec["classes_attended"] = int(rec.get("classes_attended") or 0) + 1
        else:
            rec["classes_missed"] = int(rec.get("classes_missed") or 0) + 1
        rec["total_classes"] = int(rec.get("total_classes") or 0) + 1
        total = int(rec["total_classes"])
        att = int(rec.get("classes_attended") or 0)
        rec["attendance_rate"] = round((att / total) * 100) if total else 0
        _students_file_save(store)
        return rec

    if not db:
        return _apply_local()

    try:
        db.table("attendance_records").insert(attendance_record).execute()

        updates = {}
        if attended:
            updates["classes_attended"] = int(student.get("classes_attended") or 0) + 1
        else:
            updates["classes_missed"] = int(student.get("classes_missed") or 0) + 1
        updates["total_classes"] = int(student.get("total_classes") or 0) + 1

        # Calculate attendance rate
        total = updates["total_classes"]
        attended_count = updates.get("classes_attended", int(student.get("classes_attended") or 0))
        updates["attendance_rate"] = round((attended_count / total) * 100) if total > 0 else 0

        updated = update_student(student_id, updates)
        if updated:
            return updated
        # update_student returned nothing � mirror locally below.
    except Exception as e:
        print(f"[WARN] PostgreSQL attendance insert failed ({e}) � recording locally")

    return _apply_local()


def record_quiz_score(student_id, topic, score, total_questions):
    """Record a quiz score for a student using PostgreSQL."""
    if not db:
        return None
    
    try:
        student = get_student(student_id)
        if not student:
            return None

        # Insert quiz record
        quiz_record = {
            "student_id": student_id,
            "topic": topic,
            "score": score,
            "total_questions": total_questions,
            "percentage": round((score / total_questions) * 100) if total_questions > 0 else 0,
        }
        
        db.table("quiz_records").insert(quiz_record).execute()

        # Update average
        quiz_resp = db.table("quiz_records").select("percentage").eq("student_id", student_id).execute()
        all_scores = [q["percentage"] for q in quiz_resp.data] if quiz_resp.data else []
        avg_score = round(sum(all_scores) / len(all_scores)) if all_scores else 0

        # Update grade based on average
        if avg_score >= 90:
            grade = "A"
        elif avg_score >= 80:
            grade = "B"
        elif avg_score >= 70:
            grade = "C"
        elif avg_score >= 60:
            grade = "D"
        else:
            grade = "F"

        updates = {
            "avg_quiz_score": avg_score,
            "overall_grade": grade,
            "cgpa": round((avg_score / 100) * 4.0, 2)  # Convert to GPA scale
        }

        return update_student(student_id, updates)
    except Exception as e:
        print(f"[ERROR] Failed to record quiz score: {e}")
        return None


def submit_assignment(student_id, assignment_number,
                      submission_text, score=None):
    """Record an assignment submission using PostgreSQL."""
    if not db:
        return None
    
    try:
        student = get_student(student_id)
        if not student:
            return None

        # Insert assignment record
        assignment_record = {
            "student_id": student_id,
            "assignment_number": assignment_number,
            "submission_file": submission_text[:500],
            "score": score,
            "submitted_on": datetime.now().isoformat(),
        }

        db.table("assignment_records").insert(assignment_record).execute()
        
        updates = {
            "assignments_submitted": student.get("assignments_submitted", 0) + 1
        }
        
        result = update_student(student_id, updates)
        print(f"[YES] Assignment {assignment_number} submitted by {student['name']}")
        return result
    except Exception as e:
        print(f"[ERROR] Failed to submit assignment: {e}")
        return None


# ============================================================
# WHATSAPP MESSAGING
# ============================================================

def send_whatsapp(phone, message):
    """Send a WhatsApp message via OpenClaw."""
    try:
        result = subprocess.run([
            "openclaw", "msg", "send",
            "--channel", "whatsapp",
            "--to", phone,
            "--text", message
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"[YES] WhatsApp sent to {phone}")
            return True
        else:
            print(f"[NO] WhatsApp failed: {result.stderr[:100]}")
            return False
    except Exception as e:
        print(f"[NO] WhatsApp error: {e}")
        return False


def send_whatsapp_admin(message):
    """Send a private message to Daniel only."""
    if not ADMIN_PHONE:
        print("[NO] BOIRSU_ADMIN_PHONE not set in .env")
        return False
    return send_whatsapp(ADMIN_PHONE, message)


# ============================================================
# AI FRIEND — DAILY INTERACTIONS
# ============================================================

MORNING_MESSAGES = [
    "Good morning {name}!  Hope you slept well. "
    "Ready for another day of learning? "
    "You're doing amazing on your {course} journey! ",

    "Hey {name}!  Good morning! "
    "Just wanted to check in and see how you're doing today. "
    "How are you feeling?",

    "Morning {name}!  "
    "We have class tonight at 7pm — "
    "you're going to love what we're covering today! "
    "How has your week been so far?"
]

MOTIVATION_MESSAGES = [
    "Hey {name}!  Just a quick thought — "
    "every expert was once a beginner. "
    "You're making real progress and I'm proud of you! ",

    "{name}, I've been thinking about your progress — "
    "you've come so far already! "
    "Keep going, you're closer than you think. ",

    "Hey {name}!  "
    "Did you know that most successful tech professionals "
    "felt exactly like you do right now when they started? "
    "Trust the process!"
]

TECH_TIPS = [
    " Tech Tip: The best way to learn coding is to build things. "
    "Don't just read — write code every single day!",

    " Did you know? Google, Facebook and Twitter were all "
    "built by self-taught developers. Your journey is valid! ",

    " Pro Tip: When you're stuck on a problem, explain it out loud "
    "to yourself. This is called rubber duck debugging and it works! ",

    " Career Insight: 73% of tech jobs don't require a degree. "
    "Skills and portfolio matter more than certificates in tech! "
]

WEEKEND_MESSAGES = [
    "Happy weekend {name}!  "
    "No class today but that doesn't mean we stop learning! "
    "Even 30 minutes of practice makes a huge difference. "
    "Enjoy your rest too — you've earned it! ",

    "Hey {name}! Weekend vibes!  "
    "Just wanted to say your dedication this week has been amazing. "
    "Take some time to rest and come back stronger on Monday! "
]


def send_morning_checkin():
    """Send morning check-in to all active students."""
    if not db:
        print("[WARN] PostgreSQL not available")
        return
    
    try:
        response = db.table("students").select("student_id, name, phone, career_path, payment_status").eq("payment_status", "paid").execute()
        students = response.data if response.data else []
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
              f"Sending morning check-ins to {len(students)} students...")

        for student in students:
            if student.get("payment_status") != "paid":
                continue

            career_path = student.get("career_path", "")
            roadmap = CAREER_ROADMAPS.get(career_path, {})
            course_title = roadmap.get("title", "your course")

            message = random.choice(MORNING_MESSAGES).format(
                name=student["name"].split()[0],
                course=course_title
            )
            send_whatsapp(student["phone"], message)
    except Exception as e:
        print(f"[ERROR] Failed to send morning checkins: {e}")

        # Add class reminder if class day
        today = datetime.now().strftime("%A")
        if today in ["Monday", "Tuesday", "Wednesday", "Thursday"]:
            message += (f"\n\n Reminder: Class tonight at 7pm WAT! "
                       f"See you there!")

        send_whatsapp(student["phone"], message)

    print(f"[YES] Morning check-ins sent to {len(students)} students")


def send_class_reminder(career_path, intake_month):
    """Send 1 hour class reminder to all students in a group."""
    group = get_class_group(career_path, intake_month)

    for student in group:
        roadmap = CAREER_ROADMAPS.get(career_path, {})
        current_month = student.get("current_month", 1)
        month_plan = roadmap.get("monthly_plan", [{}])
        if current_month <= len(month_plan):
            topic = month_plan[current_month - 1].get("title", "tonight's lesson")
        else:
            topic = "tonight's lesson"

        message = (
            f"Hey {student['name'].split()[0]}! 🕖 "
            f"Class starts in 1 HOUR!\n\n"
            f"Tonight's topic: *{topic}*\n\n"
            f"Make sure you:\n"
            f"[YES] Have your laptop/device ready\n"
            f"[YES] Find a quiet place\n"
            f"[YES] Have good internet connection\n\n"
            f"See you at 7pm sharp! "
        )
        send_whatsapp(student["phone"], message)


def send_class_link(career_path, intake_month, class_number):
    """Send Jitsi class link to all students."""
    group = get_class_group(career_path, intake_month)
    jitsi_url = create_jitsi_room(career_path, intake_month, class_number)

    for student in group:
        message = (
            f" *Class Starting Now!*\n\n"
            f"Hi {student['name'].split()[0]}! "
            f"Your class is starting!\n\n"
            f"👇 Click to join:\n"
            f"{jitsi_url}\n\n"
            f"See you inside! "
        )
        send_whatsapp(student["phone"], message)

    return jitsi_url


def send_class_notes_and_assignment(career_path, intake_month,
                                    class_number, topic, assignment_text):
    """Send class notes, quiz and assignment after class."""
    group = get_class_group(career_path, intake_month)

    # Generate textbook/notes
    current_month = group[0].get("current_month", 1) if group else 1
    notes_path = generate_textbook_pdf(career_path, current_month)

    # Generate quiz
    quiz = generate_quiz(topic, career_path)

    for student in group:
        # Send notes
        notes_message = (
            f" *Class {class_number} Notes*\n\n"
            f"Great class tonight {student['name'].split()[0]}! "
            f"Here are your notes and materials.\n\n"
            f"Topic covered: *{topic}*\n\n"
            f"Your detailed textbook has been sent separately. "
            f"Make sure to read through it before next class!"
        )
        send_whatsapp(student["phone"], notes_message)

        # Send quiz
        quiz_message = f" *Quick Quiz — {topic}*\n\n"
        for i, q in enumerate(quiz[:3], 1):
            quiz_message += f"Q{i}: {q['q']}\n"
            for opt in q["options"]:
                quiz_message += f"{opt}\n"
            quiz_message += "\n"
        quiz_message += "Reply with your answers! e.g. 1:A, 2:C, 3:B"
        send_whatsapp(student["phone"], quiz_message)

        # Send assignment
        assignment_message = (
            f" *Assignment {class_number}*\n\n"
            f"{assignment_text}\n\n"
            f"📅 Deadline: Tomorrow by 7pm WAT\n\n"
            f"Submit by replying to this message with your work!\n"
            f"Good luck! You've got this "
        )
        send_whatsapp(student["phone"], assignment_message)

    print(f"[YES] Notes and assignments sent to {len(group)} students")


def check_on_absent_students(career_path, intake_month, class_number):
    """Send messages to students who missed class."""
    group = get_class_group(career_path, intake_month)

    for student in group:
        attendance = student.get("attendance_records", [])
        last_class = next(
            (a for a in reversed(attendance)
             if a["class_number"] == class_number), None)

        if last_class and not last_class["attended"]:
            message = (
                f"Hey {student['name'].split()[0]}!  "
                f"We missed you in class today!\n\n"
                f"Hope everything is okay. "
                f"Don't worry — I've sent you the notes and "
                f"recording so you don't miss anything.\n\n"
                f"Is everything alright? "
                f"Let me know if you need anything! "
            )
            send_whatsapp(student["phone"], message)


def send_weekly_progress_report(student_id):
    """Send weekly progress report to a student."""
    student = get_student(student_id)
    if not student:
        return

    career_path = student["career_path"]
    roadmap = CAREER_ROADMAPS.get(career_path, {})

    total_months = len(roadmap.get("monthly_plan", []))
    current_month = student.get("current_month", 1)
    progress_pct = round((current_month / total_months) * 100)

    message = (
        f" *Your Weekly Progress Report*\n\n"
        f"Hi {student['name'].split()[0]}! "
        f"Here's how you're doing:\n\n"
        f" Course: {roadmap.get('title', career_path)}\n"
        f" Progress: {progress_pct}% complete\n"
        f"[YES] Classes Attended: {student.get('classes_attended', 0)}\n"
        f"[NO] Classes Missed: {student.get('classes_missed', 0)}\n"
        f" Avg Quiz Score: {student.get('avg_quiz_score', 0)}%\n"
        f" Assignments Done: "
        f"{student.get('assignments_submitted', 0)}\n"
        f" Current Grade: {student.get('overall_grade', 'N/A')}\n\n"
    )

    # Add personalised message based on performance
    avg_quiz = student.get("avg_quiz_score", 0)
    attendance_rate = student.get("attendance_rate", 0)

    if avg_quiz >= 80 and attendance_rate >= 80:
        message += (
            f" You're absolutely crushing it! "
            f"Keep up this incredible work!\n\n"
        )
    elif avg_quiz >= 60:
        message += (
            f" You're making solid progress! "
            f"A little more consistency and you'll be unstoppable!\n\n"
        )
    else:
        message += (
            f" I believe in you! "
            f"Let's work together to improve. "
            f"Message me anytime you need help!\n\n"
        )

    message += f"Keep going — you're {100 - progress_pct}% away from your certificate! "
    send_whatsapp(student["phone"], message)


def send_random_motivation():
    """Send random motivation to all students."""
    if not db:
        print("[WARN] PostgreSQL not available")
        return
    
    try:
        response = db.table("students").select("student_id, name, phone, payment_status").eq("payment_status", "paid").execute()
        students = response.data if response.data else []
        
        today = datetime.now().strftime("%A")

        for student in students:
            if student.get("payment_status") != "paid":
                continue

            if today in ["Saturday", "Sunday"]:
                message = random.choice(WEEKEND_MESSAGES).format(
                    name=student["name"].split()[0])
            else:
                # Mix of motivation and tech tips
                if random.random() > 0.5:
                    message = random.choice(MOTIVATION_MESSAGES).format(
                        name=student["name"].split()[0])
                else:
                    message = random.choice(TECH_TIPS)

            send_whatsapp(student["phone"], message)
    except Exception as e:
        print(f"[ERROR] Failed to send motivation: {e}")


# ============================================================
# PAYMENT INTEGRATION
# ============================================================

def create_enrollment_payment_link(student_name, email, career_path):
    """Create a Paystack payment link for course enrollment."""
    if not PAYSTACK_SECRET_KEY:
        print("[NO] PAYSTACK_SECRET_KEY not set")
        return None

    roadmap = CAREER_ROADMAPS.get(career_path, {})
    course_title = roadmap.get("title", career_path)
    amount_naira = 50000
    reference = f"BOIRSU-{career_path}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "email": email,
        "amount": amount_naira * 100,
        "currency": "NGN",
        "reference": reference,
        "metadata": {
            "student_name": student_name,
            "career_path": career_path,
            "course_title": course_title
        },
        "callback_url": "https://boirsu.com/payment-success"
    }

    try:
        r = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers=headers, json=payload, timeout=15)
        result = r.json()
        if result.get("status"):
            url = result["data"]["authorization_url"]
            print(f"[YES] Payment link: {url}")
            return url, reference
        print(f"[NO] Paystack error: {result.get('message')}")
        return None, None
    except Exception as e:
        print(f"[NO] Payment error: {e}")
        return None, None


def verify_enrollment_payment(reference):
    """Verify course payment."""
    if not PAYSTACK_SECRET_KEY:
        return False

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    try:
        r = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers=headers, timeout=15)
        result = r.json()
        if (result.get("status") and
                result["data"]["status"] == "success"):
            print(f"[YES] Payment confirmed!")
            return True
        return False
    except Exception as e:
        print(f"[NO] Verify error: {e}")
        return False


# ============================================================
# ADMIN REPORTS — PRIVATE TO DANIEL ONLY
# ============================================================

def send_admin_daily_report():
    """Send private daily report to Daniel."""
    if not db:
        print("[WARN] PostgreSQL not available")
        return
    
    try:
        response = db.table("students").select("*").execute()
        students = response.data if response.data else []
        now = datetime.now()
        today = date.today().isoformat()

        total_students = len(students)
        active_students = len([s for s in students.values()
                          if s.get("payment_status") == "paid"])
        today_joined = len([s for s in students.values()
                       if s.get("enrolled_date", "").startswith(today)])

        # Group by career path
        paths = {}
        for s in students.values():
            path = s.get("career_path", "unknown")
            paths[path] = paths.get(path, 0) + 1

        report = (
        f" *BOI RSU — PRIVATE DAILY REPORT*\n"
        f"{now.strftime('%A, %B %d, %Y — %I:%M %p')}\n\n"
        f" *STUDENTS*\n"
        f"Total Enrolled: {total_students}\n"
        f"Active: {active_students}\n"
        f"New Today: {today_joined}\n\n"
        f" *BY CAREER PATH*\n"
        )

        for path, count in paths.items():
            roadmap = CAREER_ROADMAPS.get(path, {})
            title = roadmap.get("title", path)
            report += f"- {title}: {count} students\n"

        report += (
        f"\n *REVENUE*\n"
        f"Monthly Target: ₦{active_students * 50000:,}\n\n"
        f"_ Private — Daniel only_"
        )

        send_whatsapp_admin(report)
    except Exception as e:
        print(f"[ERROR] Failed to send admin daily report: {e}")


# ============================================================
# AVAILABLE COURSES DISPLAY
# ============================================================

def show_available_courses():
    """Display all available career paths."""
    print(f"\n{'='*60}")
    print(f"BOI RSU — AVAILABLE CAREER PATHS")
    print(f"{'='*60}\n")

    for key, roadmap in CAREER_ROADMAPS.items():
        print(f" {roadmap['title']}")
        print(f"   Duration: {roadmap['duration']}")
        print(f"   Fee: ₦50,000/month")
        print(f"   {roadmap['description']}")
        print(f"   Topics per month: "
              f"{len(roadmap['monthly_plan'][0]['topics'])}")
        print()


def show_student_list():
    """Display all enrolled students."""
    students = load_students()
    print(f"\n{'='*60}")
    print(f"BOI RSU — ENROLLED STUDENTS ({len(students)})")
    print(f"{'='*60}\n")

    for student in students.values():
        roadmap = CAREER_ROADMAPS.get(
            student.get("career_path", ""), {})
        print(f" {student['name']} ({student['student_id']})")
        print(f"   Course: {roadmap.get('title', 'N/A')}")
        print(f"   Class: {student.get('class_type', 'N/A')}")
        print(f"   Progress: Month {student.get('current_month', 1)}/6")
        print(f"   Attendance: {student.get('attendance_rate', 0)}%")
        print(f"   Grade: {student.get('overall_grade', 'N/A')}")
        print()


# ============================================================
# SCHEDULER — AUTOMATED DAILY TASKS
# ============================================================

def run_scheduler():
    """Run the automated scheduler for daily tasks."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
          f"Starting BOI RSU Scheduler...")

    # Morning check-ins at 8am
    schedule.every().day.at("08:00").do(send_morning_checkin)

    # Random motivation at 12pm
    schedule.every().day.at("12:00").do(send_random_motivation)

    # Class reminders Mon-Thu at 6pm
    for day in ["monday", "tuesday", "wednesday", "thursday"]:
        getattr(schedule.every(), day).at("18:00").do(
            lambda: print("6pm reminder — send class reminders for all groups"))

    # Admin report at 9pm
    schedule.every().day.at("21:00").do(send_admin_daily_report)

    # Weekly progress reports on Sundays at 10am
    def send_weekly_reports():
        if db:
            try:
                resp = db.table("students").select("student_id").execute()
                for row in resp.data:
                    send_weekly_progress_report(row["student_id"])
            except Exception as e:
                print(f"[ERROR] Failed to send weekly reports: {e}")
    
    schedule.every().sunday.at("10:00").do(send_weekly_reports)

    print("[YES] Scheduler started!")
    print("   08:00 — Morning check-ins")
    print("   12:00 — Random motivation/tips")
    print("   18:00 — Class reminders (Mon-Thu)")
    print("   21:00 — Admin daily report")
    print("   Sunday 10:00 — Weekly progress reports")

    while True:
        schedule.run_pending()
        time.sleep(60)


# ============================================================
# AI LEARNING INTEGRATION
# ============================================================

def _load_backend_env_for_child(env: dict) -> dict:
    """Load backend .env files into the child process environment."""
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parents[1]
    candidates = [
        script_dir / ".env.local",
        backend_dir / ".env.local",
        backend_dir / ".env",
        Path.cwd() / ".env.local",
        Path.cwd() / ".env",
    ]

    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value and value[0] in {"'", '"'} and value[-1] == value[0]:
                value = value[1:-1]
            env.setdefault(key, value)
        break

    return env


def _find_ai_learning_script() -> Path:
    """Find the AI learning script beside boirsu.py."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir / "ai_learning.py",
        script_dir / "ai_learning_system_v4.py",
        script_dir / "ai_learning_system_v4 (14).py",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find ai_learning.py or ai_learning_system_v4 script")


def _course_topic_from_roadmap(career_path: str, month_number: int, topic_number: int = 1) -> str:
    """Pick a BOI course topic from CAREER_ROADMAPS for AI lesson generation."""
    roadmap = CAREER_ROADMAPS.get(career_path)
    if not roadmap:
        raise ValueError(f"Unknown career path: {career_path}")

    monthly_plan = roadmap.get("monthly_plan", [])
    if month_number < 1 or month_number > len(monthly_plan):
        raise ValueError(f"Month must be between 1 and {len(monthly_plan)}")

    topics = monthly_plan[month_number - 1].get("topics", [])
    if topic_number < 1 or topic_number > len(topics):
        raise ValueError(f"Topic number must be between 1 and {len(topics)}")

    course_title = roadmap.get("title", career_path)
    month_title = monthly_plan[month_number - 1].get("title", f"Month {month_number}")
    topic = topics[topic_number - 1]
    return f"{course_title} - {month_title} - {topic}"


def get_topic_youtube_recommendations(topic: str, max_results: int = 3):
    """Fetch YouTube recommendations for a BOI course topic using the shared helper."""
    if get_boi_course_videos is None:
        return []
    return get_boi_course_videos(topic, max_results=max_results, student_level="beginner")


def run_ai_learning(topic: str = ""):
    """Launch the AI learning system from BOI RSU management."""
    import sys

    ai_script = _find_ai_learning_script()
    env = _load_backend_env_for_child(os.environ.copy())
    if topic:
        env["AI_LEARNING_TOPIC"] = topic

    if topic:
        videos = get_topic_youtube_recommendations(topic)
        if videos:
            env["BOI_YOUTUBE_TOPIC"] = topic
            env["BOI_YOUTUBE_RECOMMENDATIONS"] = json.dumps(videos[:3])

    print(f"[BOI RSU] Starting AI learning system: {ai_script.name}")
    if topic:
        print(f"[BOI RSU] Lesson topic: {topic}")

    subprocess.run([sys.executable, str(ai_script)], cwd=str(ai_script.parent), env=env, check=False)
# ============================================================
# ENTRY POINT
# ============================================================

COMMANDS = {
    "courses":      show_available_courses,
    "students":     show_student_list,
    "scheduler":    run_scheduler,
    "admin-report": send_admin_daily_report,
    "morning":      send_morning_checkin,
    "motivation":   send_random_motivation,
    "ai-learning":  run_ai_learning,
}

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()

        if cmd in COMMANDS:
            COMMANDS[cmd]()

        elif cmd == "enroll" and len(sys.argv) > 5:
            enroll_student(
                name=sys.argv[2],
                phone=sys.argv[3],
                email=sys.argv[4],
                career_path=sys.argv[5],
                experience_level=sys.argv[6]
                if len(sys.argv) > 6 else "beginner"
            )

        elif cmd == "roadmap" and len(sys.argv) > 2:
            generate_roadmap_pdf(sys.argv[2])

        elif cmd == "textbook" and len(sys.argv) > 3:
            generate_textbook_pdf(sys.argv[2], int(sys.argv[3]))

        elif cmd == "ai-class":
            try:
                if len(sys.argv) == 2:
                    run_ai_learning()
                elif len(sys.argv) >= 4 and sys.argv[2] in CAREER_ROADMAPS and sys.argv[3].isdigit():
                    topic_number = int(sys.argv[4]) if len(sys.argv) > 4 else 1
                    topic = _course_topic_from_roadmap(sys.argv[2], int(sys.argv[3]), topic_number)
                    run_ai_learning(topic)
                else:
                    run_ai_learning(" ".join(sys.argv[2:]))
            except Exception as e:
                print(f"[ERROR] Could not start AI class: {e}")
        elif cmd == "certificate" and len(sys.argv) > 2:
            generate_certificate(sys.argv[2])

        elif cmd == "attendance" and len(sys.argv) > 3:
            mark_attendance(sys.argv[2], int(sys.argv[3]),
                           sys.argv[4].lower() == "true"
                           if len(sys.argv) > 4 else True)

        elif cmd == "quiz-score" and len(sys.argv) > 4:
            record_quiz_score(sys.argv[2], sys.argv[3],
                             int(sys.argv[4]),
                             int(sys.argv[5]) if len(sys.argv) > 5 else 10)

        elif cmd == "submit" and len(sys.argv) > 4:
            submit_assignment(sys.argv[2], int(sys.argv[3]), sys.argv[4])

        elif cmd == "progress" and len(sys.argv) > 2:
            send_weekly_progress_report(sys.argv[2])

        elif cmd == "class-link" and len(sys.argv) > 4:
            send_class_link(sys.argv[2], sys.argv[3], int(sys.argv[4]))

        elif cmd == "jitsi" and len(sys.argv) > 4:
            url = create_jitsi_room(sys.argv[2], sys.argv[3],
                                   int(sys.argv[4]))
            print(f"Class link: {url}")

        else:
            print(f"Unknown command: {cmd}")
            print(f"\nAvailable commands:")
            for c in COMMANDS:
                print(f"  python3 boirsu.py {c}")
            print(f"\n  python3 boirsu.py enroll <name> <phone> <email> <career-path>")
            print(f"  python3 boirsu.py roadmap <student-id>")
            print(f"  python3 boirsu.py textbook <career-path> <month-number>")
            print(f"  python3 boirsu.py ai-class [topic]")
            print(f"  python3 boirsu.py ai-class <career-path> <month-number> [topic-number]")
            print(f"  python3 boirsu.py certificate <student-id>")
            print(f"  python3 boirsu.py attendance <student-id> <class-number> <true/false>")
            print(f"  python3 boirsu.py quiz-score <student-id> <topic> <score> <total>")
            print(f"  python3 boirsu.py submit <student-id> <assignment-number> <text>")
            print(f"  python3 boirsu.py progress <student-id>")
            print(f"  python3 boirsu.py class-link <career-path> <intake-month> <class-number>")
            print(f"  python3 boirsu.py jitsi <career-path> <intake-month> <class-number>")
            print(f"\nCareer paths:")
            for path in CAREER_ROADMAPS.keys():
                print(f"  {path}")
    else:
        show_available_courses()


# ============================================================================
# MONTHLY TEXTBOOKS - the current, timetable-driven engine.
# Defined at the END of this module so this name wins over the legacy
# generator above for every caller (library routes, study notes, CLI).
# ============================================================================

def generate_textbook_pdf(career_path, month_number, class_days=None, tasks=None):
    """Generate (or regenerate) one month's textbook PDF - AI-WRITTEN ONLY.

    The book is written by textbook_ai.build_ai_textbook() using AI_BOOK_PROMPT
    (the expert technical writer + PDF document designer brief). There is
    deliberately NO pre-written/template fallback any more: when the AI engine
    cannot produce the book (no key, model unreachable, output too thin) this
    returns None and the library simply has no book for that month yet -
    students wait until after class (generation fires when the class ends) or
    until the teacher uploads a PDF, which lands in the library instantly.
    """
    roadmap = CAREER_ROADMAPS.get(career_path)
    if not roadmap:
        return None
    plans = roadmap.get("monthly_plan") or []
    if month_number < 1 or month_number > len(plans):
        return None
    month_plan = plans[month_number - 1]
    filepath = TEXTBOOKS_DIR / f"textbook_{career_path}_month{month_number}.pdf"

    try:
        import textbook_ai
        out = textbook_ai.build_ai_textbook(
            career_path, month_number, filepath,
            roadmap=roadmap, month_plan=month_plan)
        if out:
            print(f"[OK] AI textbook: {filepath.name} "
                  f"({os.path.getsize(str(filepath)) // 1024} KB)")
            return str(out)
    except Exception as exc:
        print(f"[WARN] AI textbook engine failed ({exc})")

    print(f"[TEXTBOOK] No book filed for {career_path} month {month_number} - "
          f"it is written automatically after class ends; nothing pre-written "
          f"is served in the meantime.")
    return None


# ============================================================================
# PER-TOPIC READING MATERIAL - the pre-written engine was REMOVED on purpose.
# Topic books used to be stamped out here by textbook_v2/topic_library (fixed
# text written by a coding assistant). The library now carries ONLY real AI
# writing: textbook_ai month books (generate_textbook_pdf above) and the
# post-class W3Schools textbooks, plus teacher-uploaded PDFs.
# ============================================================================
