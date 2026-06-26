from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    ApplicationDraftForm,
    CandidateDirectoryFilterForm,
    CandidateDocumentForm,
    CandidateForm,
    DocumentTemplateForm,
    EmployerForm,
    JobForm,
    MatchStatusForm,
    ScoringWeightForm,
    UploadForm,
)
from .models import (
    ApplicationDraft,
    Candidate,
    CandidateDocument,
    CandidateProfile,
    CandidateSkill,
    DocumentTemplate,
    Employer,
    Job,
    MatchScore,
    ScoringWeight,
)
from .services.applications import create_application_draft, ensure_default_templates, send_application_draft
from .services.importers import import_candidates, import_jobs
from .services.scoring import ensure_default_weights, score_job_against_active_candidates


@login_required
def dashboard(request):
    ensure_default_weights()
    ensure_default_templates()
    context = {
        "candidate_count": Candidate.objects.exclude(status=Candidate.Status.ARCHIVED).count(),
        "open_job_count": Job.objects.filter(status=Job.Status.OPEN).count(),
        "draft_count": ApplicationDraft.objects.filter(status=ApplicationDraft.Status.DRAFT).count(),
        "sent_count": ApplicationDraft.objects.filter(status=ApplicationDraft.Status.SENT).count(),
        "top_matches": MatchScore.objects.select_related("candidate", "job", "job__employer")[:8],
        "recent_drafts": ApplicationDraft.objects.select_related("match_score__candidate", "match_score__job")[:6],
    }
    return render(request, "matching/dashboard.html", context)


@login_required
def candidate_list(request):
    candidates = Candidate.objects.annotate(match_count=Count("match_scores"))
    return render(request, "matching/candidate_list.html", {"candidates": candidates})


def distinct_values(queryset, field_name):
    return [
        value
        for value in queryset.exclude(**{field_name: ""}).values_list(field_name, flat=True).distinct().order_by(field_name)
        if value
    ][:100]


def directory_filter_choices():
    profiles = CandidateProfile.objects.all()
    return {
        "skill": distinct_values(CandidateSkill.objects.all(), "name"),
        "location": distinct_values(Candidate.objects.all(), "location"),
        "nationality": distinct_values(profiles, "nationality"),
        "education": distinct_values(profiles, "education_level"),
        "english": distinct_values(profiles, "english_speaking"),
        "computer": distinct_values(profiles, "computer_skill_level"),
        "migration_country": sorted(
            {
                part.strip()
                for value in profiles.exclude(migration_countries="").values_list("migration_countries", flat=True)
                for part in value.replace(";", ",").replace("|", ",").split(",")
                if part.strip()
            }
        )[:100],
    }


def truthy_filter(queryset, field_name, value):
    if value == "yes":
        return queryset.exclude(**{field_name: ""})
    if value == "no":
        return queryset.filter(Q(**{field_name: ""}) | Q(**{field_name + "__isnull": True}))
    return queryset


