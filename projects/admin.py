from django import forms
from django.contrib import admin

from .admin_forms import GenericChoiceFormMixin
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
        "executor",
    )
    list_filter = ("status", "project_type", "research_institute")
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
        ("وضعیت فرآیند تصویب", {"fields": ("status", "pending_revision_target", "current_version")}),
        ("اطلاعات سیستمی", {
            "fields": ("submitted_at", "decided_at", "order_issued_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    readonly_fields = ("submitted_at", "updated_at", "decided_at", "order_issued_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm
    list_display = ("project", "person", "allocation_percent", "role_description", "start_date", "end_date")
    list_filter = ("project",)
    fields = ("project", "person_choice", "allocation_percent", "role_description", "start_date", "end_date")
