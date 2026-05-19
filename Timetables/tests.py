from datetime import date

from django.test import TestCase

from Academic.models import AcademicYear, BellSchedule, Day, Period
from Classes.models import ClassLevel, Division
from Schools.models import School
from Subjects.models import Subject, TeacherSubjectCapability
from Teachers.models import Teacher
from Timetables.models import ClassSection, LessonAllocation, Timetable, TimetableConfiguration
from Timetables.views import _teacher_capability_missing_rows
from Timetables.views_builder import _validate_timetable_payload


class TeacherAllocationRowsTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.academic_year = AcademicYear.objects.create(
            school=self.school,
            name="2026-27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.teacher = Teacher.objects.create(
            school=self.school,
            name="Priya",
            max_periods_per_week=40,
        )
        self.class_level = ClassLevel.objects.create(
            school=self.school,
            name="5th",
            sort_order=5,
            section_type="PRIMARY",
            is_active=True,
        )
        self.division_c = Division.objects.create(
            school=self.school,
            name="C",
            sort_order=3,
            is_active=True,
        )
        self.class_section = ClassSection.objects.create(
            school=self.school,
            class_level=self.class_level,
            division=self.division_c,
            is_active=True,
        )
        self.computer = Subject.objects.create(
            school=self.school,
            name="Computer",
            section_type="BOTH",
            subject_type="PRACTICAL",
            is_active=True,
        )

    def test_new_capability_is_prepared_as_missing_allocation_row(self):
        capability = TeacherSubjectCapability.objects.create(
            school=self.school,
            teacher=self.teacher,
            subject=self.computer,
            priority="PRIMARY",
        )
        capability.class_sections.add(self.class_section)

        rows = _teacher_capability_missing_rows(
            self.school,
            self.teacher,
            self.academic_year,
            existing_keys=set(),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["class_section_id"], self.class_section.id)
        self.assertEqual(rows[0]["subject_id"], self.computer.id)
        self.assertTrue(rows[0]["requires_double_period"])

    def test_existing_allocation_is_not_duplicated(self):
        LessonAllocation.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            class_section=self.class_section,
            subject=self.computer,
            teacher=self.teacher,
            weekly_periods=5,
            requires_double_period=True,
            is_active=True,
        )
        capability = TeacherSubjectCapability.objects.create(
            school=self.school,
            teacher=self.teacher,
            subject=self.computer,
            priority="PRIMARY",
        )
        capability.class_sections.add(self.class_section)

        rows = _teacher_capability_missing_rows(
            self.school,
            self.teacher,
            self.academic_year,
            existing_keys={(self.class_section.id, self.computer.id)},
        )

        self.assertEqual(rows, [])


class TimetableValidationScopeTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Scope School")
        self.academic_year = AcademicYear.objects.create(
            school=self.school,
            name="2026-27",
            start_date=date(2026, 4, 1),
            end_date=date(2027, 3, 31),
            is_active=True,
        )
        self.timetable = Timetable.objects.create(
            school=self.school,
            academic_year=self.academic_year,
            name="Primary Scope",
            timetable_type="PRIMARY",
        )
        self.class_level = ClassLevel.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="5th",
            sort_order=5,
            section_type="PRIMARY",
            is_active=True,
        )
        self.division = Division.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="A",
            sort_order=1,
            is_active=True,
        )
        self.class_section = ClassSection.objects.create(
            school=self.school,
            timetable=self.timetable,
            class_level=self.class_level,
            division=self.division,
            is_active=True,
        )
        self.selected_teacher = Teacher.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="Selected Teacher",
        )
        self.unselected_teacher = Teacher.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="Unselected Teacher",
        )
        self.subject = Subject.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="Math",
            section_type="BOTH",
            subject_type="THEORY",
            is_active=True,
        )
        TeacherSubjectCapability.objects.create(
            school=self.school,
            timetable=self.timetable,
            teacher=self.unselected_teacher,
            subject=self.subject,
            priority="PRIMARY",
        )
        self.day = Day.objects.create(
            school=self.school,
            timetable=self.timetable,
            name="Monday",
            short_name="Mon",
            sort_order=1,
            day_type="WEEKDAY",
            is_working=True,
        )
        self.bell_schedule = BellSchedule.objects.create(
            school=self.school,
            timetable=self.timetable,
            academic_year=self.academic_year,
            name="Main Bell",
            is_active=True,
        )
        self.period = Period.objects.create(
            school=self.school,
            timetable=self.timetable,
            bell_schedule=self.bell_schedule,
            day_type="WEEKDAY",
            name="Period 1",
            period_number=1,
            start_time="09:00",
            end_time="09:40",
            period_type="TEACHING",
            is_teaching_period=True,
        )
        self.configuration = TimetableConfiguration.objects.create(
            timetable=self.timetable,
            bell_schedule=self.bell_schedule,
        )
        self.configuration.class_sections.add(self.class_section)
        self.configuration.teachers.add(self.selected_teacher)
        self.configuration.working_days.add(self.day)
        self.configuration.periods.add(self.period)

    def test_validation_rejects_teacher_outside_selected_timetable_scope(self):
        validation = _validate_timetable_payload(self.school, self.timetable, [{
            "class_section_id": self.class_section.id,
            "day_id": self.day.id,
            "day_name": self.day.name,
            "period_id": self.period.id,
            "period_name": self.period.name,
            "subject_id": self.subject.id,
            "teacher_id": self.unselected_teacher.id,
            "room_id": None,
        }])

        self.assertIn("invalid or inactive teacher", " ".join(validation["errors"]))
