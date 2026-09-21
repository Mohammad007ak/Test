from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import (
    Assignment,
    ExternalCollaborator,
    InternalCollaborator,
    Project,
    Proposal,
    ProposalDecision,
    Soldier,
)
from .nav import visible_nav_groups
from .permissions import (
    ROLE_DATA_ENTRY,
    ROLE_EXECUTOR,
    ROLE_PROJECT_CONTROL,
    ROLE_SUPER_ADMIN,
    role_required,
    user_roles,
)

PERSON_MODELS = (
    (Soldier, "سرباز"),
    (InternalCollaborator, "همکار داخلی"),
    (ExternalCollaborator, "همکار خارجی"),
)


def _executor_persons_for_user(user):
    """موجودیت(های) همکار داخلی/خارجی مرتبط با کاربر جاری (برای داشبورد مجری)."""
    persons = []
    for model in (InternalCollaborator, ExternalCollaborator):
        persons += list(model.objects.filter(full_name=user.get_full_name()))
    return persons


def _average_approval_days():
    finished = Proposal.objects.filter(order_issued_at__isnull=False)
    duration_expr = ExpressionWrapper(F("order_issued_at") - F("submitted_at"), output_field=DurationField())
    avg_duration = finished.annotate(duration=duration_expr).aggregate(avg=Avg("duration"))["avg"]
    return avg_duration.days if avg_duration else None


def _global_kpis(include_admin_only):
    projects = Project.objects.all()
    in_progress_qs = projects.filter(status=Project.Status.IN_PROGRESS)
    delayed = sum(1 for p in in_progress_qs if p.delay_percent > 0)

    active_proposal_statuses = [
        Proposal.Status.SUBMITTED,
        Proposal.Status.INSTITUTE_REVIEW,
        Proposal.Status.ACADEMY_REVIEW,
        Proposal.Status.NEEDS_REVISION,
    ]
    proposals_in_progress = Proposal.objects.filter(status__in=active_proposal_statuses).count()

    avg_days = _average_approval_days()

    workforce_total = sum(model.objects.count() for model, _ in PERSON_MODELS)
    overloaded = sum(
        1
        for model, _ in PERSON_MODELS
        for person in model.objects.all()
        if person.active_allocation_percent() > 100
    )

    cutoff = timezone.localdate() + timedelta(days=90)
    soldiers_ending = Soldier.objects.filter(
        service_end_date__lte=cutoff, service_end_date__gte=timezone.localdate()
    ).count()

    kpis = [
        {"label": "کل پروژه‌ها", "value": projects.count(), "url": "project_status_overview"},
        {"label": "در حال اجرا", "value": in_progress_qs.count(), "tone": "accent", "url": "project_status_overview"},
        {"label": "پروژه‌های دارای تأخیر", "value": delayed, "tone": "bad" if delayed else "good", "url": "delayed_projects"},
        {"label": "پروپوزال در جریان", "value": proposals_in_progress, "url": "proposals_in_progress"},
        {"label": "میانگین زمان تصویب", "value": f"{avg_days} روز" if avg_days is not None else "—", "url": "average_approval_time"},
        {"label": "نیروی انسانی فعال", "value": workforce_total, "url": "workforce_composition"},
        {"label": "بیش‌ازحد درگیر", "value": overloaded, "tone": "warn" if overloaded else "good", "url": "workload_report"},
        {"label": "پایان خدمت نزدیک", "value": soldiers_ending, "url": "soldier_service_end"},
    ]
    if include_admin_only:
        contracts_ending = ExternalCollaborator.objects.filter(
            contract_end_date__lte=cutoff, contract_end_date__gte=timezone.localdate()
        ).count()
        kpis.append({
            "label": "قرارداد نزدیک به پایان",
            "value": contracts_ending,
            "tone": "warn" if contracts_ending else "good",
            "url": "external_contracts",
        })
    return kpis


