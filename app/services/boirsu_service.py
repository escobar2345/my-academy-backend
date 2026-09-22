"""BOI RSU Student Management Service.

This service encapsulates all business logic for:
- Student enrollment and management
- Course roadmap generation
- Payment processing
- WhatsApp messaging integration
- Scheduling and reminders
- Performance tracking
"""

from typing import List, Dict, Any, Optional
from .container import Service


class BoiRsuService(Service):
    """Service for BOI RSU student management and course delivery."""
    
    def __init__(self, container):
        """Initialize BOI RSU service.
        
        Args:
            container: ServiceContainer for accessing dependencies
        """
        super().__init__(container)
        self._boirsu_module = None
    
    def initialize(self) -> None:
        """Load and initialize the BOI RSU module."""
        try:
            from app.boi_rsu import load_module
            self._boirsu_module = load_module()
        except Exception as e:
            print(f"[WARN] BOI RSU module initialization failed: {e}")
            self._boirsu_module = None
    
    def shutdown(self) -> None:
        """Cleanup BOI RSU resources."""
        self._boirsu_module = None
    
    def _check_module(self) -> bool:
        """Check if module is available."""
        if self._boirsu_module is None:
            raise RuntimeError("BOI RSU module not available. Check initialization errors.")
        return True
    
    # ========================
    # Course Management
    # ========================
    
    def list_courses(self) -> List[Dict[str, Any]]:
        """Get list of all available courses.
        
        Returns:
            List of course dictionaries with title, duration, description
        """
        self._check_module()
        
        courses = []
        roadmaps = getattr(self._boirsu_module, 'CAREER_ROADMAPS', {})
        
        for slug, roadmap in roadmaps.items():
            courses.append({
                'slug': slug,
                'title': roadmap.get('title'),
                'duration': roadmap.get('duration'),
                'description': roadmap.get('description'),
                'fee': roadmap.get('fee', 'Contact for pricing')
            })
        
        return courses
    
    def get_course_roadmap(self, career_path: str) -> Dict[str, Any]:
        """Get detailed roadmap for a specific career path.
        
        Args:
            career_path: Career path slug (e.g., 'frontend-developer')
            
        Returns:
            Detailed course roadmap dictionary
            
        Raises:
            ValueError: If career path not found
        """
        self._check_module()
        
        roadmaps = getattr(self._boirsu_module, 'CAREER_ROADMAPS', {})
        if career_path not in roadmaps:
            raise ValueError(f"Career path '{career_path}' not found")
        
        return roadmaps[career_path]
    
    # ========================
    # Student Management
    # ========================
    
    def enroll_student(self, name: str, phone: str, email: str, 
                      career_path: str, experience_level: str = 'beginner') -> Dict[str, Any]:
        """Enroll a new student in a course.
        
        Args:
            name: Student full name
            phone: WhatsApp phone number
            email: Student email
            career_path: Career path to enroll in
            experience_level: Experience level (beginner, intermediate, advanced)
            
        Returns:
            Enrolled student dictionary with ID
            
        Raises:
            Exception: If enrollment fails
        """
        self._check_module()
        
        enroll = getattr(self._boirsu_module, 'enroll_student', None)
        if not enroll:
            raise RuntimeError("enroll_student function not available")
        
        return enroll(
            name=name,
            phone=phone,
            email=email,
            career_path=career_path,
            experience_level=experience_level
        )
    
    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get student details.
        
        Args:
            student_id: Student ID
            
        Returns:
            Student dictionary or None if not found
        """
        self._check_module()
        
        get_student_fn = getattr(self._boirsu_module, 'get_student', None)
        if not get_student_fn:
            raise RuntimeError("get_student function not available")
        
        return get_student_fn(student_id)
    
    def load_all_students(self) -> Dict[str, Dict[str, Any]]:
        """Load all enrolled students.
        
        Returns:
            Dictionary of students by ID
        """
        self._check_module()
        
        load_students = getattr(self._boirsu_module, 'load_students', None)
        if not load_students:
            raise RuntimeError("load_students function not available")
        
        return load_students()
    
    def get_student_count(self) -> int:
        """Get total number of enrolled students.
        
        Returns:
            Number of enrolled students
        """
        try:
            students = self.load_all_students()
            return len(students)
        except:
            return 0
    
    def get_active_students(self) -> List[Dict[str, Any]]:
        """Get list of students with paid enrollment.
        
        Returns:
            List of active student dictionaries
        """
        try:
            students = self.load_all_students()
            return [s for s in students.values() 
                   if s.get('payment_status') == 'paid']
        except:
            return []
    
    # ========================
    # Attendance & Performance
    # ========================
    
    def record_attendance(self, student_id: str, class_number: int, 
                         attended: bool) -> bool:
        """Record student attendance for a class.
        
        Args:
            student_id: Student ID
            class_number: Class number
            attended: Whether student attended
            
        Returns:
            True if recorded successfully
        """
        self._check_module()
        
        record_fn = getattr(self._boirsu_module, 'record_attendance', None)
        if not record_fn:
            raise RuntimeError("record_attendance function not available")
        
        return record_fn(student_id, class_number, attended)
    
    def submit_quiz_response(self, student_id: str, quiz_id: str, 
                            answers: Dict[str, str]) -> Dict[str, Any]:
        """Submit quiz responses for a student.
        
        Args:
            student_id: Student ID
            quiz_id: Quiz ID
            answers: Dictionary of question ID -> answer
            
        Returns:
            Quiz result with score
        """
        self._check_module()
        
        submit_fn = getattr(self._boirsu_module, 'submit_quiz_response', None)
        if not submit_fn:
            raise RuntimeError("submit_quiz_response function not available")
        
        return submit_fn(student_id, quiz_id, answers)
    
    def submit_assignment(self, student_id: str, assignment_number: int, 
                         submission_text: str) -> Dict[str, Any]:
        """Submit an assignment.
        
        Args:
            student_id: Student ID
            assignment_number: Assignment number
            submission_text: Assignment submission text
            
        Returns:
            Assignment record
        """
        self._check_module()
        
        submit_fn = getattr(self._boirsu_module, 'submit_assignment', None)
        if not submit_fn:
            raise RuntimeError("submit_assignment function not available")
        
        return submit_fn(student_id, assignment_number, submission_text)
    
    # ========================
    # Payment Integration
    # ========================
    
    def create_payment_link(self, student_name: str, email: str, 
                           career_path: str) -> Optional[tuple]:
        """Create a payment link for course enrollment.
        
        Args:
            student_name: Student name
            email: Student email
            career_path: Career path to enroll in
            
        Returns:
            Tuple of (payment_url, reference) or None if failed
        """
        self._check_module()
        
        create_fn = getattr(self._boirsu_module, 'create_enrollment_payment_link', None)
        if not create_fn:
            raise RuntimeError("create_enrollment_payment_link function not available")
        
        return create_fn(student_name, email, career_path)
    
    def verify_payment(self, reference: str) -> bool:
        """Verify if a payment was successful.
        
        Args:
            reference: Payment reference ID
            
        Returns:
            True if payment verified, False otherwise
        """
        self._check_module()
        
        verify_fn = getattr(self._boirsu_module, 'verify_enrollment_payment', None)
        if not verify_fn:
            raise RuntimeError("verify_enrollment_payment function not available")
        
        return verify_fn(reference)
    
    # ========================
    # Messaging Integration
    # ========================
    
    def send_whatsapp_message(self, phone: str, message: str) -> bool:
        """Send a WhatsApp message to a student.
        
        Args:
            phone: WhatsApp phone number
            message: Message text
            
        Returns:
            True if sent successfully
        """
        self._check_module()
        
        send_fn = getattr(self._boirsu_module, 'send_whatsapp', None)
        if not send_fn:
            raise RuntimeError("send_whatsapp function not available")
        
        return send_fn(phone, message)
    
    def send_morning_checkin(self) -> int:
        """Send morning check-in messages to all active students.
        
        Returns:
            Number of messages sent
        """
        self._check_module()
        
        send_fn = getattr(self._boirsu_module, 'send_morning_checkin', None)
        if not send_fn:
            raise RuntimeError("send_morning_checkin function not available")
        
        return send_fn()
    
    def send_motivation_messages(self) -> int:
        """Send random motivation messages to all active students.
        
        Returns:
            Number of messages sent
        """
        self._check_module()
        
        send_fn = getattr(self._boirsu_module, 'send_random_motivation', None)
        if not send_fn:
            raise RuntimeError("send_random_motivation function not available")
        
        return send_fn()
    
    def send_admin_report(self) -> bool:
        """Send private daily report to admin.
        
        Returns:
            True if sent successfully
        """
        self._check_module()
        
        send_fn = getattr(self._boirsu_module, 'send_admin_daily_report', None)
        if not send_fn:
            raise RuntimeError("send_admin_daily_report function not available")
        
        return send_fn()
    
    # ========================
    # Reporting & Analytics
    # ========================
    
    def get_course_statistics(self, career_path: str) -> Dict[str, Any]:
        """Get statistics for a specific course.
        
        Args:
            career_path: Career path slug
            
        Returns:
            Statistics dictionary with enrollment, completion, etc.
        """
        self._check_module()
        
        try:
            students = self.load_all_students()
            course_students = [s for s in students.values() 
                             if s.get('career_path') == career_path]
            
            active_count = len([s for s in course_students 
                              if s.get('payment_status') == 'paid'])
            
            avg_progress = sum(s.get('current_month', 0) 
                             for s in course_students) / len(course_students) if course_students else 0
            
            avg_grade = sum(s.get('current_grade', 0) 
                          for s in course_students) / len(course_students) if course_students else 0
            
            return {
                'career_path': career_path,
                'total_enrolled': len(course_students),
                'active_students': active_count,
                'avg_progress_month': round(avg_progress, 1),
                'avg_grade': round(avg_grade, 1)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_student_progress(self, student_id: str) -> Dict[str, Any]:
        """Get detailed progress report for a student.
        
        Args:
            student_id: Student ID
            
        Returns:
            Progress dictionary with grades, attendance, completion
        """
        self._check_module()
        
        student = self.get_student(student_id)
        if not student:
            raise ValueError(f"Student {student_id} not found")
        
        roadmap = self.get_course_roadmap(student.get('career_path', ''))
        total_months = len(roadmap.get('monthly_plan', []))
        current_month = student.get('current_month', 1)
        
        return {
            'student_id': student_id,
            'name': student.get('name'),
            'career_path': student.get('career_path'),
            'current_month': current_month,
            'total_months': total_months,
            'progress_percentage': round((current_month / total_months * 100) if total_months else 0, 1),
            'attendance_rate': student.get('attendance_rate', 0),
            'overall_grade': student.get('overall_grade', 'N/A'),
            'classes_attended': student.get('classes_attended', 0),
            'classes_missed': student.get('classes_missed', 0),
            'avg_quiz_score': student.get('avg_quiz_score', 0)
        }
