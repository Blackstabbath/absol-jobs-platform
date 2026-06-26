from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


def validate_upload_file(value):
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if value.size > max_size:
        raise ValidationError(f"File must be {settings.MAX_UPLOAD_SIZE_MB} MB or smaller.")

    allowed = {".csv", ".xlsx", ".xls", ".pdf", ".docx", ".txt"}
    suffix = Path(value.name).suffix.lower()
    if suffix not in allowed:
        raise ValidationError(f"Unsupported file type: {suffix or 'unknown'}.")


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Candidate(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        ARCHIVED = "archived", "Archived"

    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=160, blank=True)
    willing_remote = models.BooleanField(default=True)
    work_authorization = models.CharField(max_length=160, blank=True)
    years_experience = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    salary_expectation = models.PositiveIntegerField(null=True, blank=True)
    skills = models.TextField(blank=True, help_text="Comma-separated skills.")
    education = models.TextField(blank=True)
    certifications = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    relevant_experience = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_absolute_url(self):
        return reverse("candidate_detail", args=[self.pk])


class CandidateDocument(TimestampedModel):
    class DocumentType(models.TextChoices):
        RESUME = "resume", "Resume"
        CV = "cv", "CV"
        COVER_LETTER = "cover_letter", "Cover letter"
        OTHER = "other", "Other"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DocumentType.choices, default=DocumentType.RESUME)
    file = models.FileField(upload_to="candidate_documents/", validators=[validate_upload_file])
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["candidate", "document_type", "-created_at"]

    def __str__(self):
        return f"{self.candidate} - {self.get_document_type_display()}"


class CandidateProfile(TimestampedModel):
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, related_name="profile")
    raw_answers = models.JSONField(default=dict)
    gender = models.CharField(max_length=80, blank=True)
    date_of_birth = models.CharField(max_length=80, blank=True)
    aims_number = models.CharField(max_length=120, blank=True)
    nationality = models.CharField(max_length=160, blank=True)
    arrival_year = models.CharField(max_length=20, blank=True)
    majlis = models.CharField(max_length=160, blank=True)
    unhcr_registration = models.TextField(blank=True)
    marital_status = models.CharField(max_length=120, blank=True)
    education_level = models.CharField(max_length=180, blank=True)
    field_of_study = models.CharField(max_length=220, blank=True)
    institution = models.CharField(max_length=220, blank=True)
    education_year = models.CharField(max_length=40, blank=True)
    education_country = models.CharField(max_length=160, blank=True)
    education_verified = models.CharField(max_length=120, blank=True)
    english_speaking = models.CharField(max_length=120, blank=True)
    english_reading_writing = models.CharField(max_length=120, blank=True)
    english_test = models.CharField(max_length=180, blank=True)
    english_score = models.CharField(max_length=120, blank=True)
    basic_computer_skills = models.CharField(max_length=120, blank=True)
    computer_skill_level = models.CharField(max_length=120, blank=True)
    willing_to_migrate = models.CharField(max_length=120, blank=True)
    migration_countries = models.TextField(blank=True)
    migration_reason = models.TextField(blank=True)
    health_conditions = models.TextField(blank=True)
    linkedin_url = models.URLField(blank=True)
    valid_passport = models.CharField(max_length=120, blank=True)
    passport_expiry = models.CharField(max_length=80, blank=True)
    can_find_own_employer = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=220, blank=True)
    consent_truthful = models.CharField(max_length=80, blank=True)
    consent_database = models.CharField(max_length=80, blank=True)
    consent_share = models.CharField(max_length=80, blank=True)
    consent_contact = models.CharField(max_length=80, blank=True)
    consent_more_documents = models.CharField(max_length=80, blank=True)
    consent_data_storage = models.CharField(max_length=80, blank=True)
    photo_document_upload = models.TextField(blank=True)
    resume_upload = models.TextField(blank=True)
    education_upload = models.TextField(blank=True)
    certification_upload = models.TextField(blank=True)
    additional_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["candidate__last_name", "candidate__first_name"]

    def __str__(self):
        return f"SARP profile for {self.candidate}"

    @property
    def document_readiness(self):
        available = [
            bool(self.resume_upload),
            bool(self.education_upload),
            bool(self.certification_upload),
            bool(self.photo_document_upload),
        ]
        return sum(available), len(available)

    @property
    def consent_complete(self):
        values = [
            self.consent_truthful,
            self.consent_database,
            self.consent_share,
            self.consent_contact,
            self.consent_more_documents,
            self.consent_data_storage,
        ]
        return all(str(value).strip().lower() in {"yes", "true", "i agree", "agreed", "1"} for value in values if value)


