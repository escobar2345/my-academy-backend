import importlib.util
import pathlib
import sys


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "ai_learning_system_v4 (14).py"


def load_module():
    spec = importlib.util.spec_from_file_location("ai_learning_system_v4", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_boi_mode_menu_hides_internet_resource_options():
    module = load_module()
    lines = "\n".join(module.build_learning_menu_lines(boi_mode=True))

    assert "Read this section" in lines
    assert "God Mode internet resources for this section" not in lines
    assert "God Mode resources for the full course" not in lines


def test_boi_study_plan_is_built_for_monthly_schedule():
    module = load_module()
    sections = module.build_boi_study_plan(
        topic="Python for beginners",
        duration_months=3,
        classes_per_week=3,
        class_minutes=60,
        client=None,
    )

    assert len(sections) >= 8
    assert sections[0]["duration"] <= 60
    assert "week" in sections[0]["title"].lower() or "monday" in sections[0]["title"].lower()


def test_student_registration_duration_and_timetable_are_created_from_course_data():
    module = load_module()
    duration = module.infer_student_duration_months(
        course_name="Data Science & AI",
        experience_level="beginner",
        goals=["💼 Get a tech job", "📈 Level up in current job"],
    )
    assert 3 <= duration <= 6

    timetable = module.build_student_timetable(
        course_name="Data Science & AI",
        duration_months=duration,
        track="Weekday · evenings",
        class_minutes=60,
    )

    assert isinstance(timetable, list)
    assert len(timetable) >= 12
    assert "countdown" in timetable[0]
    assert "topic" in timetable[0]
