from flask import Blueprint, jsonify, request

from app.boi_rsu import load_module

bp = Blueprint('boirsu', __name__)


def _load_boi_module():
    return load_module()


@bp.route('/courses', methods=['GET'])
def list_courses():
    try:
        module = _load_boi_module()
        courses = []
        for slug, roadmap in module.CAREER_ROADMAPS.items():
            courses.append({
                'slug': slug,
                'title': roadmap.get('title'),
                'duration': roadmap.get('duration'),
                'description': roadmap.get('description')
            })
        return jsonify({'success': True, 'data': courses})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student', methods=['POST'])
def enroll_student():
    payload = request.get_json(silent=True) or {}
    try:
        module = _load_boi_module()
        student = module.enroll_student(
            name=payload.get('name', 'Demo Student'),
            phone=payload.get('phone', '00000000000'),
            email=payload.get('email', 'demo@example.com'),
            career_path=payload.get('career_path', 'frontend-developer'),
            experience_level=payload.get('experience_level', 'beginner')
        )
        return jsonify({'success': True, 'data': student})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>/roadmap', methods=['GET'])
def generate_student_roadmap(student_id):
    try:
        module = _load_boi_module()
        path = module.generate_roadmap_pdf(student_id)
        return jsonify({'success': True, 'data': {'student_id': student_id, 'path': path}})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>/quiz', methods=['POST'])
def record_quiz(student_id):
    payload = request.get_json(silent=True) or {}
    try:
        module = _load_boi_module()
        student = module.record_quiz_score(
            student_id=student_id,
            topic=payload.get('topic', 'Python Basics'),
            score=int(payload.get('score', 8)),
            total_questions=int(payload.get('total_questions', 10))
        )
        return jsonify({'success': True, 'data': student})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>/assignment', methods=['POST'])
def submit_assignment(student_id):
    payload = request.get_json(silent=True) or {}
    try:
        module = _load_boi_module()
        student = module.submit_assignment(
            student_id=student_id,
            assignment_number=int(payload.get('assignment_number', 1)),
            submission_text=payload.get('submission_text', 'Demo submission'),
            score=payload.get('score')
        )
        return jsonify({'success': True, 'data': student})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>/attendance', methods=['POST'])
def mark_attendance(student_id):
    payload = request.get_json(silent=True) or {}
    try:
        module = _load_boi_module()
        student = module.mark_attendance(
            student_id=student_id,
            class_number=int(payload.get('class_number', 1)),
            attended=bool(payload.get('attended', True))
        )
        return jsonify({'success': True, 'data': student})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>/certificate', methods=['GET'])
def generate_certificate(student_id):
    try:
        module = _load_boi_module()
        path = module.generate_certificate(student_id)
        return jsonify({'success': True, 'data': {'student_id': student_id, 'path': path}})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500


@bp.route('/student/<student_id>', methods=['GET'])
def get_student(student_id):
    try:
        module = _load_boi_module()
        student = module.get_student(student_id)
        return jsonify({'success': True, 'data': student})
    except Exception as exc:  # pragma: no cover
        return jsonify({'success': False, 'error': str(exc)}), 500
