import datetime

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse

from .admin_forms import GenericChoiceFormMixin, _build_choices, _decode
from .models import (
    Assignment,
    ExternalCollaborator,
    InternalCollaborator,
    Project,
    Proposal,
    ProposalDecision,
    ProposalVersion,
    ResearchInstitute,
    Soldier,
)

admin.site.site_header = "سامانه مدیریت پروژه‌های امنیت پژوهشگاه"
admin.site.site_title = "مدیریت پروژه‌های امنیت"
admin.site.index_title = "ورود داده و مدیریت موجودیت‌ها"

EXECUTOR_MODELS_AND_LABELS = (
    (InternalCollaborator, "همکار داخلی"),
    (ExternalCollaborator, "همکار خارجی"),
)
PERSON_MODELS_AND_LABELS = (
    (Soldier, "سرباز"),
    (InternalCollaborator, "همکار داخلی"),
    (ExternalCollaborator, "همکار خارجی"),
)


class ExecutorChoiceFormMixin(GenericChoiceFormMixin):
    generic_field_name = "executor_choice"
    generic_ct_field = "executor_content_type"
    generic_id_field = "executor_object_id"
    generic_models_and_labels = EXECUTOR_MODELS_AND_LABELS


class PersonChoiceFormMixin(GenericChoiceFormMixin):
    generic_field_name = "person_choice"
    generic_ct_field = "person_content_type"
    generic_id_field = "person_object_id"
    generic_models_and_labels = PERSON_MODELS_AND_LABELS


class ProjectAdminForm(ExecutorChoiceFormMixin, forms.ModelForm):
    executor_choice = forms.ChoiceField(label="مجری", required=False, choices=[])

    class Meta:
        model = Project
        exclude = ("executor_content_type", "executor_object_id")


class ProposalAdminForm(ExecutorChoiceFormMixin, forms.ModelForm):
    executor_choice = forms.ChoiceField(label="مجری پیشنهادی", required=False, choices=[])

    class Meta:
        model = Proposal
        exclude = ("executor_content_type", "executor_object_id")


class AssignmentAdminForm(PersonChoiceFormMixin, forms.ModelForm):
    person_choice = forms.ChoiceField(
        label="نیرو (سرباز / همکار داخلی / همکار خارجی)", required=True, choices=[]
    )

    class Meta:
        model = Assignment
        exclude = ("person_content_type", "person_object_id")


class AssignmentInline(admin.TabularInline):
    model = Assignment
    form = AssignmentAdminForm
    extra = 1
    fields = ("person_choice", "allocation_percent", "role_description", "start_date", "end_date")


@admin.register(ResearchInstitute)
class ResearchInstituteAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    form = ProjectAdminForm
    list_display = (
        "code",
        "title",
        "research_institute",
        "project_type",
        "status",
        "progress_percent",
        "planned_start_date",
        "planned_end_date",
        "executor_display",
    )
    list_filter = ("status", "project_type", "research_institute")

    @admin.display(description="مجری")
    def executor_display(self, obj):
        return obj.executor
    search_fields = ("code", "title", "client_or_funder")
    inlines = [AssignmentInline]
    fieldsets = (
        ("اطلاعات کلی", {"fields": ("code", "title", "research_institute", "project_type", "client_or_funder")}),
        ("زمان‌بندی", {"fields": (
            ("planned_start_date", "planned_end_date"),
            ("actual_start_date", "actual_end_date"),
        )}),
        ("وضعیت و پیشرفت", {"fields": ("status", "progress_percent", "proposal")}),
        ("بودجه", {"fields": ("budget", "cost_spent")}),
        ("مجری", {"fields": ("executor_choice", "executor_assigned_date")}),
        ("اطلاعات سیستمی", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(Soldier)
class SoldierAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialty", "service_plan", "service_start_date", "service_end_date", "supervisor")
    list_filter = ("service_plan",)
    search_fields = ("full_name", "specialty")
    autocomplete_fields = ("supervisor",)


@admin.register(InternalCollaborator)
class InternalCollaboratorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "employment_type", "organizational_unit", "specialty", "role_title")
    list_filter = ("employment_type", "organizational_unit")
    search_fields = ("full_name", "specialty")


@admin.register(ExternalCollaborator)
class ExternalCollaboratorAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "collaboration_type",
        "contract_number",
        "contract_amount",
        "contract_end_date",
        "deliverables_status",
    )
    list_filter = ("collaboration_type",)
    search_fields = ("full_name", "contract_number")


class ProposalVersionInline(admin.TabularInline):
    model = ProposalVersion
    extra = 0
    readonly_fields = ("version_number", "title", "budget", "planned_start_date", "planned_end_date", "created_at", "created_by")
    can_delete = False


