from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ResearchInstitute(models.Model):
    """پژوهشکده‌ی تخصصی (مثلاً امنیت، هوش مصنوعی)."""

    name = models.CharField("نام پژوهشکده", max_length=200, unique=True)

    class Meta:
        verbose_name = "پژوهشکده"
        verbose_name_plural = "پژوهشکده‌ها"

    def __str__(self):
        return self.name


class ProjectType(models.TextChoices):
    RESEARCH = "research", "پژوهشی"
    EXECUTIVE = "executive", "اجرایی"
    SERVICE = "service", "خدماتی"
    OTHER = "other", "سایر"


class PersonMixin(models.Model):
    """فیلدهای مشترک نیروهای انسانی (سرباز، همکار داخلی، همکار خارجی)."""

    full_name = models.CharField("نام و مشخصات", max_length=200)
    specialty = models.CharField("تخصص", max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    assignments = GenericRelation(
        "Assignment",
        content_type_field="person_content_type",
        object_id_field="person_object_id",
        related_query_name="%(class)s",
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.full_name

    def active_allocation_percent(self):
        """مجموع سهم زمانی فرد در پروژه‌های در حال اجرا."""
        return (
            self.assignments.filter(project__status=Project.Status.IN_PROGRESS)
            .aggregate(total=models.Sum("allocation_percent"))
            .get("total")
            or 0
        )

    def active_project_count(self):
        return self.assignments.filter(project__status=Project.Status.IN_PROGRESS).count()


class Soldier(PersonMixin):
    """سربازان (مشمولان طرح امریه یا سایر طرح‌های جایگزین خدمت)."""

    class ServicePlan(models.TextChoices):
        AMRIEH = "amrieh", "امریه"
        ALTERNATIVE = "alternative", "طرح جایگزین خدمت"
        OTHER = "other", "سایر"

    degree = models.CharField("مدرک تحصیلی", max_length=200, blank=True)
    service_plan = models.CharField(
        "نوع طرح خدمت", max_length=20, choices=ServicePlan.choices, default=ServicePlan.AMRIEH
    )
    service_start_date = models.DateField("تاریخ شروع خدمت")
    service_end_date = models.DateField("تاریخ پایان خدمت")
    supervisor = models.ForeignKey(
        "InternalCollaborator",
        verbose_name="سرپرست مستقیم",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supervised_soldiers",
    )

    class Meta:
        verbose_name = "سرباز"
        verbose_name_plural = "سربازان"

    def is_service_ending_within(self, days=60):
        remaining = (self.service_end_date - timezone.localdate()).days
        return 0 <= remaining <= days


class InternalCollaborator(PersonMixin):
    """همکاران داخلی (کارکنان رسمی، پیمانی یا قراردادی پژوهشگاه)."""

    class EmploymentType(models.TextChoices):
        OFFICIAL = "official", "رسمی"
        CONTRACTUAL = "contractual", "پیمانی"
        PROJECT_BASED = "project_based", "قراردادی"

    employment_type = models.CharField(
        "نوع استخدام", max_length=20, choices=EmploymentType.choices
    )
    organizational_unit = models.CharField("واحد سازمانی", max_length=200, blank=True)
    role_title = models.CharField("نقش/سمت", max_length=200, blank=True)

    class Meta:
        verbose_name = "همکار داخلی"
        verbose_name_plural = "همکاران داخلی"


class ExternalCollaborator(PersonMixin):
    """همکاران خارجی (مشاوران، اساتید دانشگاه، پیمانکاران، شرکت‌های همکار)."""

    class CollaborationType(models.TextChoices):
        CONSULTING = "consulting", "مشاوره"
        CONTRACTING = "contracting", "پیمانکاری"
        RESEARCH = "research", "پژوهشی"

    collaboration_type = models.CharField(
        "نوع همکاری", max_length=20, choices=CollaborationType.choices
    )
    contract_number = models.CharField("شماره قرارداد", max_length=100, blank=True)
    contract_amount = models.DecimalField(
        "مبلغ قرارداد", max_digits=16, decimal_places=0, null=True, blank=True
    )
    contract_start_date = models.DateField("تاریخ شروع قرارداد", null=True, blank=True)
    contract_end_date = models.DateField("تاریخ پایان قرارداد", null=True, blank=True)
    deliverables_status = models.CharField(
        "وضعیت تحویل تعهدات", max_length=200, blank=True
    )

    class Meta:
        verbose_name = "همکار خارجی"
        verbose_name_plural = "همکاران خارجی"

    def is_contract_ending_within(self, days=60):
        if not self.contract_end_date:
            return False
        remaining = (self.contract_end_date - timezone.localdate()).days
        return 0 <= remaining <= days


EXECUTOR_ALLOWED_MODELS = ("internalcollaborator", "externalcollaborator")
PERSON_ALLOWED_MODELS = ("soldier", "internalcollaborator", "externalcollaborator")


class Project(models.Model):
    """پروژه: موجودیت محوری سیستم."""

    class Status(models.TextChoices):
        DEFINED = "defined", "تعریف‌شده"
        IN_PROGRESS = "in_progress", "در حال اجرا"
        STOPPED = "stopped", "متوقف"
        FINISHED = "finished", "خاتمه‌یافته"

    code = models.CharField("کد پروژه", max_length=50, unique=True)
    title = models.CharField("عنوان پروژه", max_length=300)
    proposal = models.OneToOneField(
        "Proposal",
        verbose_name="پروپوزال مبنا",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project",
    )
    research_institute = models.ForeignKey(
        ResearchInstitute, verbose_name="پژوهشکده", on_delete=models.PROTECT, related_name="projects"
    )
    project_type = models.CharField(
        "نوع پروژه", max_length=20, choices=ProjectType.choices, default=ProjectType.RESEARCH
    )
    client_or_funder = models.CharField("کارفرما / منبع تأمین", max_length=200, blank=True)

    planned_start_date = models.DateField("تاریخ شروع برنامه‌ریزی‌شده")
    planned_end_date = models.DateField("تاریخ پایان برنامه‌ریزی‌شده")
    actual_start_date = models.DateField("تاریخ شروع واقعی", null=True, blank=True)
    actual_end_date = models.DateField("تاریخ پایان واقعی", null=True, blank=True)

    status = models.CharField(
        "وضعیت", max_length=20, choices=Status.choices, default=Status.DEFINED
    )
    progress_percent = models.PositiveSmallIntegerField("درصد پیشرفت واقعی", default=0)

    budget = models.DecimalField("بودجه", max_digits=18, decimal_places=0, default=0)
    cost_spent = models.DecimalField("هزینه‌ی مصرف‌شده", max_digits=18, decimal_places=0, default=0)

    executor_content_type = models.ForeignKey(
        ContentType,
        verbose_name="نوع موجودیت مجری",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"model__in": EXECUTOR_ALLOWED_MODELS},
        related_name="+",
    )
    executor_object_id = models.PositiveIntegerField(null=True, blank=True)
    executor = GenericForeignKey("executor_content_type", "executor_object_id")
    executor_assigned_date = models.DateField("تاریخ انتصاب مجری", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه‌ها"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def clean(self):
        if self.executor_content_type and self.executor_content_type.model not in EXECUTOR_ALLOWED_MODELS:
            raise ValidationError("مجری پروژه فقط می‌تواند همکار داخلی یا همکار خارجی باشد.")

    @property
    def planned_duration_days(self):
        return (self.planned_end_date - self.planned_start_date).days

    @property
    def elapsed_days(self):
        start = self.actual_start_date or self.planned_start_date
        end = min(timezone.localdate(), self.planned_end_date)
        return max((end - start).days, 0)

    @property
    def expected_progress_percent(self):
        """درصد پیشرفتی که طبق زمان‌بندی برنامه انتظار می‌رود."""
        total = self.planned_duration_days
        if total <= 0:
            return 100
        today = timezone.localdate()
        if today <= self.planned_start_date:
            return 0
        if today >= self.planned_end_date:
            return 100
        return round((today - self.planned_start_date).days / total * 100)

    @property
    def delay_percent(self):
        """میزان عقب‌ماندگی پیشرفت واقعی نسبت به برنامه (عدد مثبت یعنی تأخیر)."""
        return max(self.expected_progress_percent - self.progress_percent, 0)

    @property
    def is_delayed(self):
        return self.status == self.Status.IN_PROGRESS and self.delay_percent > 0

    def total_allocation_percent(self):
        return self.assignments.aggregate(total=models.Sum("allocation_percent")).get("total") or 0


class Assignment(models.Model):
    """تخصیص فرد (سرباز/همکار داخلی/همکار خارجی) به پروژه با سهم زمانی مشخص."""

    project = models.ForeignKey(Project, verbose_name="پروژه", on_delete=models.CASCADE, related_name="assignments")

    person_content_type = models.ForeignKey(
        ContentType,
        verbose_name="نوع نیرو",
        on_delete=models.CASCADE,
        limit_choices_to={"model__in": PERSON_ALLOWED_MODELS},
        related_name="+",
    )
    person_object_id = models.PositiveIntegerField()
    person = GenericForeignKey("person_content_type", "person_object_id")

    allocation_percent = models.PositiveSmallIntegerField("سهم زمانی (درصد)")
    role_description = models.CharField("نقش در پروژه", max_length=200, blank=True)
    start_date = models.DateField("تاریخ شروع تخصیص", null=True, blank=True)
    end_date = models.DateField("تاریخ پایان تخصیص", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تخصیص نیرو"
        verbose_name_plural = "تخصیص‌های نیرو"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "person_content_type", "person_object_id"],
                name="unique_assignment_per_project_person",
            )
        ]

    def __str__(self):
        return f"{self.person} -> {self.project} ({self.allocation_percent}%)"

    def clean(self):
        if self.person_content_type and self.person_content_type.model not in PERSON_ALLOWED_MODELS:
            raise ValidationError("نیروی تخصیص‌یافته باید سرباز، همکار داخلی یا همکار خارجی باشد.")
        if self.allocation_percent is not None and not (0 < self.allocation_percent <= 100):
            raise ValidationError("سهم زمانی باید عددی بین ۱ تا ۱۰۰ باشد.")


