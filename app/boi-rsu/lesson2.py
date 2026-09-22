"""
BOI RSU - Realistic Curriculum Generator
==========================================
Generates lesson notes and teaching scripts based on
realistic learning timelines (like Udemy/Coursera).
- 3 classes per week (Mon, Wed, Fri)
- Each topic gets multiple weeks based on complexity
- Each class = 1 hour, going deeper each session
"""

import os
import sys
import time
from pathlib import Path
from fpdf import FPDF
from google import genai
from roadmap_helper import fetch_roadmap

def load_env():
    env_file = Path(os.path.expanduser("~/.openclaw-boirsu/.env"))
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

load_env()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
LESSONS_DIR = Path(os.path.expanduser("~/.openclaw-boirsu/workspace/lessons"))
LESSONS_DIR.mkdir(parents=True, exist_ok=True)

client = genai.Client(api_key=GOOGLE_API_KEY)

# ── REALISTIC CURRICULUM MAP ──────────────────────────────
# Each topic gets a number of weeks based on complexity
# 1 week = 3 classes (Mon, Wed, Fri) x 1 hour each
CURRICULUM = {
    "frontend-developer": {
        "title": "Frontend Developer",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Web Foundations",
                "project": "Build your first portfolio website",
                "topics": [
                    {
                        "name": "HTML5 Fundamentals",
                        "weeks": 3,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Introduction to HTML, how the web works, basic document structure, DOCTYPE, html/head/body tags"},
                            {"class": 2, "day": "Wednesday", "focus": "Headings h1-h6, paragraphs, line breaks, horizontal rules, text formatting tags (bold, italic, underline)"},
                            {"class": 3, "day": "Friday", "focus": "Links (anchor tags, href, target), images (img tag, src, alt), absolute vs relative paths"},
                            {"class": 4, "day": "Monday", "focus": "Lists (ordered, unordered, nested lists), description lists, practical exercises"},
                            {"class": 5, "day": "Wednesday", "focus": "Tables (table, tr, td, th, colspan, rowspan), when to use tables"},
                            {"class": 6, "day": "Friday", "focus": "Forms basics (form, input, label, button), input types (text, email, password, number)"},
                            {"class": 7, "day": "Monday", "focus": "Semantic HTML5 elements (header, nav, main, section, article, aside, footer), why semantics matter"},
                            {"class": 8, "day": "Wednesday", "focus": "Audio, video, iframe, figure, figcaption, HTML5 best practices and validation"},
                            {"class": 9, "day": "Friday", "focus": "Full HTML5 project review, common mistakes, debugging HTML, assessment and quiz"}
                        ]
                    },
                    {
                        "name": "CSS3 and Flexbox",
                        "weeks": 3,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is CSS, how to link CSS, selectors (element, class, id), basic properties (color, background, font-size)"},
                            {"class": 2, "day": "Wednesday", "focus": "Box model (margin, padding, border, content), width, height, box-sizing"},
                            {"class": 3, "day": "Friday", "focus": "Typography (font-family, font-weight, line-height, letter-spacing), Google Fonts, text alignment"},
                            {"class": 4, "day": "Monday", "focus": "Colors (hex, rgb, rgba, hsl), backgrounds (color, image, gradient), opacity"},
                            {"class": 5, "day": "Wednesday", "focus": "CSS Flexbox - flex container, flex-direction, justify-content, align-items"},
                            {"class": 6, "day": "Friday", "focus": "CSS Flexbox advanced - flex-wrap, flex-grow, flex-shrink, align-self, order, real navbar example"},
                            {"class": 7, "day": "Monday", "focus": "CSS positioning (static, relative, absolute, fixed, sticky), z-index"},
                            {"class": 8, "day": "Wednesday", "focus": "CSS pseudo-classes (:hover, :focus, :nth-child), pseudo-elements (::before, ::after), transitions"},
                            {"class": 9, "day": "Friday", "focus": "CSS project review - build a complete styled webpage, common mistakes, assessment"}
                        ]
                    },
                    {
                        "name": "CSS Grid Layout",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Introduction to CSS Grid, display:grid, grid-template-columns, grid-template-rows, gap"},
                            {"class": 2, "day": "Wednesday", "focus": "Grid placement - grid-column, grid-row, grid-area, spanning multiple columns/rows"},
                            {"class": 3, "day": "Friday", "focus": "Grid vs Flexbox - when to use which, combining Grid and Flexbox, auto-fill and auto-fit"},
                            {"class": 4, "day": "Monday", "focus": "Grid template areas, named grid lines, minmax(), fr unit"},
                            {"class": 5, "day": "Wednesday", "focus": "Building a real website layout with CSS Grid - header, sidebar, main, footer"},
                            {"class": 6, "day": "Friday", "focus": "CSS Grid project review, assessment, common mistakes"}
                        ]
                    },
                    {
                        "name": "Responsive Design",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is responsive design, viewport meta tag, mobile-first vs desktop-first approach"},
                            {"class": 2, "day": "Wednesday", "focus": "Media queries - syntax, breakpoints (mobile 320px, tablet 768px, desktop 1024px), practical examples"},
                            {"class": 3, "day": "Friday", "focus": "Responsive images (max-width:100%, srcset, picture element), responsive typography (em, rem, vw, vh)"},
                            {"class": 4, "day": "Monday", "focus": "Responsive navigation patterns (hamburger menu, dropdown), flexible grid systems"},
                            {"class": 5, "day": "Wednesday", "focus": "Testing responsive design (Chrome DevTools, real devices), common responsive mistakes"},
                            {"class": 6, "day": "Friday", "focus": "Build a fully responsive webpage from scratch, assessment"}
                        ]
                    },
                    {
                        "name": "Basic JavaScript",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is JavaScript, how to add JS to HTML, console.log, variables (var/let/const), data types"},
                            {"class": 2, "day": "Wednesday", "focus": "Operators (arithmetic, comparison, logical), if/else statements, switch statements"},
                            {"class": 3, "day": "Friday", "focus": "Loops (for, while, do-while), arrays (create, access, push, pop, length)"},
                            {"class": 4, "day": "Monday", "focus": "Functions (declaration, expression, arrow functions), parameters, return values, scope"},
                            {"class": 5, "day": "Wednesday", "focus": "Objects (create, access properties, methods), JSON basics, typeof"},
                            {"class": 6, "day": "Friday", "focus": "Basic DOM manipulation (getElementById, querySelector, innerHTML, style), event listeners (click), assessment"}
                        ]
                    }
                ]
            },
            {
                "month": 2,
                "title": "JavaScript Mastery",
                "project": "Build a weather app using an API",
                "topics": [
                    {
                        "name": "JavaScript ES6 Plus",
                        "weeks": 3,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Template literals, destructuring arrays and objects, spread operator, rest parameters"},
                            {"class": 2, "day": "Wednesday", "focus": "Arrow functions deep dive, default parameters, enhanced object literals"},
                            {"class": 3, "day": "Friday", "focus": "Promises basics, then/catch, async/await introduction"},
                            {"class": 4, "day": "Monday", "focus": "Modules (import/export), ES6 classes, constructor, inheritance"},
                            {"class": 5, "day": "Wednesday", "focus": "Array methods (map, filter, reduce, find, some, every, forEach)"},
                            {"class": 6, "day": "Friday", "focus": "Set, Map, WeakMap, Symbol, optional chaining, nullish coalescing"},
                            {"class": 7, "day": "Monday", "focus": "Error handling (try/catch/finally), custom errors, debugging techniques"},
                            {"class": 8, "day": "Wednesday", "focus": "Regular expressions basics, string methods (includes, startsWith, endsWith, repeat)"},
                            {"class": 9, "day": "Friday", "focus": "ES6+ project exercises, assessment, common mistakes"}
                        ]
                    },
                    {
                        "name": "DOM Manipulation",
                        "weeks": 3,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is the DOM, DOM tree, selecting elements (getElementById, querySelector, querySelectorAll)"},
                            {"class": 2, "day": "Wednesday", "focus": "Reading and changing element content (innerHTML, textContent, innerText), attributes"},
                            {"class": 3, "day": "Friday", "focus": "Changing CSS styles with JS, classList (add, remove, toggle, contains)"},
                            {"class": 4, "day": "Monday", "focus": "Creating and removing elements (createElement, appendChild, removeChild, insertBefore)"},
                            {"class": 5, "day": "Wednesday", "focus": "DOM traversal (parentNode, childNodes, nextSibling, previousSibling, children)"},
                            {"class": 6, "day": "Friday", "focus": "Event handling deep dive (addEventListener, event object, preventDefault, stopPropagation)"},
                            {"class": 7, "day": "Monday", "focus": "Event delegation, bubbling and capturing, custom events"},
                            {"class": 8, "day": "Wednesday", "focus": "DOM performance (DocumentFragment, reflow/repaint, batching DOM updates)"},
                            {"class": 9, "day": "Friday", "focus": "Build an interactive DOM project, assessment"}
                        ]
                    },
                    {
                        "name": "Events and Forms",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Form events (submit, input, change, focus, blur), reading form values"},
                            {"class": 2, "day": "Wednesday", "focus": "Form validation with JavaScript, custom validation messages, regex for forms"},
                            {"class": 3, "day": "Friday", "focus": "Keyboard events (keydown, keyup, keypress), mouse events (click, mouseover, mouseout)"},
                            {"class": 4, "day": "Monday", "focus": "Touch events for mobile, drag and drop API basics"},
                            {"class": 5, "day": "Wednesday", "focus": "Building a complete form with real-time validation"},
                            {"class": 6, "day": "Friday", "focus": "Assessment, common form mistakes, accessibility in forms"}
                        ]
                    },
                    {
                        "name": "Fetch API and AJAX",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is an API, HTTP methods (GET, POST, PUT, DELETE), JSON, REST API concepts"},
                            {"class": 2, "day": "Wednesday", "focus": "Fetch API basics - fetch(), Response object, .json(), error handling"},
                            {"class": 3, "day": "Friday", "focus": "Async/await with fetch, loading states, displaying API data in DOM"},
                            {"class": 4, "day": "Monday", "focus": "POST requests with fetch, sending JSON data, CORS explained"},
                            {"class": 5, "day": "Wednesday", "focus": "Working with real public APIs (OpenWeather, JSONPlaceholder, REST Countries)"},
                            {"class": 6, "day": "Friday", "focus": "Build a weather app using OpenWeather API, assessment"}
                        ]
                    },
                    {
                        "name": "Local Storage",
                        "weeks": 1,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "localStorage vs sessionStorage vs cookies, setItem, getItem, removeItem, clear"},
                            {"class": 2, "day": "Wednesday", "focus": "Storing objects in localStorage (JSON.stringify/parse), practical todo list project"},
                            {"class": 3, "day": "Friday", "focus": "localStorage limitations, when to use it, assessment and month 2 project review"}
                        ]
                    }
                ]
            }
        ]
    },
    "backend-developer": {
        "title": "Backend Developer",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Python Fundamentals",
                "project": "Build a student grade calculator",
                "topics": [
                    {
                        "name": "Python Basics",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is Python, installing Python, first program, print(), comments, indentation rules"},
                            {"class": 2, "day": "Wednesday", "focus": "Variables, naming conventions, input(), type conversion, basic operators"},
                            {"class": 3, "day": "Friday", "focus": "Strings - indexing, slicing, methods (upper, lower, strip, split, join, replace, format)"},
                            {"class": 4, "day": "Monday", "focus": "Conditional statements (if, elif, else), comparison operators, logical operators (and, or, not)"},
                            {"class": 5, "day": "Wednesday", "focus": "Loops (for, while, range, break, continue, pass), nested loops"},
                            {"class": 6, "day": "Friday", "focus": "Python project exercises, common mistakes, assessment"}
                        ]
                    },
                    {
                        "name": "Data Types and Variables",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Lists - creating, indexing, slicing, methods (append, extend, insert, remove, pop, sort, reverse)"},
                            {"class": 2, "day": "Wednesday", "focus": "Tuples - immutability, when to use tuples, tuple unpacking, named tuples"},
                            {"class": 3, "day": "Friday", "focus": "Dictionaries - creating, accessing, methods (keys, values, items, get, update, pop)"},
                            {"class": 4, "day": "Monday", "focus": "Sets - unique values, set operations (union, intersection, difference), frozenset"},
                            {"class": 5, "day": "Wednesday", "focus": "Type conversion, isinstance(), type checking, mutable vs immutable"},
                            {"class": 6, "day": "Friday", "focus": "Data structures project, assessment, common mistakes"}
                        ]
                    },
                    {
                        "name": "Functions and Modules",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Defining functions, parameters, return values, default arguments, keyword arguments"},
                            {"class": 2, "day": "Wednesday", "focus": "Args and kwargs, lambda functions, scope (local, global, nonlocal), closures"},
                            {"class": 3, "day": "Friday", "focus": "Recursion, higher order functions, map(), filter(), zip(), enumerate()"},
                            {"class": 4, "day": "Monday", "focus": "Creating modules, importing (import, from import, as), __name__ == __main__"},
                            {"class": 5, "day": "Wednesday", "focus": "Standard library modules (os, sys, math, random, datetime, json)"},
                            {"class": 6, "day": "Friday", "focus": "pip, installing packages, virtual environments, requirements.txt, assessment"}
                        ]
                    },
                    {
                        "name": "OOP Concepts",
                        "weeks": 2,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "What is OOP, classes vs objects, __init__, self, instance variables vs class variables"},
                            {"class": 2, "day": "Wednesday", "focus": "Methods (instance, class, static), __str__, __repr__, __len__, dunder methods"},
                            {"class": 3, "day": "Friday", "focus": "Inheritance, super(), method overriding, isinstance(), issubclass()"},
                            {"class": 4, "day": "Monday", "focus": "Encapsulation (public, protected, private), properties (@property, setter, deleter)"},
                            {"class": 5, "day": "Wednesday", "focus": "Polymorphism, abstract classes (ABC), interfaces in Python, duck typing"},
                            {"class": 6, "day": "Friday", "focus": "OOP project - design a real system using classes, assessment"}
                        ]
                    },
                    {
                        "name": "File Handling",
                        "weeks": 1,
                        "classes": [
                            {"class": 1, "day": "Monday", "focus": "Opening and reading files (open, read, readline, readlines), with statement, file modes"},
                            {"class": 2, "day": "Wednesday", "focus": "Writing to files, appending, CSV files (csv module), JSON files (json module)"},
                            {"class": 3, "day": "Friday", "focus": "Exception handling (try/except/finally), custom exceptions, os.path, assessment"}
                        ]
                    }
                ]
            }
        ]
    },
    "data-scientist": {
        "title": "Data Scientist",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Python for Data Science",
                "project": "Analyse a real Nigerian dataset",
                "topics": [
                    {"name": "Python Basics", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Python for data science introduction, Jupyter notebooks, variables, data types, operators"},
                        {"class": 2, "day": "Wednesday", "focus": "Strings, lists, dictionaries, loops, conditionals with data examples"},
                        {"class": 3, "day": "Friday", "focus": "Functions, list comprehensions, lambda, map/filter for data processing"},
                        {"class": 4, "day": "Monday", "focus": "File I/O, reading CSV files, JSON, working with real Nigerian datasets"},
                        {"class": 5, "day": "Wednesday", "focus": "Error handling in data pipelines, debugging data scripts"},
                        {"class": 6, "day": "Friday", "focus": "Assessment - process a Nigerian dataset using pure Python"}
                    ]},
                    {"name": "NumPy Arrays", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is NumPy, installing, creating arrays (array, zeros, ones, arange, linspace)"},
                        {"class": 2, "day": "Wednesday", "focus": "Array indexing, slicing, reshaping, transpose, array dimensions (1D, 2D, 3D)"},
                        {"class": 3, "day": "Friday", "focus": "Array operations (arithmetic, broadcasting, comparison), universal functions"},
                        {"class": 4, "day": "Monday", "focus": "Statistical functions (mean, median, std, var, min, max, sum), axis parameter"},
                        {"class": 5, "day": "Wednesday", "focus": "Boolean indexing, fancy indexing, where(), sorting arrays"},
                        {"class": 6, "day": "Friday", "focus": "NumPy with real data, performance vs Python lists, assessment"}
                    ]},
                    {"name": "Pandas DataFrames", "weeks": 3, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is Pandas, Series vs DataFrame, creating DataFrames from dict/list/CSV"},
                        {"class": 2, "day": "Wednesday", "focus": "Reading data (read_csv, read_excel, read_json), head, tail, info, describe, shape"},
                        {"class": 3, "day": "Friday", "focus": "Selecting data - loc vs iloc, column selection, boolean filtering"},
                        {"class": 4, "day": "Monday", "focus": "Adding/removing columns, rename, apply(), map(), lambda with Pandas"},
                        {"class": 5, "day": "Wednesday", "focus": "GroupBy operations, aggregation (sum, mean, count, min, max), pivot tables"},
                        {"class": 6, "day": "Friday", "focus": "Merging DataFrames (merge, join, concat), handling duplicates"},
                        {"class": 7, "day": "Monday", "focus": "Sorting (sort_values, sort_index), value_counts, unique, nunique"},
                        {"class": 8, "day": "Wednesday", "focus": "Date/time handling in Pandas, resample, rolling"},
                        {"class": 9, "day": "Friday", "focus": "Pandas project with Nigerian dataset, assessment"}
                    ]},
                    {"name": "Data Cleaning", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Identifying dirty data, missing values (isnull, notnull, sum), dropna, fillna strategies"},
                        {"class": 2, "day": "Wednesday", "focus": "Handling duplicates (duplicated, drop_duplicates), outlier detection (IQR, z-score)"},
                        {"class": 3, "day": "Friday", "focus": "Data type conversion, string cleaning (strip, lower, replace, regex)"},
                        {"class": 4, "day": "Monday", "focus": "Standardizing data, normalization vs standardization, encoding categories"},
                        {"class": 5, "day": "Wednesday", "focus": "Real Nigerian dataset cleaning project (population data, economic data)"},
                        {"class": 6, "day": "Friday", "focus": "Assessment - clean a messy Nigerian dataset from scratch"}
                    ]},
                    {"name": "Jupyter Notebooks", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Jupyter interface, cell types (code, markdown), keyboard shortcuts, running cells"},
                        {"class": 2, "day": "Wednesday", "focus": "Markdown formatting, adding explanations, creating structured notebooks for presentation"},
                        {"class": 3, "day": "Friday", "focus": "Jupyter best practices, exporting notebooks, Google Colab, assessment"}
                    ]}
                ]
            }
        ]
    },
    "cybersecurity": {
        "title": "Cybersecurity Professional",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Networking Fundamentals",
                "project": "Set up a home lab network",
                "topics": [
                    {"name": "TCP IP Protocol", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is TCP/IP, IP addresses (IPv4, IPv6), subnets, CIDR notation"},
                        {"class": 2, "day": "Wednesday", "focus": "TCP vs UDP, ports, three-way handshake, connection states"},
                        {"class": 3, "day": "Friday", "focus": "TCP/IP layers, encapsulation, packet structure, Wireshark introduction"},
                        {"class": 4, "day": "Monday", "focus": "NAT, DHCP, ARP, ICMP, ping, traceroute practical exercises"},
                        {"class": 5, "day": "Wednesday", "focus": "TCP/IP vulnerabilities, packet sniffing basics, man-in-the-middle overview"},
                        {"class": 6, "day": "Friday", "focus": "TCP/IP assessment, Wireshark capture analysis"}
                    ]},
                    {"name": "OSI Model", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "OSI 7 layers overview, why it matters, mnemonic to remember layers"},
                        {"class": 2, "day": "Wednesday", "focus": "Physical and Data Link layers - cables, MAC addresses, switches, ARP"},
                        {"class": 3, "day": "Friday", "focus": "Network and Transport layers - IP routing, TCP/UDP, ports"},
                        {"class": 4, "day": "Monday", "focus": "Session, Presentation, Application layers - SSL/TLS, HTTP/S, DNS, FTP"},
                        {"class": 5, "day": "Wednesday", "focus": "OSI model attacks per layer, security at each layer"},
                        {"class": 6, "day": "Friday", "focus": "OSI model assessment, real-world scenario mapping"}
                    ]},
                    {"name": "DNS and HTTP", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "How DNS works, A records, MX, CNAME, TTL, DNS hierarchy, nslookup/dig"},
                        {"class": 2, "day": "Wednesday", "focus": "HTTP vs HTTPS, request/response cycle, methods, status codes, headers, cookies"},
                        {"class": 3, "day": "Friday", "focus": "DNS attacks (poisoning, hijacking), HTTP attacks (MITM, session hijacking), assessment"}
                    ]},
                    {"name": "Firewalls and VPNs", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is a firewall, types (packet filter, stateful, application), rules and policies"},
                        {"class": 2, "day": "Wednesday", "focus": "iptables basics, UFW on Linux, Windows Firewall, configuring rules"},
                        {"class": 3, "day": "Friday", "focus": "VPN concepts, types (Site-to-site, Remote access), protocols (OpenVPN, WireGuard, IPSec)"},
                        {"class": 4, "day": "Monday", "focus": "Setting up a VPN server, VPN for privacy, split tunneling"},
                        {"class": 5, "day": "Wednesday", "focus": "Firewall + VPN lab exercise, common misconfigurations"},
                        {"class": 6, "day": "Friday", "focus": "Assessment, home lab network setup"}
                    ]},
                    {"name": "Network Scanning", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Nmap basics - host discovery, port scanning, service detection, OS detection"},
                        {"class": 2, "day": "Wednesday", "focus": "Nmap advanced - scripts (NSE), output formats, scanning techniques (SYN, TCP, UDP)"},
                        {"class": 3, "day": "Friday", "focus": "Legal and ethical considerations, scanning your own network, assessment"}
                    ]}
                ]
            }
        ]
    },
    "mobile-developer": {
        "title": "Mobile App Developer",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Flutter Basics",
                "project": "Build a calculator app",
                "topics": [
                    {"name": "Dart Language", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is Dart, installing Dart SDK, variables, data types (int, double, String, bool, dynamic)"},
                        {"class": 2, "day": "Wednesday", "focus": "Operators, control flow (if/else, switch, for, while), null safety basics"},
                        {"class": 3, "day": "Friday", "focus": "Functions (named, anonymous, arrow), optional parameters, positional vs named"},
                        {"class": 4, "day": "Monday", "focus": "Lists, Maps, Sets in Dart, collection methods, spread operator"},
                        {"class": 5, "day": "Wednesday", "focus": "OOP in Dart - classes, constructors, inheritance, mixins, interfaces"},
                        {"class": 6, "day": "Friday", "focus": "Async Dart - Future, async/await, Stream basics, assessment"}
                    ]},
                    {"name": "Flutter Setup", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Installing Flutter, Flutter Doctor, Android Studio setup, emulator setup"},
                        {"class": 2, "day": "Wednesday", "focus": "First Flutter app, project structure (lib, pubspec.yaml, assets), running on emulator and real device"},
                        {"class": 3, "day": "Friday", "focus": "Hot reload vs hot restart, debugging basics, Flutter DevTools, assessment"}
                    ]},
                    {"name": "Widgets and Layouts", "weeks": 3, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Everything is a widget, MaterialApp, Scaffold, AppBar, Text, Container, Center"},
                        {"class": 2, "day": "Wednesday", "focus": "Layout widgets - Row, Column, mainAxisAlignment, crossAxisAlignment, Expanded, Flexible"},
                        {"class": 3, "day": "Friday", "focus": "Stack, Positioned, Align, SizedBox, Padding, Margin, EdgeInsets"},
                        {"class": 4, "day": "Monday", "focus": "ListView, GridView, SingleChildScrollView, scrolling and overflow handling"},
                        {"class": 5, "day": "Wednesday", "focus": "Buttons (ElevatedButton, TextButton, IconButton, FloatingActionButton), GestureDetector"},
                        {"class": 6, "day": "Friday", "focus": "Images (AssetImage, NetworkImage), Icons, Card, Divider, Chip"},
                        {"class": 7, "day": "Monday", "focus": "TextFormField, TextField, Form widget, input decoration"},
                        {"class": 8, "day": "Wednesday", "focus": "SnackBar, AlertDialog, BottomSheet, showDialog, showModalBottomSheet"},
                        {"class": 9, "day": "Friday", "focus": "Build a complete UI layout, assessment"}
                    ]},
                    {"name": "Stateful vs Stateless", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "StatelessWidget vs StatefulWidget, when to use each, widget lifecycle"},
                        {"class": 2, "day": "Wednesday", "focus": "setState(), understanding rebuilds, keys in Flutter, avoid unnecessary rebuilds"},
                        {"class": 3, "day": "Friday", "focus": "Counter app, toggle widget, form with state, assessment"}
                    ]},
                    {"name": "Hot Reload", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "How hot reload works, limitations, when it breaks, hot restart use cases"},
                        {"class": 2, "day": "Wednesday", "focus": "Productive Flutter development workflow, keyboard shortcuts, code snippets"},
                        {"class": 3, "day": "Friday", "focus": "Build and run the calculator app project, assessment, month review"}
                    ]}
                ]
            }
        ]
    },
    "ui-ux-designer": {
        "title": "UI/UX Designer",
        "duration": "4 months",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Design Fundamentals",
                "project": "Redesign a bad app interface",
                "topics": [
                    {"name": "Design Principles", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is UI vs UX, importance of good design, examples of good and bad Nigerian apps"},
                        {"class": 2, "day": "Wednesday", "focus": "Gestalt principles (proximity, similarity, continuity, closure, figure-ground)"},
                        {"class": 3, "day": "Friday", "focus": "Visual hierarchy, emphasis, contrast, balance (symmetrical and asymmetrical)"},
                        {"class": 4, "day": "Monday", "focus": "Alignment, repetition, proximity, whitespace, Hicks Law, Fitts Law"},
                        {"class": 5, "day": "Wednesday", "focus": "Applying design principles to real Nigerian app redesigns"},
                        {"class": 6, "day": "Friday", "focus": "Design principles assessment, critique session"}
                    ]},
                    {"name": "Colour Theory", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "Color wheel, primary/secondary/tertiary colors, warm vs cool colors, color psychology"},
                        {"class": 2, "day": "Wednesday", "focus": "Color harmony - complementary, analogous, triadic, split-complementary, tetradic"},
                        {"class": 3, "day": "Friday", "focus": "Color in branding - Nigerian company brand colors (GTBank, Airtel, MTN, Zenith Bank)"},
                        {"class": 4, "day": "Monday", "focus": "Tints, shades, tones, saturation, lightness, creating a color palette for an app"},
                        {"class": 5, "day": "Wednesday", "focus": "Accessibility and color - contrast ratios, color blindness, WCAG guidelines"},
                        {"class": 6, "day": "Friday", "focus": "Build a color palette for a Nigerian fintech app, assessment"}
                    ]},
                    {"name": "Typography", "weeks": 2, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is typography, typeface vs font, serif vs sans-serif vs display vs monospace"},
                        {"class": 2, "day": "Wednesday", "focus": "Type hierarchy (heading, subheading, body, caption), font pairing rules"},
                        {"class": 3, "day": "Friday", "focus": "Size scale, line height, letter spacing, paragraph width, readability rules"},
                        {"class": 4, "day": "Monday", "focus": "Google Fonts, custom fonts, loading fonts in design tools, font licenses"},
                        {"class": 5, "day": "Wednesday", "focus": "Typography for Nigerian apps - local language support, multilingual design"},
                        {"class": 6, "day": "Friday", "focus": "Typography assessment, apply to redesign project"}
                    ]},
                    {"name": "Layout and Grids", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "What is a grid system, columns, gutters, margins, 8pt grid system"},
                        {"class": 2, "day": "Wednesday", "focus": "Mobile grids (4-column), tablet grids (8-column), desktop grids (12-column)"},
                        {"class": 3, "day": "Friday", "focus": "Applying grids in Figma, layout for Nigerian apps, assessment"}
                    ]},
                    {"name": "Design Thinking", "weeks": 1, "classes": [
                        {"class": 1, "day": "Monday", "focus": "5 stages of design thinking - Empathize, Define, Ideate, Prototype, Test"},
                        {"class": 2, "day": "Wednesday", "focus": "User empathy maps, problem statements, how might we questions, idea brainstorming"},
                        {"class": 3, "day": "Friday", "focus": "Apply design thinking to redesign a bad Nigerian app, assessment, month project"}
                    ]}
                ]
            }
        ]
    }
}


