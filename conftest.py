"""Shared pytest fixtures. Available in every test file automatically."""

import pytest

from apps.accounts import services as account_services

PASSWORD = "blue-owl-42-ok"


@pytest.fixture
def teacher(db):
    user = account_services.create_teacher(
        full_name="Ana Reyes", email="ana@school.test", password=PASSWORD
    )
    user.email_verified = True
    user.save()
    return user


@pytest.fixture
def other_teacher(db):
    user = account_services.create_teacher(
        full_name="Ben Cruz", email="ben@school.test", password=PASSWORD
    )
    user.email_verified = True
    user.save()
    return user


@pytest.fixture
def student(db):
    return account_services.create_student(
        full_name="Maria Santos", username="maria", password=PASSWORD
    )


@pytest.fixture
def teacher_client(client, teacher):
    client.force_login(teacher)
    return client


@pytest.fixture
def student_client(client, student):
    client.force_login(student)
    return client


@pytest.fixture
def classroom(teacher):
    from apps.classrooms.models import Classroom

    return Classroom.objects.create(teacher=teacher, name="Grade 2 Math")