class CandidateSkill(TimestampedModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="skill_records")
    name = models.CharField(max_length=220)
    years_experience = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    source_label = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ["candidate", "name"]

    def __str__(self):
        return f"{self.name} ({self.candidate})"


class CandidateExperience(TimestampedModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="experience_records")
    skill = models.CharField(max_length=220, blank=True)
    years_experience = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    details = models.TextField(blank=True)
    source_label = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ["candidate", "skill", "id"]

    def __str__(self):
        return f"{self.skill or 'Experience'} ({self.candidate})"


class Employer(TimestampedModel):
    name = models.CharField(max_length=180, unique=True)
    contact_name = models.CharField(max_length=160, blank=True)
    contact_email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Job(TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PAUSED = "paused", "Paused"
        CLOSED = "closed", "Closed"

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=180)
    contact_email = models.EmailField(blank=True)
    location = models.CharField(max_length=160, blank=True)
    remote_allowed = models.BooleanField(default=False)
    min_years_experience = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    required_skills = models.TextField(blank=True, help_text="Comma-separated must-have skills.")
    preferred_skills = models.TextField(blank=True, help_text="Comma-separated nice-to-have skills.")
    work_authorization = models.CharField(max_length=160, blank=True)
    education_requirements = models.TextField(blank=True)
    certification_requirements = models.TextField(blank=True)
    description = models.TextField(blank=True)
    must_have_notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["employer__name", "title"]
        unique_together = ["employer", "title"]

    def __str__(self):
        return f"{self.title} at {self.employer}"

    @property
    def application_email(self):
        return self.contact_email or self.employer.contact_email

    def get_absolute_url(self):
        return reverse("job_detail", args=[self.pk])


class ScoringWeight(TimestampedModel):
    key = models.SlugField(unique=True)
    label = models.CharField(max_length=120)
    weight = models.PositiveIntegerField(default=10)
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.label}: {self.weight}"


class MatchScore(TimestampedModel):
    class Status(models.TextChoices):
        UNREVIEWED = "unreviewed", "Unreviewed"
        SHORTLISTED = "shortlisted", "Shortlisted"
        REJECTED = "rejected", "Rejected"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="match_scores")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="match_scores")
    total_score = models.PositiveIntegerField(default=0)
    breakdown = models.JSONField(default=dict)
    reasons = models.JSONField(default=list)
    must_have_failures = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNREVIEWED)
    scored_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-total_score", "candidate__last_name"]
        unique_together = ["candidate", "job"]

    def __str__(self):
        return f"{self.candidate} x {self.job}: {self.total_score}%"


class DocumentTemplate(TimestampedModel):
    class TemplateType(models.TextChoices):
        EMAIL = "email", "Email body"
        COVER_LETTER = "cover_letter", "Cover letter"
        CV_LETTER = "cv_letter", "CV letter"
        RESUME_NOTE = "resume_note", "Resume note"

    name = models.CharField(max_length=160)
    template_type = models.CharField(max_length=30, choices=TemplateType.choices)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField()
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["template_type", "-is_default", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class ApplicationDraft(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    match_score = models.ForeignKey(MatchScore, on_delete=models.CASCADE, related_name="application_drafts")
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    email_body = models.TextField()
    cover_letter = models.TextField(blank=True)
    cv_letter = models.TextField(blank=True)
    generated_resume_note = models.TextField(blank=True)
    attachments = models.JSONField(default=list)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failure_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Application for {self.match_score.candidate} to {self.match_score.job}"


class ApplicationSendLog(TimestampedModel):
    draft = models.ForeignKey(ApplicationDraft, on_delete=models.CASCADE, related_name="send_logs")
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    attachment_snapshot = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.status}: {self.recipient_email} ({self.created_at:%Y-%m-%d})"