@login_required
def candidate_directory(request):
    choices = directory_filter_choices()
    form = CandidateDirectoryFilterForm(request.GET or None, choices=choices)
    candidates = (
        Candidate.objects.select_related("profile")
        .prefetch_related("skill_records", "experience_records", "documents")
        .annotate(match_count=Count("match_scores"))
    )

    if form.is_valid():
        data = form.cleaned_data
        if data.get("q"):
            query = data["q"]
            candidates = candidates.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(email__icontains=query)
                | Q(phone__icontains=query)
                | Q(location__icontains=query)
                | Q(skills__icontains=query)
                | Q(education__icontains=query)
                | Q(certifications__icontains=query)
                | Q(summary__icontains=query)
                | Q(relevant_experience__icontains=query)
                | Q(profile__raw_answers__icontains=query)
                | Q(skill_records__name__icontains=query)
                | Q(experience_records__details__icontains=query)
            )
        if data.get("status"):
            candidates = candidates.filter(status=data["status"])
        if data.get("skill"):
            candidates = candidates.filter(Q(skill_records__name=data["skill"]) | Q(skills__icontains=data["skill"]))
        if data.get("location"):
            candidates = candidates.filter(location=data["location"])
        if data.get("nationality"):
            candidates = candidates.filter(profile__nationality=data["nationality"])
        if data.get("education"):
            candidates = candidates.filter(profile__education_level=data["education"])
        if data.get("english"):
            candidates = candidates.filter(profile__english_speaking=data["english"])
        if data.get("computer"):
            candidates = candidates.filter(profile__computer_skill_level=data["computer"])
        if data.get("migration_country"):
            candidates = candidates.filter(profile__migration_countries__icontains=data["migration_country"])
        if data.get("passport"):
            candidates = truthy_filter(candidates, "profile__valid_passport", data["passport"])
        if data.get("documents") == "yes":
            candidates = candidates.filter(
                Q(profile__resume_upload__gt="")
                | Q(profile__education_upload__gt="")
                | Q(profile__certification_upload__gt="")
                | Q(profile__photo_document_upload__gt="")
                | Q(documents__isnull=False)
            )
        elif data.get("documents") == "no":
            candidates = candidates.filter(
                Q(profile__resume_upload="")
                & Q(profile__education_upload="")
                & Q(profile__certification_upload="")
                & Q(profile__photo_document_upload="")
                & Q(documents__isnull=True)
            )
        if data.get("consent") == "yes":
            candidates = candidates.exclude(profile__consent_share="").exclude(profile__consent_contact="")
        elif data.get("consent") == "no":
            candidates = candidates.filter(Q(profile__consent_share="") | Q(profile__consent_contact=""))

    candidates = candidates.distinct()
    view_mode = form.cleaned_data.get("view", "cards") if form.is_valid() else "cards"
    density = form.cleaned_data.get("density", "detailed") if form.is_valid() else "detailed"
    return render(
        request,
        "matching/candidate_directory.html",
        {
            "form": form,
            "candidates": candidates,
            "candidate_count": candidates.count(),
            "view_mode": view_mode,
            "density": density,
        },
    )


@login_required
def candidate_create(request):
    form = CandidateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        candidate = form.save()
        messages.success(request, "Candidate created.")
        return redirect(candidate)
    return render(request, "matching/form.html", {"form": form, "title": "New candidate"})


