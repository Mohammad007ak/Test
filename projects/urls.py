from django.urls import path

from . import views

urlpatterns = [
    path("", views.report_home, name="report_home"),
    path("reports/project-status/", views.project_status_overview, name="project_status_overview"),
    path("reports/project-progress/", views.project_progress, name="project_progress"),
    path("reports/delayed-projects/", views.delayed_projects, name="delayed_projects"),
    path("reports/project/<int:pk>/", views.project_profile, name="project_profile"),
    path("reports/proposals-in-progress/", views.proposals_in_progress, name="proposals_in_progress"),
    path("reports/approval-rate/", views.approval_rate, name="approval_rate"),
    path("reports/average-approval-time/", views.average_approval_time, name="average_approval_time"),
    path("reports/workforce-composition/", views.workforce_composition, name="workforce_composition"),
    path("reports/workload/", views.workload_report, name="workload_report"),
    path("reports/free-capacity/", views.free_capacity, name="free_capacity"),
    path("reports/soldier-service-end/", views.soldier_service_end, name="soldier_service_end"),
    path("reports/external-contracts/", views.external_contracts, name="external_contracts"),
    path("reports/executor-performance/", views.executor_performance, name="executor_performance"),
    path("reports/executor-dashboard/", views.executor_dashboard, name="executor_dashboard"),
]
