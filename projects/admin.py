from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

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


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 1


@admin.register(ResearchInstitute)
class ResearchInstituteAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
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
    readonly_fields = ("created_at", "updated_at")


@admin.register(Soldier)
class SoldierAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialty", "service_plan", "service_start_date", "service_end_date", "supervisor")
    list_filter = ("service_plan",)
    search_fields = ("full_name", "specialty")


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
    readonly_fields = ("submitted_at", "updated_at", "decided_at", "order_issued_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("project", "person", "allocation_percent", "role_description", "start_date", "end_date")
    list_filter = ("project",)