@login_required
def candidate_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = CandidateForm(request.POST or None, instance=candidate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Candidate updated.")
        return redirect(candidate)
    return render(request, "matching/form.html", {"form": form, "title": "Edit candidate"})


@login_required
def candidate_detail(request, pk):
    candidate = get_object_or_404(
        Candidate.objects.select_related("profile").prefetch_related("skill_records", "experience_records", "documents"),
        pk=pk,
    )
    documents = candidate.documents.all()
    skills = candidate.skill_records.all()
    experiences = candidate.experience_records.all()
    matches = candidate.match_scores.select_related("job", "job__employer")[:20]
    return render(
        request,
        "matching/candidate_detail.html",
        {
            "candidate": candidate,
            "documents": documents,
            "skills": skills,
            "experiences": experiences,
            "matches": matches,
            "raw_answers": getattr(candidate, "profile", None).raw_answers.items() if hasattr(candidate, "profile") else [],
        },
    )


@login_required
def candidate_document_add(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = CandidateDocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.candidate = candidate
        document.save()
        messages.success(request, "Document uploaded.")
        return redirect(candidate)
    return render(request, "matching/form.html", {"form": form, "title": f"Upload document for {candidate}"})


@login_required
def import_candidates_view(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        result = import_candidates(form.cleaned_data["file"])
        messages.success(request, f"Candidates imported: {result['created']} created, {result['updated']} updated.")
        for error in result["errors"]:
            messages.warning(request, error)
        return redirect("candidate_list")
    return render(request, "matching/import.html", {"form": form, "title": "Import candidates"})


@login_required
def employer_list(request):
    employers = Employer.objects.annotate(job_count=Count("jobs"))
    return render(request, "matching/employer_list.html", {"employers": employers})


@login_required
def employer_create(request):
    form = EmployerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Employer created.")
        return redirect("employer_list")
    return render(request, "matching/form.html", {"form": form, "title": "New employer"})


@login_required
def job_list(request):
    jobs = Job.objects.select_related("employer").annotate(match_count=Count("match_scores"))
    return render(request, "matching/job_list.html", {"jobs": jobs})


@login_required
def job_create(request):
    form = JobForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save()
        messages.success(request, "Job created.")
        return redirect(job)
    return render(request, "matching/form.html", {"form": form, "title": "New job"})


@login_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk)
    form = JobForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Job updated.")
        return redirect(job)
    return render(request, "matching/form.html", {"form": form, "title": "Edit job"})


@login_required
def job_detail(request, pk):
    job = get_object_or_404(Job.objects.select_related("employer"), pk=pk)
    matches = job.match_scores.select_related("candidate")[:50]
    return render(request, "matching/job_detail.html", {"job": job, "matches": matches})


@login_required
def import_jobs_view(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        result = import_jobs(form.cleaned_data["file"])
        messages.success(request, f"Jobs imported: {result['created']} created, {result['updated']} updated.")
        for error in result["errors"]:
            messages.warning(request, error)
        return redirect("job_list")
    return render(request, "matching/import.html", {"form": form, "title": "Import jobs"})


@login_required
@require_POST
def score_job_view(request, pk):
    job = get_object_or_404(Job, pk=pk)
    scores = score_job_against_active_candidates(job)
    messages.success(request, f"Scored {len(scores)} active candidates for {job.title}.")
    return redirect(job)


@login_required
def match_list(request):
    matches = MatchScore.objects.select_related("candidate", "job", "job__employer")
    job_id = request.GET.get("job")
    if job_id:
        matches = matches.filter(job_id=job_id)
    return render(request, "matching/match_list.html", {"matches": matches})


@login_required
def match_detail(request, pk):
    match = get_object_or_404(MatchScore.objects.select_related("candidate", "job", "job__employer"), pk=pk)
    form = MatchStatusForm(request.POST or None, instance=match)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Match status updated.")
        return redirect("match_detail", pk=match.pk)
    return render(request, "matching/match_detail.html", {"match": match, "form": form})


@login_required
@require_POST
def create_draft_view(request, pk):
    match = get_object_or_404(MatchScore, pk=pk)
    try:
        draft = create_application_draft(match)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("match_detail", pk=match.pk)
    messages.success(request, "Application draft generated.")
    return redirect("application_detail", pk=draft.pk)


@login_required
def application_list(request):
    drafts = ApplicationDraft.objects.select_related("match_score__candidate", "match_score__job", "match_score__job__employer")
    return render(request, "matching/application_list.html", {"drafts": drafts})


@login_required
def application_detail(request, pk):
    draft = get_object_or_404(
        ApplicationDraft.objects.select_related("match_score__candidate", "match_score__job", "match_score__job__employer"),
        pk=pk,
    )
    form = ApplicationDraftForm(request.POST or None, instance=draft)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Draft saved.")
        return redirect("application_detail", pk=draft.pk)
    return render(request, "matching/application_detail.html", {"draft": draft, "form": form})


@login_required
@require_POST
def send_application_view(request, pk):
    draft = get_object_or_404(ApplicationDraft, pk=pk)
    try:
        send_application_draft(draft)
    except Exception as exc:
        messages.error(request, f"Send failed: {exc}")
    else:
        messages.success(request, "Application sent.")
    return redirect("application_detail", pk=draft.pk)


@login_required
def template_list(request):
    ensure_default_templates()
    templates = DocumentTemplate.objects.all()
    return render(request, "matching/template_list.html", {"templates": templates})


@login_required
def template_create(request):
    form = DocumentTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        template = form.save()
        if template.is_default:
            DocumentTemplate.objects.filter(template_type=template.template_type).exclude(pk=template.pk).update(is_default=False)
        messages.success(request, "Template created.")
        return redirect("template_list")
    return render(request, "matching/form.html", {"form": form, "title": "New template"})


@login_required
def template_edit(request, pk):
    template = get_object_or_404(DocumentTemplate, pk=pk)
    form = DocumentTemplateForm(request.POST or None, instance=template)
    if request.method == "POST" and form.is_valid():
        template = form.save()
        if template.is_default:
            DocumentTemplate.objects.filter(template_type=template.template_type).exclude(pk=template.pk).update(is_default=False)
        messages.success(request, "Template updated.")
        return redirect("template_list")
    return render(request, "matching/form.html", {"form": form, "title": "Edit template"})


@login_required
def weight_list(request):
    ensure_default_weights()
    weights = ScoringWeight.objects.all()
    return render(request, "matching/weight_list.html", {"weights": weights})


@login_required
def weight_edit(request, pk):
    weight = get_object_or_404(ScoringWeight, pk=pk)
    form = ScoringWeightForm(request.POST or None, instance=weight)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Scoring weight updated.")
        return redirect("weight_list")
    return render(request, "matching/form.html", {"form": form, "title": "Edit scoring weight"})
