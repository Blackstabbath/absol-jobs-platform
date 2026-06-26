from django import forms

from .models import (
    ApplicationDraft,
    Candidate,
    CandidateDocument,
    DocumentTemplate,
    Employer,
    Job,
    MatchScore,
    ScoringWeight,
    validate_upload_file,
)


class StyledFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "checkbox" if isinstance(field.widget, forms.CheckboxInput) else "control"
            field.widget.attrs.setdefault("class", css)


class UploadForm(forms.Form):
    file = forms.FileField(validators=[validate_upload_file], widget=forms.FileInput(attrs={"class": "control"}))


class CandidateDirectoryFilterForm(forms.Form):
    VIEW_CHOICES = (("cards", "Card view"), ("table", "Table view"))
    DENSITY_CHOICES = (("detailed", "Detailed cards"), ("compact", "Compact cards"))
    YES_NO_CHOICES = (("", "Any"), ("yes", "Yes"), ("no", "No"))

    q = forms.CharField(required=False, label="Search")
    view = forms.ChoiceField(required=False, choices=VIEW_CHOICES, initial="cards")
    density = forms.ChoiceField(required=False, choices=DENSITY_CHOICES, initial="detailed")
    status = forms.ChoiceField(required=False)
    skill = forms.ChoiceField(required=False)
    location = forms.ChoiceField(required=False)
    nationality = forms.ChoiceField(required=False)
    education = forms.ChoiceField(required=False)
    english = forms.ChoiceField(required=False)
    computer = forms.ChoiceField(required=False)
    migration_country = forms.ChoiceField(required=False)
    passport = forms.ChoiceField(required=False, choices=YES_NO_CHOICES)
    documents = forms.ChoiceField(required=False, choices=YES_NO_CHOICES)
    consent = forms.ChoiceField(required=False, choices=YES_NO_CHOICES)

    def __init__(self, *args, choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = choices or {}
        self.fields["status"].choices = [("", "Any status")] + list(Candidate.Status.choices)
        for field_name, label in [
            ("skill", "Any skill"),
            ("location", "Any location"),
            ("nationality", "Any nationality"),
            ("education", "Any education"),
            ("english", "Any English level"),
            ("computer", "Any computer level"),
            ("migration_country", "Any relocation country"),
        ]:
            self.fields[field_name].choices = [("", label)] + [(value, value) for value in choices.get(field_name, [])]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")


class CandidateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "location",
            "willing_remote",
            "work_authorization",
            "years_experience",
            "salary_expectation",
            "skills",
            "education",
            "certifications",
            "summary",
            "relevant_experience",
            "status",
        ]
        widgets = {
            "skills": forms.Textarea(attrs={"rows": 3}),
            "education": forms.Textarea(attrs={"rows": 3}),
            "certifications": forms.Textarea(attrs={"rows": 3}),
            "summary": forms.Textarea(attrs={"rows": 4}),
            "relevant_experience": forms.Textarea(attrs={"rows": 5}),
        }


class CandidateDocumentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CandidateDocument
        fields = ["document_type", "file", "notes"]


class EmployerForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Employer
        fields = ["name", "contact_name", "contact_email", "website", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}


class JobForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Job
        fields = [
            "employer",
            "title",
            "contact_email",
            "location",
            "remote_allowed",
            "min_years_experience",
            "salary_min",
            "salary_max",
            "required_skills",
            "preferred_skills",
            "work_authorization",
            "education_requirements",
            "certification_requirements",
            "description",
            "must_have_notes",
            "status",
        ]
        widgets = {
            "required_skills": forms.Textarea(attrs={"rows": 3}),
            "preferred_skills": forms.Textarea(attrs={"rows": 3}),
            "education_requirements": forms.Textarea(attrs={"rows": 3}),
            "certification_requirements": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "must_have_notes": forms.Textarea(attrs={"rows": 3}),
        }


class MatchStatusForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MatchScore
        fields = ["status"]


class ApplicationDraftForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ApplicationDraft
        fields = ["recipient_email", "subject", "email_body", "cover_letter", "cv_letter", "generated_resume_note"]
        widgets = {
            "email_body": forms.Textarea(attrs={"rows": 10}),
            "cover_letter": forms.Textarea(attrs={"rows": 10}),
            "cv_letter": forms.Textarea(attrs={"rows": 10}),
            "generated_resume_note": forms.Textarea(attrs={"rows": 5}),
        }


class DocumentTemplateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["name", "template_type", "subject", "body", "is_default"]
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}


class ScoringWeightForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ScoringWeight
        fields = ["label", "weight", "enabled"]
