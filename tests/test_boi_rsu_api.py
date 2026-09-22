import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app


def test_boi_rsu_courses_endpoint():
    app = create_app()
    client = app.test_client()

    response = client.get('/api/boirsu/courses')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    slugs = [item['slug'] for item in payload['data']]
    assert 'frontend-developer' in slugs
