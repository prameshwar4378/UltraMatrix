# Generated for daily proxy lecture adjustment support.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Academic", "0002_day_day_type_period_day_type"),
        ("Rooms", "0001_initial"),
        ("Subjects", "0002_alter_subject_section_type"),
        ("Teachers", "0001_initial"),
        ("Timetables", "0004_timetableentry"),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherDailyStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("status_type", models.CharField(choices=[("LEAVE", "On Leave"), ("IN_SCHOOL_UNAVAILABLE", "In School But Unavailable")], default="LEAVE", max_length=30)),
                ("full_day", models.BooleanField(default=True)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="Schools.school")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_statuses", to="Teachers.teacher")),
                ("unavailable_periods", models.ManyToManyField(blank=True, related_name="teacher_daily_statuses", to="Academic.period")),
            ],
            options={
                "ordering": ("-date", "teacher__name"),
                "unique_together": {("teacher", "date")},
            },
        ),
        migrations.CreateModel(
            name="LectureAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("day_id_value", models.CharField(max_length=50)),
                ("day_name", models.CharField(max_length=50)),
                ("period_id_value", models.CharField(max_length=50)),
                ("period_name", models.CharField(max_length=100)),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("ASSIGNED", "Assigned"), ("CANCELLED", "Cancelled")], default="PENDING", max_length=20)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("admin_note", models.TextField(blank=True)),
                ("is_locked", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("class_section", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="Timetables.classsection")),
                ("original_entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_adjustments", to="Timetables.timetableentry")),
                ("original_teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="original_daily_adjustments", to="Teachers.teacher")),
                ("proxy_teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="proxy_daily_adjustments", to="Teachers.teacher")),
                ("room", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="Rooms.room")),
                ("subject", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="Subjects.subject")),
                ("teacher_status", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lecture_adjustments", to="Timetables.teacherdailystatus")),
                ("timetable", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lecture_adjustments", to="Timetables.timetable")),
            ],
            options={
                "ordering": ("date", "day_name", "period_id_value", "class_section__class_level__sort_order"),
                "unique_together": {("date", "original_entry")},
            },
        ),
    ]
