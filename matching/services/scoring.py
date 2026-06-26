import re
from decimal import Decimal

from django.utils import timezone

from matching.models import Candidate, Job, MatchScore, ScoringWeight


DEFAULT_WEIGHTS = {
    "required_skills": ("Required skills", 35),
    "preferred_skills": ("Preferred skills", 15),
    "experience": ("Experience", 15),
    "location": ("Location / remote fit", 10),
    "authorization": ("Work authorization", 10),
    "salary": ("Salary fit", 5),
    "education": ("Education", 5),
    "certifications": ("Certifications", 5),
}


def normalise_terms(value):
    if not value:
        return set()
    parts = re.split(r"[,;\n|/]+", str(value).lower())
    return {part.strip() for part in parts if part.strip()}


def ensure_default_weights():
    for key, (label, weight) in DEFAULT_WEIGHTS.items():
        ScoringWeight.objects.get_or_create(
            key=key,
            defaults={"label": label, "weight": weight, "enabled": True},
        )


def active_weights():
    ensure_default_weights()
    return {
        item.key: item.weight
        for item in ScoringWeight.objects.filter(enabled=True)
    }


def ratio_score(matched_count, total_count):
    if total_count == 0:
        return 100
    return round((matched_count / total_count) * 100)


def text_contains_any(text, requirements):
    haystack = (text or "").lower()
    return {term for term in requirements if term.lower() in haystack}


def score_candidate_for_job(candidate: Candidate, job: Job):
    weights = active_weights()
    candidate_skills = normalise_terms(candidate.skills)
    required_skills = normalise_terms(job.required_skills)
    preferred_skills = normalise_terms(job.preferred_skills)
    candidate_education = f"{candidate.education} {candidate.summary}"
    candidate_certs = f"{candidate.certifications} {candidate.summary}"

    breakdown = {}
    reasons = []
    failures = []

    required_matches = candidate_skills & required_skills
    required_score = ratio_score(len(required_matches), len(required_skills))
    breakdown["required_skills"] = {
        "score": required_score,
        "matched": sorted(required_matches),
        "missing": sorted(required_skills - required_matches),
    }
    if required_skills:
        reasons.append(f"Matched {len(required_matches)} of {len(required_skills)} required skills.")
    if required_skills - required_matches:
        failures.append("Missing required skills: " + ", ".join(sorted(required_skills - required_matches)))

    preferred_matches = candidate_skills & preferred_skills
    preferred_score = ratio_score(len(preferred_matches), len(preferred_skills))
    breakdown["preferred_skills"] = {
        "score": preferred_score,
        "matched": sorted(preferred_matches),
        "missing": sorted(preferred_skills - preferred_matches),
    }
    if preferred_skills:
        reasons.append(f"Matched {len(preferred_matches)} of {len(preferred_skills)} preferred skills.")

    if job.min_years_experience:
        experience_score = min(100, round(float(candidate.years_experience / job.min_years_experience) * 100))
    else:
        experience_score = 100
    breakdown["experience"] = {
        "score": experience_score,
        "candidate_years": float(candidate.years_experience),
        "required_years": float(job.min_years_experience),
    }
    if candidate.years_experience < job.min_years_experience:
        failures.append(f"Experience below requirement: {candidate.years_experience} vs {job.min_years_experience} years.")
    else:
        reasons.append("Experience meets or exceeds the requirement.")

    candidate_location = (candidate.location or "").lower().strip()
    job_location = (job.location or "").lower().strip()
    location_score = 100
    if job_location and candidate_location and candidate_location not in job_location and job_location not in candidate_location:
        location_score = 100 if (job.remote_allowed and candidate.willing_remote) else 35
    elif job_location and not candidate_location:
        location_score = 60 if job.remote_allowed else 40
    breakdown["location"] = {
        "score": location_score,
        "candidate_location": candidate.location,
        "job_location": job.location,
        "remote_fit": job.remote_allowed and candidate.willing_remote,
    }
    reasons.append("Remote/location fit is acceptable." if location_score >= 80 else "Location fit needs review.")

    authorization_score = 100
    if job.work_authorization:
        authorization_score = 100 if job.work_authorization.lower() in candidate.work_authorization.lower() else 35
    breakdown["authorization"] = {
        "score": authorization_score,
        "candidate": candidate.work_authorization,
        "required": job.work_authorization,
    }
    if authorization_score < 80:
        failures.append("Work authorization does not clearly match.")

    salary_score = 100
    if candidate.salary_expectation and job.salary_max:
        salary_score = 100 if candidate.salary_expectation <= job.salary_max else max(0, 100 - round(((candidate.salary_expectation - job.salary_max) / job.salary_max) * 100))
    breakdown["salary"] = {
        "score": salary_score,
        "candidate_expectation": candidate.salary_expectation,
        "job_min": job.salary_min,
        "job_max": job.salary_max,
    }

    education_terms = normalise_terms(job.education_requirements)
    education_matches = text_contains_any(candidate_education, education_terms)
    education_score = ratio_score(len(education_matches), len(education_terms))
    breakdown["education"] = {
        "score": education_score,
        "matched": sorted(education_matches),
        "missing": sorted(education_terms - education_matches),
    }

    cert_terms = normalise_terms(job.certification_requirements)
    cert_matches = text_contains_any(candidate_certs, cert_terms)
    cert_score = ratio_score(len(cert_matches), len(cert_terms))
    breakdown["certifications"] = {
        "score": cert_score,
        "matched": sorted(cert_matches),
        "missing": sorted(cert_terms - cert_matches),
    }

    weighted_total = Decimal("0")
    total_weight = Decimal("0")
    for key, weight in weights.items():
        if key in breakdown:
            weighted_total += Decimal(breakdown[key]["score"]) * Decimal(weight)
            total_weight += Decimal(weight)
    total_score = int(round(weighted_total / total_weight)) if total_weight else 0

    return {
        "total_score": max(0, min(100, total_score)),
        "breakdown": breakdown,
        "reasons": reasons,
        "must_have_failures": failures,
    }


def refresh_match_score(candidate, job):
    result = score_candidate_for_job(candidate, job)
    match_score, _ = MatchScore.objects.update_or_create(
        candidate=candidate,
        job=job,
        defaults={
            "total_score": result["total_score"],
            "breakdown": result["breakdown"],
            "reasons": result["reasons"],
            "must_have_failures": result["must_have_failures"],
            "scored_at": timezone.now(),
        },
    )
    return match_score


def score_job_against_active_candidates(job):
    return [
        refresh_match_score(candidate, job)
        for candidate in Candidate.objects.filter(status=Candidate.Status.ACTIVE)
    ]