def _executor_kpis(user):
    from django.contrib.contenttypes.models import ContentType

    persons = _executor_persons_for_user(user)
    pks = [p.pk for p in persons]
    types = [type(p)._meta.model_name for p in persons]
    cts = ContentType.objects.filter(model__in=set(types)) if types else ContentType.objects.none()
    projects = Project.objects.filter(executor_content_type__in=cts, executor_object_id__in=pks)
    delayed = sum(1 for p in projects if p.is_delayed)
    return [
        {"label": "پروژه‌های شما", "value": projects.count(), "url": "executor_dashboard"},
        {"label": "در حال اجرا", "value": projects.filter(status=Project.Status.IN_PROGRESS).count(), "tone": "accent", "url": "executor_dashboard"},
        {"label": "دارای تأخیر", "value": delayed, "tone": "bad" if delayed else "good", "url": "executor_dashboard"},
    ]


_PIPELINE_STAGES = [
    (Proposal.Status.SUBMITTED, "ارسال‌شده"),
    (Proposal.Status.INSTITUTE_REVIEW, "در حال بررسی در پژوهشکده"),
    (Proposal.Status.NEEDS_REVISION, "نیازمند اصلاح"),
    (Proposal.Status.ACADEMY_REVIEW, "در حال بررسی در پژوهشگاه"),
    (Proposal.Status.APPROVED, "تأییدشده (در انتظار صدور حکم)"),
]

_PIPELINE_ACTION_LABELS = {
    Proposal.Status.SUBMITTED: "شروع بررسی در پژوهشکده",
    Proposal.Status.INSTITUTE_REVIEW: "ثبت تصمیم شورای پژوهشکده",
    Proposal.Status.NEEDS_REVISION: "اصلاح و ارسال مجدد",
    Proposal.Status.ACADEMY_REVIEW: "ثبت تصمیم شورای پژوهشگاه",
    Proposal.Status.APPROVED: "صدور حکم مجری",
}


def _proposal_pipeline():
    counts = [
        {"label": label, "count": Proposal.objects.filter(status=status).count()}
        for status, label in _PIPELINE_STAGES
    ]
    max_count = max((c["count"] for c in counts), default=0)
    for c in counts:
        c["percent"] = round(c["count"] / max_count * 100) if max_count else 0

    actionable_statuses = [status for status, _ in _PIPELINE_STAGES]
    pending = (
        Proposal.objects.filter(status__in=actionable_statuses)
        .select_related("research_institute")
        .order_by("updated_at")[:8]
    )
    rows = [
        {"proposal": p, "action_label": _PIPELINE_ACTION_LABELS.get(p.status, "بررسی")}
        for p in pending
    ]
    return {"stage_counts": counts, "pending_rows": rows}


@login_required
def report_home(request):
    roles = user_roles(request.user)
    is_admin_like = request.user.is_superuser or bool(roles & {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL})
    if is_admin_like:
        kpis = _global_kpis(include_admin_only=request.user.is_superuser or ROLE_SUPER_ADMIN in roles)
        proposal_pipeline = _proposal_pipeline()
    elif ROLE_EXECUTOR in roles:
        kpis = _executor_kpis(request.user)
        proposal_pipeline = None
    else:
        kpis = []
        proposal_pipeline = None
    return render(
        request,
        "projects/report_home.html",
        {
            "nav_groups": visible_nav_groups(request.user),
            "kpis": kpis,
            "proposal_pipeline": proposal_pipeline,
        },
    )


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def project_status_overview(request):
    counts = (
        Project.objects.values("status").annotate(total=Count("id")).order_by("status")
    )
    status_labels = dict(Project.Status.choices)
    data = [{"status": status_labels.get(row["status"], row["status"]), "total": row["total"]} for row in counts]
    return render(request, "projects/project_status_overview.html", {"data": data, "total": Project.objects.count()})


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL, ROLE_EXECUTOR)
def project_progress(request):
    qs = Project.objects.select_related("research_institute").all()
    if ROLE_EXECUTOR in user_roles(request.user) and not request.user.is_superuser and not (
        user_roles(request.user) & {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL}
    ):
        persons = _executor_persons_for_user(request.user)
        pks = [p.pk for p in persons]
        types = [type(p)._meta.model_name for p in persons]
        from django.contrib.contenttypes.models import ContentType

        cts = ContentType.objects.filter(model__in=set(types)) if types else ContentType.objects.none()
        qs = qs.filter(executor_content_type__in=cts, executor_object_id__in=pks)
    rows = [
        {
            "project": project,
            "expected": project.expected_progress_percent,
            "actual": project.progress_percent,
            "delay": project.delay_percent,
        }
        for project in qs
    ]
    return render(request, "projects/project_progress.html", {"rows": rows})


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def delayed_projects(request):
    rows = [
        {"project": project, "delay": project.delay_percent}
        for project in Project.objects.filter(status=Project.Status.IN_PROGRESS)
        if project.delay_percent > 0
    ]
    rows.sort(key=lambda r: r["delay"], reverse=True)
    return render(request, "projects/delayed_projects.html", {"rows": rows})


