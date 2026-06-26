from django.contrib import admin

from .models import (
    ApplicationDraft,
    ApplicationSendLog,
    Candidate,
    CandidateDocument,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    DocumentTemplate,
    Employer,
    Job,
    MatchScore,
    ScoringWeight,
)


class CandidateDocumentInline(admin.TabularInline):
    model = CandidateDocument
    extra = 0


class CandidateSkillInline(admin.TabularInline):
    model = CandidateSkill
    extra = 0


class CandidateExperienceInline(admin.TabularInline):
    model = CandidateExperience
    extra = 0


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "location", "years_experience", "status")
    list_filter = ("status", "willing_remote")
    search_fields = ("first_name", "last_name", "email", "skills", "summary")
    inlines = [CandidateDocumentInline, CandidateSkillInline, CandidateExperienceInline]


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("candidate", "nationality", "education_level", "english_speaking", "valid_passport")
    search_fields = ("candidate__first_name", "candidate__last_name", "nationality", "migration_countries")
    readonly_fields = ("raw_answers",)


@admin.register(CandidateSkill)
class CandidateSkillAdmin(admin.ModelAdmin):
    list_display = ("candidate", "name", "years_experience")
    search_fields = ("candidate__first_name", "candidate__last_name", "name")


@admin.register(CandidateExperience)
class CandidateExperienceAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill", "years_experience")
    search_fields = ("candidate__first_name", "candidate__last_name", "skill", "details")


class JobInline(admin.TabularInline):
    model = Job
    extra = 0


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_name", "contact_email", "website")
    search_fields = ("name", "contact_name", "contact_email")
    inlines = [JobInline]


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "location", "remote_allowed", "status")
    list_filter = ("status", "remote_allowed")
    search_fields = ("title", "employer__name", "required_skills", "preferred_skills")


@admin.register(MatchScore)
class MatchScoreAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "total_score", "status", "scored_at")
    list_filter = ("status", "job__employer")
    search_fields = ("candidate__first_name", "candidate__last_name", "job__title")
    readonly_fields = ("breakdown", "reasons", "must_have_failures", "scored_at")


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "template_type", "is_default", "updated_at")
    list_filter = ("template_type", "is_default")


@admin.register(ScoringWeight)
class ScoringWeightAdmin(admin.ModelAdmin):
    list_display = ("key", "label", "weight", "enabled")
    list_editable = ("weight", "enabled")


@admin.register(ApplicationDraft)
class ApplicationDraftAdmin(admin.ModelAdmin):
    list_display = ("match_score", "recipient_email", "status", "created_at", "sent_at")
    list_filter = ("status",)
    search_fields = ("recipient_email", "subject", "match_score__candidate__email")


@admin.register(ApplicationSendLog)
class ApplicationSendLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "subject", "status", "created_at")
    list_filter = ("status",)

# Register your models here.