class Proposal(models.Model):
    """پروپوزال پروژه و روند تصویب آن در شورای پژوهشکده و شورای پژوهشگاه."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "ارسال‌شده"
        INSTITUTE_REVIEW = "institute_review", "در حال بررسی در پژوهشکده"
        ACADEMY_REVIEW = "academy_review", "در حال بررسی در پژوهشگاه"
        NEEDS_REVISION = "needs_revision", "نیازمند اصلاح"
        REJECTED = "rejected", "ردشده"
        APPROVED = "approved", "تأییدشده (در انتظار صدور حکم)"
        IN_PROGRESS = "in_progress", "در حال اجرا"

    class Council(models.TextChoices):
        INSTITUTE = "institute", "شورای علمی پژوهشکده"
        ACADEMY = "academy", "شورای پژوهشی پژوهشگاه"

    class Decision(models.TextChoices):
        APPROVED = "approved", "تأیید"
        NEEDS_REVISION = "needs_revision", "نیازمند اصلاح"
        REJECTED = "rejected", "رد"

    code = models.CharField("کد پروپوزال", max_length=50, unique=True)
    title = models.CharField("عنوان", max_length=300)
    research_institute = models.ForeignKey(
        ResearchInstitute, verbose_name="پژوهشکده", on_delete=models.PROTECT, related_name="proposals"
    )

    executor_content_type = models.ForeignKey(
        ContentType,
        verbose_name="نوع موجودیت مجری پیشنهادی",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        limit_choices_to={"model__in": EXECUTOR_ALLOWED_MODELS},
        related_name="+",
    )
    executor_object_id = models.PositiveIntegerField(null=True, blank=True)
    executor = GenericForeignKey("executor_content_type", "executor_object_id")

    project_type = models.CharField(
        "نوع پروژه", max_length=20, choices=ProjectType.choices, default=ProjectType.RESEARCH
    )
    client_or_funder = models.CharField("کارفرما / منبع تأمین", max_length=200, blank=True)
    planned_start_date = models.DateField("تاریخ شروع پیشنهادی")
    planned_end_date = models.DateField("تاریخ پایان پیشنهادی")
    budget = models.DecimalField("بودجه پیشنهادی", max_digits=18, decimal_places=0, default=0)
    description = models.TextField("شرح پروپوزال", blank=True)
    resource_requirement = models.TextField("اعلام نیاز نیرویی", blank=True)

    status = models.CharField("وضعیت", max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    pending_revision_target = models.CharField(
        "شورای مرجع اصلاحیه", max_length=20, choices=Council.choices, null=True, blank=True
    )
    current_version = models.PositiveSmallIntegerField(default=1)

    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField("زمان تصویب نهایی", null=True, blank=True)
    order_issued_at = models.DateTimeField("زمان صدور حکم مجری", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "پروپوزال"
        verbose_name_plural = "پروپوزال‌ها"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    # --- workflow ---------------------------------------------------

    def _snapshot_version(self, created_by=None):
        return ProposalVersion.objects.create(
            proposal=self,
            version_number=self.current_version,
            title=self.title,
            description=self.description,
            budget=self.budget,
            planned_start_date=self.planned_start_date,
            planned_end_date=self.planned_end_date,
            resource_requirement=self.resource_requirement,
            created_by=created_by,
        )

    def start_institute_review(self):
        if self.status != self.Status.SUBMITTED:
            raise ValidationError("فقط پروپوزال ارسال‌شده قابل ورود به بررسی پژوهشکده است.")
        self.status = self.Status.INSTITUTE_REVIEW
        self.save(update_fields=["status", "updated_at"])

    def _record_decision(self, council, decision, comments, recorded_by):
        ProposalDecision.objects.create(
            proposal=self,
            version_number=self.current_version,
            council=council,
            decision=decision,
            comments=comments,
            recorded_by=recorded_by,
        )

    def record_institute_decision(self, decision, comments="", recorded_by=None):
        if self.status != self.Status.INSTITUTE_REVIEW:
            raise ValidationError("پروپوزال در وضعیت بررسی پژوهشکده نیست.")
        self._record_decision(self.Council.INSTITUTE, decision, comments, recorded_by)
        if decision == self.Decision.APPROVED:
            self.status = self.Status.ACADEMY_REVIEW
            self.pending_revision_target = None
        elif decision == self.Decision.NEEDS_REVISION:
            self.status = self.Status.NEEDS_REVISION
            self.pending_revision_target = self.Council.INSTITUTE
        elif decision == self.Decision.REJECTED:
            self.status = self.Status.REJECTED
            self.pending_revision_target = None
        else:
            raise ValidationError("تصمیم نامعتبر است.")
        self.save(update_fields=["status", "pending_revision_target", "updated_at"])

    def record_academy_decision(self, decision, comments="", recorded_by=None):
        if self.status != self.Status.ACADEMY_REVIEW:
            raise ValidationError("پروپوزال در وضعیت بررسی پژوهشگاه نیست.")
        self._record_decision(self.Council.ACADEMY, decision, comments, recorded_by)
        if decision == self.Decision.APPROVED:
            self.status = self.Status.APPROVED
            self.pending_revision_target = None
            self.decided_at = timezone.now()
        elif decision == self.Decision.NEEDS_REVISION:
            self.status = self.Status.NEEDS_REVISION
            self.pending_revision_target = self.Council.ACADEMY
        elif decision == self.Decision.REJECTED:
            self.status = self.Status.REJECTED
            self.pending_revision_target = None
        else:
            raise ValidationError("تصمیم نامعتبر است.")
        self.save(update_fields=["status", "pending_revision_target", "decided_at", "updated_at"])

    def resubmit_after_revision(self, recorded_by=None):
        if self.status != self.Status.NEEDS_REVISION:
            raise ValidationError("فقط پروپوزال نیازمند اصلاح قابل ارسال مجدد است.")
        target = self.pending_revision_target
        self.current_version += 1
        self._snapshot_version(created_by=recorded_by)
        if target == self.Council.INSTITUTE:
            self.status = self.Status.INSTITUTE_REVIEW
        elif target == self.Council.ACADEMY:
            self.status = self.Status.ACADEMY_REVIEW
        else:
            raise ValidationError("شورای مرجع اصلاحیه نامشخص است.")
        self.pending_revision_target = None
        self.save(update_fields=["current_version", "status", "pending_revision_target", "updated_at"])

    def issue_executor_order(self, executor, executor_content_type=None, assigned_date=None):
        """صدور حکم مجری و ایجاد رسمی پروژه بر مبنای پروپوزال تأییدشده."""
        if self.status != self.Status.APPROVED:
            raise ValidationError("فقط پروپوزال تأییدشده‌ی نهایی قابل صدور حکم است.")
        if hasattr(self, "project") and self.project_id:
            raise ValidationError("برای این پروپوزال قبلاً پروژه ایجاد شده است.")

        assigned_date = assigned_date or timezone.localdate()
        ct = executor_content_type or ContentType.objects.get_for_model(executor)

        project = Project.objects.create(
            code=self.code,
            title=self.title,
            proposal=self,
            research_institute=self.research_institute,
            project_type=self.project_type,
            client_or_funder=self.client_or_funder,
            planned_start_date=self.planned_start_date,
            planned_end_date=self.planned_end_date,
            actual_start_date=assigned_date,
            status=Project.Status.IN_PROGRESS,
            budget=self.budget,
            executor_content_type=ct,
            executor_object_id=executor.pk,
            executor_assigned_date=assigned_date,
        )
        self.status = self.Status.IN_PROGRESS
        self.order_issued_at = timezone.now()
        self.save(update_fields=["status", "order_issued_at", "updated_at"])
        return project


class ProposalVersion(models.Model):
    """سابقه‌ی نسخه‌های مختلف یک پروپوزال."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    budget = models.DecimalField(max_digits=18, decimal_places=0, default=0)
    planned_start_date = models.DateField()
    planned_end_date = models.DateField()
    resource_requirement = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name = "نسخه‌ی پروپوزال"
        verbose_name_plural = "نسخه‌های پروپوزال"
        ordering = ["proposal", "version_number"]
        constraints = [
            models.UniqueConstraint(fields=["proposal", "version_number"], name="unique_proposal_version")
        ]

    def __str__(self):
        return f"{self.proposal.code} - نسخه {self.version_number}"


class ProposalDecision(models.Model):
    """تصمیم ثبت‌شده‌ی شورای علمی پژوهشکده یا شورای پژوهشی پژوهشگاه."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="decisions")
    version_number = models.PositiveSmallIntegerField()
    council = models.CharField(max_length=20, choices=Proposal.Council.choices)
    decision = models.CharField(max_length=20, choices=Proposal.Decision.choices)
    comments = models.TextField("نظرات / دلایل رد", blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تصمیم شورا"
        verbose_name_plural = "تصمیم‌های شورا"
        ordering = ["-decided_at"]

    def __str__(self):
        return f"{self.proposal.code} - {self.get_council_display()} - {self.get_decision_display()}"