@login_required
def project_profile(request, pk):
    project = get_object_or_404(Project.objects.select_related("research_institute", "proposal"), pk=pk)
    roles = user_roles(request.user)
    if not (request.user.is_superuser or roles & {ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL, ROLE_DATA_ENTRY}):
        if ROLE_EXECUTOR in roles:
            persons = _executor_persons_for_user(request.user)
            if project.executor not in persons:
                raise PermissionDenied("شما فقط به شناسنامه‌ی پروژه‌های خود دسترسی دارید.")
        else:
            raise PermissionDenied
    assignments = project.assignments.select_related("person_content_type").all()
    decisions = project.proposal.decisions.all() if project.proposal_id else []
    return render(
        request,
        "projects/project_profile.html",
        {"project": project, "assignments": assignments, "decisions": decisions},
    )


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def proposals_in_progress(request):
    active_statuses = [
        Proposal.Status.SUBMITTED,
        Proposal.Status.INSTITUTE_REVIEW,
        Proposal.Status.ACADEMY_REVIEW,
        Proposal.Status.NEEDS_REVISION,
    ]
    now = timezone.now()
    rows = []
    for proposal in Proposal.objects.filter(status__in=active_statuses):
        last_change = proposal.updated_at
        rows.append(
            {
                "proposal": proposal,
                "status": proposal.get_status_display(),
                "days_in_stage": (now - last_change).days,
            }
        )
    rows.sort(key=lambda r: r["days_in_stage"], reverse=True)
    return render(request, "projects/proposals_in_progress.html", {"rows": rows})


@role_required(ROLE_SUPER_ADMIN)
def approval_rate(request):
    data = {}
    for council_value, council_label in Proposal.Council.choices:
        decisions = ProposalDecision.objects.filter(council=council_value)
        total = decisions.count()
        breakdown = decisions.values("decision").annotate(total=Count("id"))
        decision_labels = dict(Proposal.Decision.choices)
        data[council_label] = {
            "total": total,
            "breakdown": [
                {
                    "decision": decision_labels.get(row["decision"], row["decision"]),
                    "total": row["total"],
                    "percent": round(row["total"] / total * 100) if total else 0,
                }
                for row in breakdown
            ],
        }
    return render(request, "projects/approval_rate.html", {"data": data})


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def average_approval_time(request):
    avg_days = _average_approval_days()
    sample_size = Proposal.objects.filter(order_issued_at__isnull=False).count()
    return render(
        request,
        "projects/average_approval_time.html",
        {"avg_days": avg_days, "sample_size": sample_size},
    )


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def workforce_composition(request):
    overall = {label: model.objects.count() for model, label in PERSON_MODELS}

    per_project = []
    for project in Project.objects.all():
        counts = {model._meta.model_name: 0 for model, _ in PERSON_MODELS}
        for assignment in project.assignments.select_related("person_content_type"):
            if assignment.person_content_type.model in counts:
                counts[assignment.person_content_type.model] += 1
        per_project.append({"project": project, "counts": counts})

    return render(
        request,
        "projects/workforce_composition.html",
        {"overall": overall, "per_project": per_project},
    )


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL)
def workload_report(request):
    rows = []
    for model, label in PERSON_MODELS:
        for person in model.objects.all():
            total_allocation = person.active_allocation_percent()
            rows.append(
                {
                    "person": person,
                    "type": label,
                    "project_count": person.active_project_count(),
                    "total_allocation": total_allocation,
                    "overloaded": total_allocation > 100,
                }
            )
    rows.sort(key=lambda r: r["total_allocation"], reverse=True)
    return render(request, "projects/workload_report.html", {"rows": rows})


