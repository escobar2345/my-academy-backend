"""World-wide course search for the boi-school registration page.

The frontend (frontend/boi-school/registration.vue) calls
GET /api/courses/search?q=<query> and expects {"success": true, "results": [...]}.

"Any course in the world" is powered by Class Central (classcentral.com) —
the aggregator indexing Coursera, edX, Udemy, Stanford, MIT and 250k+ other
courses. We fetch its search results page and parse the structured tracking
JSON (data-track-props) embedded on every course card anchor. Verified against
a live capture (2026-09-07): each a[data-track-click=course_click] carries
{"course_name", "course_id", "course_provider", "course_institution",
"course_avg_rating", "course_num_rating", "course_level", "course_language",
"course_is_free", "course_format", "course_slug"} and href="/course/<slug>-<id>".
"""

import json
import re
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request

bp = Blueprint('courses', __name__)

_BASE = 'https://www.classcentral.com'
_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
_TIMEOUT = 20
_MAX_RESULTS = 18


def _clean(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def _parse_cards(html):
    """Extract course dicts from the search page's tracking anchors."""
    soup = BeautifulSoup(html, 'lxml')
    results, seen = [], set()
    for a in soup.select('a[data-track-click="course_click"][data-track-props]'):
        try:
            props = json.loads(a['data-track-props'])
        except (TypeError, ValueError):
            continue
        cid = props.get('course_id')
        if not cid or cid in seen:
            continue
        seen.add(cid)
        name = _clean(props.get('course_name'))
        if not name:
            continue
        institution = _clean(props.get('course_institution'))
        level = _clean(props.get('course_level'))
        language = _clean(props.get('course_language'))
        desc_bits = [
            b for b in (institution,
                        level.title() if level else '',
                        language)
            if b
        ]
        rating = props.get('course_avg_rating')
        reviews = props.get('course_num_rating')
        try:
            rating = round(float(rating), 1) if rating else None
        except (TypeError, ValueError):
            rating = None
        try:
            reviews = int(reviews) if reviews else None
        except (TypeError, ValueError):
            reviews = None
        href = a.get('href') or f"/course/{props.get('course_slug')}-{cid}"
        results.append({
            'name': name,
            'provider': _clean(props.get('course_provider')) or 'Class Central',
            'institution': institution,
            'desc': ' · '.join(desc_bits) or 'Online course',
            'rating': rating,
            'reviews': reviews,
            'duration': _clean(props.get('course_format')) or '',
            'free': bool(props.get('course_is_free')),
            'url': urljoin(_BASE, href),
        })
        if len(results) >= _MAX_RESULTS:
            break
    return results


@bp.route('/courses/search', methods=['GET'])
def search_courses():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({
            'success': False,
            'error': 'Type at least 2 characters to search world courses'
        }), 400

    try:
        resp = requests.get(
            f'{_BASE}/search?q={quote_plus(q)}',
            headers={
                'User-Agent': _UA,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': f'{_BASE}/',
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        return jsonify({
            'success': False,
            'error': f'Could not reach Class Central: {exc}'
        }), 502

    if resp.status_code != 200:
        return jsonify({
            'success': False,
            'error': f'Class Central returned HTTP {resp.status_code}'
        }), 502

    results = _parse_cards(resp.text)
    return jsonify({
        'success': True,
        'query': q,
        'source': 'classcentral',
        'count': len(results),
        'results': results,
    })
