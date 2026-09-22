#!/usr/bin/env python
"""Verify the service-based architecture implementation.

Tests:
1. Service container initialization
2. Service registration and instantiation
3. BoiRsuService functionality
4. Dependency injection
"""

import sys
import traceback


def test_service_container():
    """Test service container creation and basic operations."""
    print("\n" + "="*60)
    print("TEST 1: Service Container")
    print("="*60)
    
    try:
        from app.services.container import ServiceContainer, Service
        
        class TestService(Service):
            def initialize(self):
                self.initialized = True
            
            def shutdown(self):
                self.initialized = False
            
            def test_method(self):
                return "test"
        
        container = ServiceContainer()
        container.register(TestService)
        
        # Get service
        service = container.get(TestService)
        assert service.initialized, "Service not initialized"
        assert service.test_method() == "test", "Service method failed"
        
        # Check singleton
        service2 = container.get(TestService)
        assert service is service2, "Service not singleton"
        
        # Shutdown
        container.shutdown_all()
        assert not service.initialized, "Service not shut down"
        
        print("✅ Service Container: PASS")
        return True
    except Exception as e:
        print(f"❌ Service Container: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_boirsu_service_import():
    """Test BoiRsuService can be imported and instantiated."""
    print("\n" + "="*60)
    print("TEST 2: BoiRsuService Import & Instantiation")
    print("="*60)
    
    try:
        from app.services.boirsu_service import BoiRsuService
        from app.services.container import ServiceContainer
        
        container = ServiceContainer()
        container.register(BoiRsuService)
        
        service = container.get(BoiRsuService)
        assert service is not None, "Service not created"
        
        # Check service has expected methods
        expected_methods = [
            'list_courses', 'get_course_roadmap', 'enroll_student',
            'get_student', 'load_all_students', 'record_attendance',
            'send_whatsapp_message', 'get_student_count'
        ]
        
        for method_name in expected_methods:
            assert hasattr(service, method_name), f"Missing method: {method_name}"
        
        print(f"✅ BoiRsuService: PASS ({len(expected_methods)} methods verified)")
        container.shutdown_all()
        return True
    except Exception as e:
        print(f"❌ BoiRsuService: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_boirsu_service_courses():
    """Test BoiRsuService can list courses."""
    print("\n" + "="*60)
    print("TEST 3: BoiRsuService.list_courses()")
    print("="*60)
    
    try:
        from app.services.boirsu_service import BoiRsuService
        from app.services.container import ServiceContainer
        
        container = ServiceContainer()
        container.register(BoiRsuService)
        service = container.get(BoiRsuService)
        
        courses = service.list_courses()
        assert isinstance(courses, list), "Courses not a list"
        assert len(courses) > 0, "No courses returned"
        
        # Check course structure
        first_course = courses[0]
        expected_fields = ['slug', 'title', 'duration', 'description']
        for field in expected_fields:
            assert field in first_course, f"Missing field: {field}"
        
        print(f"✅ BoiRsuService.list_courses(): PASS ({len(courses)} courses found)")
        for course in courses:
            print(f"   - {course['title']} ({course['slug']})")
        
        container.shutdown_all()
        return True
    except Exception as e:
        print(f"❌ BoiRsuService.list_courses(): FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_boirsu_service_students():
    """Test BoiRsuService student management methods."""
    print("\n" + "="*60)
    print("TEST 4: BoiRsuService Student Management")
    print("="*60)
    
    try:
        from app.services.boirsu_service import BoiRsuService
        from app.services.container import ServiceContainer
        
        container = ServiceContainer()
        container.register(BoiRsuService)
        service = container.get(BoiRsuService)
        
        # Test student count
        count = service.get_student_count()
        assert isinstance(count, int), "Student count not an int"
        print(f"✅ get_student_count(): {count} students")
        
        # Test active students
        active = service.get_active_students()
        assert isinstance(active, list), "Active students not a list"
        print(f"✅ get_active_students(): {len(active)} active students")
        
        # Test load all students
        all_students = service.load_all_students()
        assert isinstance(all_students, dict), "All students not a dict"
        print(f"✅ load_all_students(): {len(all_students)} total students")
        
        container.shutdown_all()
        return True
    except Exception as e:
        print(f"❌ BoiRsuService Student Management: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_domain_services():
    """Test other domain services can be imported."""
    print("\n" + "="*60)
    print("TEST 5: Domain Services Availability")
    print("="*60)
    
    try:
        from app.services.domain_services import (
            GraphService, SimulationService, ReportService, YouTubeService
        )
        from app.services.container import ServiceContainer
        
        container = ServiceContainer()
        container.register(GraphService)
        container.register(SimulationService)
        container.register(ReportService)
        container.register(YouTubeService)
        
        # Verify all services can be instantiated
        graph_svc = container.get(GraphService)
        sim_svc = container.get(SimulationService)
        report_svc = container.get(ReportService)
        youtube_svc = container.get(YouTubeService)
        
        services = [
            ('GraphService', graph_svc),
            ('SimulationService', sim_svc),
            ('ReportService', report_svc),
            ('YouTubeService', youtube_svc),
        ]
        
        for name, svc in services:
            assert svc is not None, f"{name} is None"
            print(f"✅ {name}: Available")

        # Ensure the remaining domain services are actually implemented instead of
        # stubbed placeholders that raise NotImplementedError.
        try:
            graph_svc.build_graph('proj_test', 'missing.txt')
        except (FileNotFoundError, ValueError):
            pass
        else:
            raise AssertionError('GraphService.build_graph should not be a stub')

        try:
            sim_svc.start_simulation('proj_test', 'twitter', {'graph_id': 'g_test'})
        except ValueError:
            pass
        else:
            assert isinstance(sim_svc.start_simulation('proj_test', 'twitter', {'graph_id': 'g_test'}), str), \
                'SimulationService.start_simulation should return a simulation id'

        try:
            report_svc.generate_report('proj_test', 'summary')
        except ValueError:
            pass
        else:
            assert isinstance(report_svc.generate_report('proj_test', 'summary'), dict), \
                'ReportService.generate_report should return a dict'

        try:
            youtube_svc.search_courses('python basics', 1)
        except (RuntimeError, ValueError):
            pass
        else:
            assert isinstance(youtube_svc.search_courses('python basics', 1), list), \
                'YouTubeService.search_courses should return a list'
        
        container.shutdown_all()
        return True
    except Exception as e:
        print(f"❌ Domain Services: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_get_service_function():
    """Test the global get_service convenience function."""
    print("\n" + "="*60)
    print("TEST 6: Global get_service() Function")
    print("="*60)
    
    try:
        from app.services.boirsu_service import BoiRsuService
        from app.services.container import get_service, get_container
        
        # Initialize container with service
        container = get_container()
        container.register(BoiRsuService)
        
        # Get via convenience function
        service = get_service(BoiRsuService)
        assert service is not None, "Service not retrieved"
        assert isinstance(service, BoiRsuService), "Wrong service type"
        
        print("✅ get_service() function: PASS")
        
        return True
    except Exception as e:
        print(f"❌ get_service() function: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def test_api_routes():
    """Test that service-based API routes can be imported."""
    print("\n" + "="*60)
    print("TEST 7: Service-Based API Routes")
    print("="*60)
    
    try:
        from app.api.boirsu_v2 import bp as boirsu_bp
        
        assert boirsu_bp is not None, "Blueprint not created"
        assert boirsu_bp.name == 'boirsu', "Blueprint name incorrect"
        
        # Check blueprint has routes defined via deferred_functions
        route_count = len(boirsu_bp.deferred_functions)
        print(f"✅ Service-based API routes: PASS ({route_count} route functions defined)")
        
        # List some route definitions
        routes = [
            '/courses',
            '/courses/<career_path>',
            '/student',
            '/student/<student_id>',
            '/students',
            '/payment/create',
            '/health'
        ]
        
        for route in routes[:5]:
            print(f"   - {route}")
        
        return True
    except Exception as e:
        print(f"❌ Service-Based API Routes: FAIL")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("SERVICE-BASED ARCHITECTURE VERIFICATION")
    print("="*60)
    
    tests = [
        test_service_container,
        test_boirsu_service_import,
        test_boirsu_service_courses,
        test_boirsu_service_students,
        test_domain_services,
        test_get_service_function,
        test_api_routes,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n❌ Test {test_func.__name__} crashed")
            print(f"   Error: {e}")
            traceback.print_exc()
            results.append((test_func.__name__, False))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Service-based architecture is working.")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please review errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