def get_curriculum_for(slug: str) -> dict:
    """Return a curriculum dict for `slug`. If not present locally,
    fetch roadmap.sh content and return a minimal curriculum that
    includes the roadmap markdown under `roadmap_md`.
    """
    key = slug.replace(" ", "-").lower()
    if key in CURRICULUM:
        return CURRICULUM[key]

    md = fetch_roadmap(slug)
    if not md:
        return {}

    curriculum = {
        "title": key.replace("-", " ").title(),
        "duration": "Varies",
        "monthly_plan": [
            {
                "month": 1,
                "title": "Imported Roadmap",
                "topics": [
                    {"name": key, "weeks": 1, "classes": []}
                ],
                "project": "Follow the imported roadmap"
            }
        ],
        "roadmap_md": md,
    }
    CURRICULUM[key] = curriculum
    return curriculum


def generate_class_content(course_title, month_title, topic_name, class_info, month_number, total_classes):
    """Generate AI content for a single class session."""
    prompt = f"""You are an expert tech educator writing content for BOI RSU Tech Education Platform in Nigeria.

Course: {course_title}
Month {month_number}: {month_title}
Topic: {topic_name}
Class Session: Class {class_info['class']} of {total_classes} ({class_info['day']})
This class focuses on: {class_info['focus']}

Write TWO things:

=== LESSON NOTE ===
Write a detailed student lesson note for this specific class. Include:

TODAYS CLASS FOCUS
Brief intro to what this specific class covers and why it matters.

CORE CONTENT
Detailed explanation of: {class_info['focus']}
Use simple language, Nigerian examples (Jumia, Paystack, Flutterwave, Lagos, everyday Nigerian life).
Include actual code examples where relevant, step by step.

KEY CONCEPTS
List and explain the 3-5 most important things from today.

WORKED EXAMPLES
Walk through 2 complete practical examples in detail.

COMMON MISTAKES
3-4 mistakes beginners make on this specific topic and how to avoid them.

PRACTICE EXERCISES
3 exercises students must complete before the next class (Monday/Wednesday/Friday).

KEY TAKEAWAYS
5 bullet points summarizing what was learned today.

=== TEACHING SCRIPT ===
Write Alex's complete word-for-word 1-hour teaching script for this class.

[0:00 - 5:00] OPENING (5 minutes)
Alex greets students, recaps last class briefly, introduces today's focus: {class_info['focus']}

[5:00 - 45:00] MAIN TEACHING (40 minutes)
Alex teaches {class_info['focus']} in full depth. Word for word. Natural spoken language.
Include Nigerian examples, step by step code walkthroughs, questions to students,
encouragement. Be detailed - this should fill 40 minutes of actual speaking.
Include at least 2 detailed examples with code or practical steps.
Include [PAUSE - ASK STUDENTS: question here] markers where Alex asks students questions.

[45:00 - 52:00] PRACTICE TIME (7 minutes)
Alex gives students a practice challenge related to today's content.
Walks around (or in our case, encourages students to try it while Alex watches).
[PAUSE - GIVE STUDENTS TIME TO PRACTICE]

[52:00 - 57:00] QUIZ (5 minutes)
Alex asks 2 quick questions to check understanding.
For each question: ask it, give options A B C D, [PAUSE FOR ANSWERS], reveal answer with explanation.

[57:00 - 60:00] CLOSING (3 minutes)
Alex summarizes today, gives homework (the practice exercises), previews next class,
motivational closing, goodbye.

Make the script sound like a real energetic human teacher speaking naturally to Nigerian students.
Do NOT write summaries - write EXACTLY what Alex says word for word."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"    [AI Error] {e}")
        return f"Content for {topic_name} Class {class_info['class']} could not be generated."


class BOIRSUDocument(FPDF):
    def header(self):
        self.set_fill_color(10, 50, 100)
        self.rect(0, 0, 210, 20, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.set_y(6)
        self.cell(0, 8, "BOI RSU TECH EDUCATION PLATFORM", align="C")
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()} | BOI RSU Tech Education", align="C")

    def add_cover(self, course_title, month_title, topic_name, class_num, day, focus, doc_type):
        self.add_page()
        self.set_fill_color(10, 50, 100)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(255, 200, 0)
        self.set_font("Helvetica", "B", 26)
        self.set_y(40)
        self.cell(0, 15, "BOI RSU", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "TECH EDUCATION PLATFORM", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_font("Helvetica", "B", 20)
        self.cell(0, 12, course_title.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        self.set_font("Helvetica", "", 14)
        self.cell(0, 10, month_title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(8)
        self.set_fill_color(255, 200, 0)
        self.set_text_color(10, 50, 100)
        self.set_font("Helvetica", "B", 14)
        y = self.get_y()
        self.rect(20, y, 170, 14, 'F')
        self.set_y(y + 2)
        self.cell(0, 10, f"TOPIC: {topic_name}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 12, f"CLASS {class_num} - {day.upper()}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(5)
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(0, 100, 200)
        y2 = self.get_y()
        self.rect(15, y2, 180, 20, 'F')
        self.set_y(y2 + 3)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(180, 7, f"Focus: {focus}", align="C")
        self.ln(8)
        self.set_fill_color(200, 50, 50)
        y3 = self.get_y()
        self.rect(40, y3, 130, 14, 'F')
        self.set_y(y3 + 2)
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, doc_type.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_y(260)
        self.set_text_color(150, 150, 150)
        self.set_font("Helvetica", "", 10)
        self.cell(0, 8, "BOI RSU AI Learning Platform | 3 Classes Per Week", align="C", new_x="LMARGIN", new_y="NEXT")

    def clean_text(self, text):
        """Replace smart quotes and other non-latin1 characters."""
        replacements = {
            '’': "'", '‘': "'", '“': '"', '”': '"',
            '–': '-', '—': '-', '…': '...', 'â': 'a',
            '•': '-', '·': '-', '‒': '-', '―': '-',
        }
        for old_char, new_char in replacements.items():
            text = text.replace(old_char, new_char)
        return text.encode('latin-1', errors='replace').decode('latin-1')

    def add_content(self, text):
        text = self.clean_text(text)
        self.set_font("Helvetica", "", 11)
        self.set_text_color(40, 40, 40)
        self.set_left_margin(10)
        self.set_right_margin(10)
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                self.ln(3)
                continue
            if line.startswith('===') and line.endswith('==='):
                self.ln(6)
                self.set_fill_color(10, 50, 100)
                self.set_text_color(255, 255, 255)
                self.set_font("Helvetica", "B", 13)
                self.set_x(10)
                self.multi_cell(190, 9, f"  {line.replace('=','').strip()}  ", fill=True)
                self.set_text_color(40, 40, 40)
                self.set_font("Helvetica", "", 11)
                self.ln(3)
            elif line.isupper() and len(line) > 4 and not line.startswith('['):
                self.ln(4)
                self.set_font("Helvetica", "B", 12)
                self.set_text_color(10, 50, 100)
                self.set_x(10)
                self.multi_cell(190, 7, line)
                self.set_line_width(0.3)
                self.set_draw_color(10, 50, 100)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(2)
                self.set_font("Helvetica", "", 11)
                self.set_text_color(40, 40, 40)
            elif line.startswith('[') and ']' in line:
                self.ln(4)
                self.set_fill_color(230, 240, 255)
                self.set_font("Helvetica", "B", 11)
                self.set_text_color(10, 50, 100)
                self.set_x(10)
                self.multi_cell(190, 8, line, fill=True)
                self.set_font("Helvetica", "", 11)
                self.set_text_color(40, 40, 40)
                self.ln(2)
            elif line.startswith(('-', '*', 'bullet', '+')):
                self.set_x(14)
                self.multi_cell(186, 6, f"  {line[1:].strip()}")
            elif line[0].isdigit() and '.' in line[:3]:
                self.set_font("Helvetica", "B", 11)
                self.set_x(10)
                self.multi_cell(190, 7, line)
                self.set_font("Helvetica", "", 11)
            else:
                self.set_x(10)
                self.multi_cell(190, 6, line)


def generate_for_topic_class(course_dir, course_title, month_title, topic, class_info, month_number):
    """Generate lesson note and script for one class."""
    total_classes = len(topic['classes'])
    class_num = class_info['class']
    day = class_info['day']
    focus = class_info['focus']
    topic_name = topic['name']

    print(f"    Class {class_num}/{total_classes} ({day}): {focus[:60]}...")

    # Generate AI content
    content = generate_class_content(
        course_title, month_title, topic_name,
        class_info, month_number, total_classes
    )

    # Split into lesson note and teaching script
    if "=== TEACHING SCRIPT ===" in content:
        parts = content.split("=== TEACHING SCRIPT ===")
        lesson_note_content = parts[0].replace("=== LESSON NOTE ===", "").strip()
        script_content = parts[1].strip()
    else:
        lesson_note_content = content
        script_content = content

    # File naming
    topic_slug = topic_name.lower().replace(" ", "_").replace("/", "_").replace("&", "and")
    base = f"class{class_num:02d}_{day.lower()}"
    topic_dir = course_dir / topic_slug
    topic_dir.mkdir(parents=True, exist_ok=True)

    # Save lesson note
    note_txt = topic_dir / f"{base}_lesson_note.txt"
    note_pdf = topic_dir / f"{base}_lesson_note.pdf"

    header = f"BOI RSU TECH EDUCATION\n{course_title}\n{month_title}\nTopic: {topic_name}\nClass {class_num} - {day}\nFocus: {focus}\n{'='*60}\n\n"
    with open(note_txt, 'w', encoding='utf-8') as f:
        f.write(header + lesson_note_content)

    pdf = BOIRSUDocument()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_cover(course_title, month_title, topic_name, class_num, day, focus, "LESSON NOTE")
    pdf.add_page()
    pdf.add_content(lesson_note_content)
    pdf.output(str(note_pdf))

    # Save teaching script
    script_txt = topic_dir / f"{base}_teaching_script.txt"
    script_pdf = topic_dir / f"{base}_teaching_script.pdf"

    with open(script_txt, 'w', encoding='utf-8') as f:
        f.write(header + script_content)

    pdf2 = BOIRSUDocument()
    pdf2.set_auto_page_break(auto=True, margin=25)
    pdf2.add_cover(course_title, month_title, topic_name, class_num, day, focus, "1-HOUR TEACHING SCRIPT")
    pdf2.add_page()
    pdf2.add_content(script_content)
    pdf2.output(str(script_pdf))

    time.sleep(3)  # Avoid Gemini rate limiting


def generate_for_course(career_path):
    if career_path not in CURRICULUM:
        print(f"Course '{career_path}' not found.")
        return

    roadmap = CURRICULUM[career_path]
    course_title = roadmap["title"]
    course_dir = LESSONS_DIR / career_path
    course_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Course: {course_title}")
    print(f"Duration: {roadmap['duration']}")
    print(f"{'='*60}")

    for month_plan in roadmap["monthly_plan"]:
        month_number = month_plan["month"]
        month_title = f"Month {month_number}: {month_plan['title']}"
        print(f"\n{month_title}")
        print(f"Project: {month_plan['project']}")

        month_dir = course_dir / f"month{month_number:02d}"
        month_dir.mkdir(parents=True, exist_ok=True)

        for topic in month_plan["topics"]:
            print(f"\n  Topic: {topic['name']} ({topic['weeks']} weeks, {len(topic['classes'])} classes)")

            for class_info in topic["classes"]:
                generate_for_topic_class(
                    month_dir, course_title, month_title,
                    topic, class_info, month_number
                )

    print(f"\nDone! All files saved to: {course_dir}")


def main():
    print("BOI RSU Realistic Curriculum Generator")
    print("3 classes per week | Realistic timeline | Full depth")
    print("=" * 60)

    if not GOOGLE_API_KEY:
        print("ERROR: GOOGLE_API_KEY not found!")
        sys.exit(1)

    if len(sys.argv) > 1:
        career_path = sys.argv[1]
        # Allow specifying month and topic too
        generate_for_course(career_path)
    else:
        for career_path in CURRICULUM.keys():
            generate_for_course(career_path)
            time.sleep(5)

    print(f"\nALL DONE! Files saved to: {LESSONS_DIR}")


if __name__ == "__main__":
    main()
 