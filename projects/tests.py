import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    Assignment,
    ExternalCollaborator,
    InternalCollaborator,
    Project,
    Proposal,
    ResearchInstitute,
    Soldier,
)

User = get_user_model()


def make_proposal(**overrides):
    institute = overrides.pop("research_institute", None) or ResearchInstitute.objects.create(name="امنیت")
    today = timezone.localdate()
    defaults = dict(
        code="P-1",
        title="پروژه‌ی نمونه",
        research_institute=institute,
        planned_start_date=today,
        planned_end_date=today + datetime.timedelta(days=180),
        budget=1000,
    )
    defaults.update(overrides)
    return Proposal.objects.create(**defaults)


class ProposalWorkflowTests(TestCase):
    def test_happy_path_reaches_in_progress_and_creates_project(self):
        proposal = make_proposal()
        self.assertEqual(proposal.status, Proposal.Status.SUBMITTED)

        proposal.start_institute_review()
        self.assertEqual(proposal.status, Proposal.Status.INSTITUTE_REVIEW)

        proposal.record_institute_decision(Proposal.Decision.APPROVED, "خوب است")
        self.assertEqual(proposal.status, Proposal.Status.ACADEMY_REVIEW)

        proposal.record_academy_decision(Proposal.Decision.APPROVED, "تصویب شد")
        self.assertEqual(proposal.status, Proposal.Status.APPROVED)
        self.assertIsNotNone(proposal.decided_at)

        executor = InternalCollaborator.objects.create(
            full_name="مجری نمونه", employment_type=InternalCollaborator.EmploymentType.OFFICIAL
        )
        project = proposal.issue_executor_order(executor)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, Proposal.Status.IN_PROGRESS)
        self.assertIsNotNone(proposal.order_issued_at)
        self.assertEqual(project.status, Project.Status.IN_PROGRESS)
        self.assertEqual(project.executor, executor)
        self.assertEqual(proposal.project, project)

    def test_institute_revision_returns_to_institute_review(self):
        proposal = make_proposal()
        proposal.start_institute_review()
        proposal.record_institute_decision(Proposal.Decision.NEEDS_REVISION, "نیاز به اصلاح دارد")
        self.assertEqual(proposal.status, Proposal.Status.NEEDS_REVISION)
        self.assertEqual(proposal.pending_revision_target, Proposal.Council.INSTITUTE)

        proposal.resubmit_after_revision()
        self.assertEqual(proposal.status, Proposal.Status.INSTITUTE_REVIEW)
        self.assertEqual(proposal.current_version, 2)
        self.assertEqual(proposal.versions.count(), 1)

    def test_academy_revision_returns_directly_to_academy_review(self):
        proposal = make_proposal()
        proposal.start_institute_review()
        proposal.record_institute_decision(Proposal.Decision.APPROVED)
        proposal.record_academy_decision(Proposal.Decision.NEEDS_REVISION, "بودجه بازبینی شود")
        self.assertEqual(proposal.pending_revision_target, Proposal.Council.ACADEMY)

        proposal.resubmit_after_revision()
        self.assertEqual(proposal.status, Proposal.Status.ACADEMY_REVIEW)

    def test_rejection_at_institute_stops_process(self):
        proposal = make_proposal()
        proposal.start_institute_review()
        proposal.record_institute_decision(Proposal.Decision.REJECTED, "عدم تطابق با اولویت‌ها")
        self.assertEqual(proposal.status, Proposal.Status.REJECTED)
        with self.assertRaises(ValidationError):
            proposal.resubmit_after_revision()

    def test_cannot_record_institute_decision_outside_review_state(self):
        proposal = make_proposal()
        with self.assertRaises(ValidationError):
            proposal.record_institute_decision(Proposal.Decision.APPROVED)

    def test_cannot_issue_order_before_approval(self):
        proposal = make_proposal()
        executor = InternalCollaborator.objects.create(
            full_name="مجری", employment_type=InternalCollaborator.EmploymentType.OFFICIAL
        )
        with self.assertRaises(ValidationError):
            proposal.issue_executor_order(executor)


class ProjectProgressTests(TestCase):
    def setUp(self):
        self.institute = ResearchInstitute.objects.create(name="امنیت")

    def make_project(self, progress_percent, start_offset, end_offset):
        today = timezone.localdate()
        return Project.objects.create(
            code="PJ-1",
            title="پروژه",
            research_institute=self.institute,
            planned_start_date=today + datetime.timedelta(days=start_offset),
            planned_end_date=today + datetime.timedelta(days=end_offset),
            status=Project.Status.IN_PROGRESS,
            progress_percent=progress_percent,
        )

    def test_delay_percent_positive_when_behind_schedule(self):
        project = self.make_project(progress_percent=10, start_offset=-100, end_offset=100)
        self.assertEqual(project.expected_progress_percent, 50)
        self.assertEqual(project.delay_percent, 40)
        self.assertTrue(project.is_delayed)

    def test_delay_percent_zero_when_ahead_of_schedule(self):
        project = self.make_project(progress_percent=90, start_offset=-100, end_offset=100)
        self.assertEqual(project.delay_percent, 0)
        self.assertFalse(project.is_delayed)

    def test_not_started_project_is_not_delayed(self):
        project = self.make_project(progress_percent=0, start_offset=10, end_offset=200)
        self.assertEqual(project.expected_progress_percent, 0)
        self.assertFalse(project.is_delayed)