@role_required(ROLE_SUPER_ADMIN, ROLE_EXECUTOR)
def free_capacity(request):
    rows = []
    for model, label in PERSON_MODELS:
        for person in model.objects.all():
            total_allocation = person.active_allocation_percent()
            if total_allocation < 100:
                rows.append(
                    {
                        "person": person,
                        "type": label,
                        "specialty": person.specialty,
                        "free_percent": 100 - total_allocation,
                    }
                )
    rows.sort(key=lambda r: (r["specialty"], -r["free_percent"]))
    return render(request, "projects/free_capacity.html", {"rows": rows})


@role_required(ROLE_SUPER_ADMIN, ROLE_PROJECT_CONTROL, ROLE_EXECUTOR)
def soldier_service_end(request):
    horizon_days = int(request.GET.get("days", 90))
    cutoff = timezone.localdate() + timedelta(days=horizon_days)
    soldiers = Soldier.objects.filter(service_end_date__lte=cutoff, service_end_date__gte=timezone.localdate())
    rows = []
    for soldier in soldiers:
        projects = [a.project for a in soldier.assignments.filter(project__status=Project.Status.IN_PROGRESS)]
        rows.append({"soldier": soldier, "projects": projects})
    return render(request, "projects/soldier_service_end.html", {"rows": rows, "horizon_days": horizon_days})


@role_required(ROLE_SUPER_ADMIN)
def external_contracts(request):
    horizon_days = int(request.GET.get("days", 90))
    cutoff = timezone.localdate() + timedelta(days=horizon_days)
    collaborators = ExternalCollaborator.objects.all()
    rows = []
    for collaborator in collaborators:
        ending_soon = bool(
            collaborator.contract_end_date
            and timezone.localdate() <= collaborator.contract_end_date <= cutoff
        )
        rows.append({"collaborator": collaborator, "ending_soon": ending_soon})
    return render(request, "projects/external_contracts.html", {"rows": rows, "horizon_days": horizon_days})


@role_required(ROLE_SUPER_ADMIN)
def executor_performance(request):
    rows = []
    for model, _ in ((InternalCollaborator, None), (ExternalCollaborator, None)):
        for person in model.objects.all():
            from django.contrib.contenttypes.models import ContentType

            ct = ContentType.objects.get_for_model(model)
            projects = Project.objects.filter(executor_content_type=ct, executor_object_id=person.pk)
            if not projects.exists():
                continue
            rows.append(
                {
                    "executor": person,
                    "project_count": projects.count(),
                    "in_progress": projects.filter(status=Project.Status.IN_PROGRESS).count(),
                    "finished": projects.filter(status=Project.Status.FINISHED).count(),
                    "delayed": sum(1 for p in projects if p.is_delayed),
                }
            )
    return render(request, "projects/executor_performance.html", {"rows": rows})


@role_required(ROLE_EXECUTOR, ROLE_SUPER_ADMIN)
def executor_dashboard(request):
    persons = _executor_persons_for_user(request.user)
    from django.contrib.contenttypes.models import ContentType

    pks = [p.pk for p in persons]
    types = [type(p)._meta.model_name for p in persons]
    cts = ContentType.objects.filter(model__in=set(types)) if types else ContentType.objects.none()
    projects = Project.objects.filter(executor_content_type__in=cts, executor_object_id__in=pks)

    upcoming_deadline = timezone.localdate() + timedelta(days=30)
    rows = []
    for project in projects:
        rows.append(
            {
                "project": project,
                "people_count": project.assignments.count(),
                "deadline_soon": project.status == Project.Status.IN_PROGRESS
                and project.planned_end_date <= upcoming_deadline,
            }
        )
    return render(request, "projects/executor_dashboard.html", {"rows": rows})