class ProposalDecisionInline(admin.TabularInline):
    model = ProposalDecision
    extra = 0
    readonly_fields = ("version_number", "council", "decision", "comments", "recorded_by", "decided_at")
    can_delete = False


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    form = ProposalAdminForm
    change_form_template = "admin/projects/proposal/change_form.html"
    list_display = (
        "code",
        "title",
        "research_institute",
        "status",
        "current_version",
        "submitted_at",
        "decided_at",
        "order_issued_at",
    )
    list_filter = ("status", "research_institute", "project_type")
    search_fields = ("code", "title")
    inlines = [ProposalVersionInline, ProposalDecisionInline]
    fieldsets = (
        ("اطلاعات کلی", {"fields": ("code", "title", "research_institute", "project_type", "client_or_funder")}),
        ("محتوای پروپوزال", {"fields": (
            ("planned_start_date", "planned_end_date"),
            "budget", "description", "resource_requirement",
        )}),
        ("مجری پیشنهادی", {"fields": ("executor_choice",)}),
        ("وضعیت فرآیند تصویب (فقط از طریق دکمه‌های بالای صفحه تغییر می‌کند)", {
            "fields": ("status", "pending_revision_target", "current_version"),
        }),
        ("اطلاعات سیستمی", {
            "fields": ("submitted_at", "decided_at", "order_issued_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = (
        "submitted_at", "updated_at", "decided_at", "order_issued_at",
        "status", "pending_revision_target", "current_version",
    )

    # --- دکمه‌های فرآیند تصویب --------------------------------------

    def get_urls(self):
        custom = [
            path("<int:pk>/start-review/", self.admin_site.admin_view(self.start_review_view), name="proposal_start_review"),
            path("<int:pk>/institute-decision/", self.admin_site.admin_view(self.institute_decision_view), name="proposal_institute_decision"),
            path("<int:pk>/academy-decision/", self.admin_site.admin_view(self.academy_decision_view), name="proposal_academy_decision"),
            path("<int:pk>/resubmit/", self.admin_site.admin_view(self.resubmit_view), name="proposal_resubmit"),
            path("<int:pk>/issue-order/", self.admin_site.admin_view(self.issue_order_view), name="proposal_issue_order"),
        ]
        return custom + super().get_urls()

    def _redirect_to_change(self, pk):
        return redirect(reverse("admin:projects_proposal_change", args=[pk]))

    @staticmethod
    def _error_text(exc):
        return "؛ ".join(exc.messages) if hasattr(exc, "messages") else str(exc)

    def start_review_view(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if request.method == "POST":
            try:
                proposal.start_institute_review()
                messages.success(request, "پروپوزال وارد بررسی در پژوهشکده شد.")
            except ValidationError as exc:
                messages.error(request, self._error_text(exc))
        return self._redirect_to_change(pk)

    def resubmit_view(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if request.method == "POST":
            try:
                proposal.resubmit_after_revision(recorded_by=request.user)
                messages.success(request, "اصلاحیه ثبت و پروپوزال مجدداً ارسال شد.")
            except ValidationError as exc:
                messages.error(request, self._error_text(exc))
        return self._redirect_to_change(pk)

    def institute_decision_view(self, request, pk):
        return self._decision_view(request, pk, council="institute")

    def academy_decision_view(self, request, pk):
        return self._decision_view(request, pk, council="academy")

    def _decision_view(self, request, pk, council):
        proposal = get_object_or_404(Proposal, pk=pk)
        council_label = "شورای علمی پژوهشکده" if council == "institute" else "شورای پژوهشی پژوهشگاه"
        if request.method == "POST":
            decision = request.POST.get("decision")
            comments = request.POST.get("comments", "")
            try:
                if council == "institute":
                    proposal.record_institute_decision(decision, comments, recorded_by=request.user)
                else:
                    proposal.record_academy_decision(decision, comments, recorded_by=request.user)
                messages.success(request, "تصمیم شورا ثبت شد.")
                return self._redirect_to_change(pk)
            except ValidationError as exc:
                messages.error(request, self._error_text(exc))
        context = {
            **self.admin_site.each_context(request),
            "proposal": proposal,
            "council_label": council_label,
            "decision_choices": Proposal.Decision.choices,
            "title": f"ثبت تصمیم {council_label}",
            "opts": self.model._meta,
        }
        return render(request, "admin/projects/proposal/decision_form.html", context)

    def issue_order_view(self, request, pk):
        proposal = get_object_or_404(Proposal, pk=pk)
        if request.method == "POST":
            value = request.POST.get("executor_choice")
            assigned_date_raw = request.POST.get("executor_assigned_date")
            assigned_date = datetime.date.fromisoformat(assigned_date_raw) if assigned_date_raw else None
            if not value:
                messages.error(request, "انتخاب مجری الزامی است.")
            else:
                content_type, object_id = _decode(value)
                executor = content_type.get_object_for_this_type(pk=object_id)
                try:
                    proposal.issue_executor_order(executor, executor_content_type=content_type, assigned_date=assigned_date)
                    messages.success(request, "حکم مجری صادر شد و پروژه‌ی مرتبط ایجاد شد.")
                    return self._redirect_to_change(pk)
                except ValidationError as exc:
                    messages.error(request, self._error_text(exc))
        context = {
            **self.admin_site.each_context(request),
            "proposal": proposal,
            "executor_choices": _build_choices(EXECUTOR_MODELS_AND_LABELS),
            "title": "صدور حکم مجری",
            "opts": self.model._meta,
        }
        return render(request, "admin/projects/proposal/issue_order_form.html", context)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm
    list_display = ("project", "person", "allocation_percent", "role_description", "start_date", "end_date")
    list_filter = ("project",)
    fields = ("project", "person_choice", "allocation_percent", "role_description", "start_date", "end_date")