class AssignmentTests(TestCase):
    def setUp(self):
        self.institute = ResearchInstitute.objects.create(name="امنیت")
        today = timezone.localdate()
        self.project = Project.objects.create(
            code="PJ-2",
            title="پروژه",
            research_institute=self.institute,
            planned_start_date=today,
            planned_end_date=today + datetime.timedelta(days=100),
            status=Project.Status.IN_PROGRESS,
        )
        self.soldier = Soldier.objects.create(
            full_name="سرباز نمونه",
            service_start_date=today,
            service_end_date=today + datetime.timedelta(days=300),
        )

    def test_allocation_percent_must_be_between_1_and_100(self):
        from django.contrib.contenttypes.models import ContentType

        assignment = Assignment(
            project=self.project,
            person_content_type=ContentType.objects.get_for_model(self.soldier),
            person_object_id=self.soldier.pk,
            allocation_percent=150,
        )
        with self.assertRaises(ValidationError):
            assignment.clean()

    def test_workload_helpers_sum_active_allocations(self):
        from django.contrib.contenttypes.models import ContentType

        Assignment.objects.create(
            project=self.project,
            person_content_type=ContentType.objects.get_for_model(self.soldier),
            person_object_id=self.soldier.pk,
            allocation_percent=60,
        )
        self.assertEqual(self.soldier.active_allocation_percent(), 60)
        self.assertEqual(self.soldier.active_project_count(), 1)


class AdminEntityCreationTests(TestCase):
    """اطمینان از اینکه فرم‌های سفارشی مجری/نیرو در پنل مدیریت واقعاً موجودیت می‌سازند."""

    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(username="siteadmin", password="pass12345", email="")
        self.client.login(username="siteadmin", password="pass12345")
        self.institute = ResearchInstitute.objects.create(name="امنیت")

    def test_create_project_with_executor_via_admin_form(self):
        from django.contrib.contenttypes.models import ContentType

        executor = InternalCollaborator.objects.create(
            full_name="دکتر تستی", employment_type=InternalCollaborator.EmploymentType.OFFICIAL
        )
        ct = ContentType.objects.get_for_model(executor)
        today = timezone.localdate()

        response = self.client.post(
            reverse("admin:projects_project_add"),
            data={
                "code": "TST-1",
                "title": "پروژه‌ی آزمایشی",
                "research_institute": self.institute.pk,
                "project_type": "research",
                "client_or_funder": "",
                "planned_start_date": today.isoformat(),
                "planned_end_date": (today + datetime.timedelta(days=30)).isoformat(),
                "actual_start_date": "",
                "actual_end_date": "",
                "status": Project.Status.DEFINED,
                "progress_percent": 0,
                "budget": 0,
                "cost_spent": 0,
                "executor_choice": f"{ct.pk}:{executor.pk}",
                "executor_assigned_date": "",
                "assignments-TOTAL_FORMS": 0,
                "assignments-INITIAL_FORMS": 0,
                "assignments-MIN_NUM_FORMS": 0,
                "assignments-MAX_NUM_FORMS": 1000,
            },
        )
        self.assertEqual(response.status_code, 302, response.context["adminform"].form.errors if response.status_code == 200 else None)
        project = Project.objects.get(code="TST-1")
        self.assertEqual(project.executor, executor)

    def test_create_assignment_with_person_via_admin_form(self):
        project = Project.objects.create(
            code="TST-2",
            title="پروژه‌ی دوم",
            research_institute=self.institute,
            planned_start_date=timezone.localdate(),
            planned_end_date=timezone.localdate() + datetime.timedelta(days=10),
        )
        soldier = Soldier.objects.create(
            full_name="سرباز تستی",
            service_start_date=timezone.localdate(),
            service_end_date=timezone.localdate() + datetime.timedelta(days=200),
        )
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(soldier)

        response = self.client.post(
            reverse("admin:projects_assignment_add"),
            data={
                "project": project.pk,
                "person_choice": f"{ct.pk}:{soldier.pk}",
                "allocation_percent": 40,
                "role_description": "تحلیلگر",
                "start_date": "",
                "end_date": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        assignment = Assignment.objects.get(project=project)
        self.assertEqual(assignment.person, soldier)
        self.assertEqual(assignment.allocation_percent, 40)


class ReportAccessTests(TestCase):
    def setUp(self):
        self.client = Client()
        Group.objects.get_or_create(name="ادمین کل سامانه")
        self.admin_user = User.objects.create_user(username="admin1", password="pass12345", is_superuser=True, is_staff=True)
        self.plain_user = User.objects.create_user(username="plain1", password="pass12345")

    def test_report_home_requires_login(self):
        response = self.client.get(reverse("report_home"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_view_restricted_report(self):
        self.client.login(username="admin1", password="pass12345")
        response = self.client.get(reverse("approval_rate"))
        self.assertEqual(response.status_code, 200)

    def test_plain_user_forbidden_from_restricted_report(self):
        self.client.login(username="plain1", password="pass12345")
        response = self.client.get(reverse("approval_rate"))
        self.assertEqual(response.status_code, 403)
