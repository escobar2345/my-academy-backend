"""Refactored BOI RSU API routes using service-based architecture.

This module demonstrates the new service-based approach where:
- Business logic is encapsulated in BoiRsuService
- Routes are thin and focused on HTTP concerns only
- Services are obtained via dependency injection
- Better testability, maintainability, and separation of concerns
"""

from flask import Blueprint, jsonify, request
from ..services.boirsu_service import BoiRsuService
from ..services.container import get_service

bp = Blueprint('boirsu', __name__)


# ============================================================================
# Course Management Routes
# ============================================================================

@bp.route('/courses', methods=['GET'])
def list_courses():
    """List all available career paths and courses."""
    try:
        service = get_service(BoiRsuService)
        courses = service.list_courses()
        return jsonify({
            'success': True,
            'data': courses,
            'total': len(courses)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/courses/<career_path>', methods=['GET'])
def get_course_detail(career_path):
    """Get detailed roadmap for a specific course."""
    try:
        service = get_service(BoiRsuService)
        roadmap = service.get_course_roadmap(career_path)
        return jsonify({'success': True, 'data': roadmap})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Student Management Routes
# ============================================================================

@bp.route('/student', methods=['POST'])
def enroll_student():
    """Enroll a new student in a course.
    
    Request body:
        {
            "name": "John Doe",
            "phone": "+234901234567",
            "email": "john@example.com",
            "career_path": "frontend-developer",
            "experience_level": "beginner"
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        student = service.enroll_student(
            name=payload.get('name', 'Demo Student'),
            phone=payload.get('phone', '00000000000'),
            email=payload.get('email', 'demo@example.com'),
            career_path=payload.get('career_path', 'frontend-developer'),
            experience_level=payload.get('experience_level', 'beginner')
        )
        
        return jsonify({'success': True, 'data': student}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/student/<student_id>', methods=['GET'])
def get_student(student_id):
    """Get student details."""
    try:
        service = get_service(BoiRsuService)
        student = service.get_student(student_id)
        
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        return jsonify({'success': True, 'data': student})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/students', methods=['GET'])
def list_students():
    """List all enrolled students."""
    try:
        service = get_service(BoiRsuService)
        students_dict = service.load_all_students()
        students = list(students_dict.values())
        
        return jsonify({
            'success': True,
            'data': students,
            'total': len(students),
            'active': len(service.get_active_students())
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/student/<student_id>/roadmap', methods=['GET'])
def generate_student_roadmap(student_id):
    """Get personalized roadmap for a student."""
    try:
        service = get_service(BoiRsuService)
        progress = service.get_student_progress(student_id)
        return jsonify({'success': True, 'data': progress})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/student/<student_id>/progress', methods=['GET'])
def get_student_progress(student_id):
    """Get detailed progress report for a student."""
    try:
        service = get_service(BoiRsuService)
        progress = service.get_student_progress(student_id)
        return jsonify({'success': True, 'data': progress})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Attendance & Performance Routes
# ============================================================================

@bp.route('/student/<student_id>/attendance', methods=['POST'])
def record_attendance(student_id):
    """Record student attendance.
    
    Request body:
        {
            "class_number": 1,
            "attended": true
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        result = service.record_attendance(
            student_id=student_id,
            class_number=payload.get('class_number'),
            attended=payload.get('attended', False)
        )
        
        return jsonify({'success': result, 'data': {'attended': result}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/student/<student_id>/quiz', methods=['POST'])
def submit_quiz(student_id):
    """Submit quiz responses.
    
    Request body:
        {
            "quiz_id": "quiz_001",
            "answers": {"q1": "A", "q2": "B", "q3": "C"}
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        result = service.submit_quiz_response(
            student_id=student_id,
            quiz_id=payload.get('quiz_id'),
            answers=payload.get('answers', {})
        )
        
        return jsonify({'success': True, 'data': result}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/student/<student_id>/assignment', methods=['POST'])
def submit_assignment(student_id):
    """Submit an assignment.
    
    Request body:
        {
            "assignment_number": 1,
            "submission_text": "My solution..."
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        result = service.submit_assignment(
            student_id=student_id,
            assignment_number=payload.get('assignment_number'),
            submission_text=payload.get('submission_text', '')
        )
        
        return jsonify({'success': True, 'data': result}), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Payment Integration Routes
# ============================================================================

@bp.route('/payment/create', methods=['POST'])
def create_payment():
    """Create a payment link for course enrollment.
    
    Request body:
        {
            "student_name": "John Doe",
            "email": "john@example.com",
            "career_path": "frontend-developer"
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        result = service.create_payment_link(
            student_name=payload.get('student_name'),
            email=payload.get('email'),
            career_path=payload.get('career_path')
        )
        
        if not result:
            return jsonify({'success': False, 'error': 'Payment link creation failed'}), 400
        
        payment_url, reference = result
        return jsonify({
            'success': True,
            'data': {
                'payment_url': payment_url,
                'reference': reference
            }
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/payment/verify/<reference>', methods=['GET'])
def verify_payment(reference):
    """Verify a payment by reference ID."""
    try:
        service = get_service(BoiRsuService)
        verified = service.verify_payment(reference)
        
        return jsonify({
            'success': True,
            'data': {'verified': verified}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Messaging Routes
# ============================================================================

@bp.route('/message/whatsapp', methods=['POST'])
def send_whatsapp():
    """Send a WhatsApp message.
    
    Request body:
        {
            "phone": "+234901234567",
            "message": "Hello student!"
        }
    """
    try:
        payload = request.get_json(silent=True) or {}
        service = get_service(BoiRsuService)
        
        result = service.send_whatsapp_message(
            phone=payload.get('phone'),
            message=payload.get('message')
        )
        
        return jsonify({'success': result, 'data': {'sent': result}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/message/morning-checkin', methods=['POST'])
def send_morning_checkin():
    """Send morning check-in messages to all active students."""
    try:
        service = get_service(BoiRsuService)
        count = service.send_morning_checkin()
        
        return jsonify({
            'success': True,
            'data': {'messages_sent': count}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/message/motivation', methods=['POST'])
def send_motivation():
    """Send motivation messages to all active students."""
    try:
        service = get_service(BoiRsuService)
        count = service.send_motivation_messages()
        
        return jsonify({
            'success': True,
            'data': {'messages_sent': count}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/message/admin-report', methods=['POST'])
def send_admin_report():
    """Send private daily report to admin."""
    try:
        service = get_service(BoiRsuService)
        result = service.send_admin_report()
        
        return jsonify({
            'success': result,
            'data': {'sent': result}
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Analytics Routes
# ============================================================================

@bp.route('/analytics/courses', methods=['GET'])
def get_courses_stats():
    """Get statistics across all courses."""
    try:
        service = get_service(BoiRsuService)
        stats = {
            'total_students': service.get_student_count(),
            'active_students': len(service.get_active_students()),
            'available_courses': len(service.list_courses())
        }
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/analytics/course/<career_path>', methods=['GET'])
def get_course_stats(career_path):
    """Get detailed statistics for a specific course."""
    try:
        service = get_service(BoiRsuService)
        stats = service.get_course_statistics(career_path)
        
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# Health Check
# ============================================================================

@bp.route('/health', methods=['GET'])
def health():
    """Health check for BOI RSU service."""
    try:
        service = get_service(BoiRsuService)
        student_count = service.get_student_count()
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'students_loaded': student_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }), 500
