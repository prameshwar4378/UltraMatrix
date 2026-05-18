from datetime import date

from django.test import TestCase

from Academic.models import AcademicYear
from Classes.models import ClassLevel, Division
from Schools.models import School
from Subjects.models import Subject, TeacherSubjectCapability
from Teachers.models import Teacher
from Timetables.models import ClassSection, LessonAllocation
from Timetables.views import _teacher_capability_missing_rows


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
