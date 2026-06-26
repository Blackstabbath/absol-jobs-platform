from django.core.mail import EmailMessage
from django.template import Context, Template
from django.utils import timezone

from matching.models import ApplicationDraft, ApplicationSendLog, CandidateDocument, DocumentTemplate


DEFAULT_TEMPLATES = {
    DocumentTemplate.TemplateType.EMAIL: {
        "name": "Default application email",
        "subject": "Application: {{ candidate.full_name }} for {{ job.title }}",
        "body": (
            "Hello {{ employer.contact_name|default:employer.name }},\n\n"
            "Please find attached the application for {{ candidate.full_name }} for the "
            "{{ job.title }} role at {{ employer.name }}.\n\n"
            "Match score: {{ match.total_score }}%.\n"
            "Highlights:\n{% for reason in match.reasons %}- {{ reason }}\n{% endfor %}\n"
            "Best regards,\nAbsol Jobs"
        ),
    },
    DocumentTemplate.TemplateType.COVER_LETTER: {
        "name": "Default cover letter",
        "subject": "",
        "body": (
            "Dear {{ employer.contact_name|default:'Hiring Team' }},\n\n"
            "I am pleased to apply for the {{ job.title }} role at {{ employer.name }}. "
            "My background includes {{ candidate.years_experience }} years of experience "
            "and skills including {{ candidate.skills }}.\n\n"
            "{{ candidate.summary }}\n\n"
            "Sincerely,\n{{ candidate.full_name }}"
        ),
    },
    DocumentTemplate.TemplateType.CV_LETTER: {
        "name": "Default CV letter",
        "subject": "",
        "body": (
            "{{ candidate.full_name }}\n{{ candidate.email }} | {{ candidate.phone }} | {{ candidate.location }}\n\n"
            "Target role: {{ job.title }} at {{ employer.name }}\n"
            "Relevant skills: {{ candidate.skills }}\n\n"
            "{{ candidate.relevant_experience|default:candidate.summary }}"
        ),
    },
    DocumentTemplate.TemplateType.RESUME_NOTE: {
        "name": "Default resume note",
        "subject": "",
        "body": (
            "Resume package for {{ candidate.full_name }} applying to {{ job.title }} at {{ employer.name }}.\n"
            "Match score: {{ match.total_score }}%."
        ),
    },
}


def ensure_default_templates():
    for template_type, defaults in DEFAULT_TEMPLATES.items():
        DocumentTemplate.objects.get_or_create(
            template_type=template_type,
            is_default=True,
            defaults=defaults,
        )


def get_default_template(template_type):
    ensure_default_templates()
    return (
        DocumentTemplate.objects.filter(template_type=template_type, is_default=True).first()
        or DocumentTemplate.objects.filter(template_type=template_type).first()
    )


def render_template_string(template_string, context):
    return Template(template_string).render(Context(context)).strip()


def build_context(match_score):
    candidate = match_score.candidate
    job = match_score.job
    return {
        "candidate": candidate,
        "job": job,
        "employer": job.employer,
        "match": match_score,
        "matched_required_skills": match_score.breakdown.get("required_skills", {}).get("matched", []),
        "matched_preferred_skills": match_score.breakdown.get("preferred_skills", {}).get("matched", []),
    }


def create_application_draft(match_score):
    context = build_context(match_score)
    email_template = get_default_template(DocumentTemplate.TemplateType.EMAIL)
    cover_template = get_default_template(DocumentTemplate.TemplateType.COVER_LETTER)
    cv_template = get_default_template(DocumentTemplate.TemplateType.CV_LETTER)
    resume_note_template = get_default_template(DocumentTemplate.TemplateType.RESUME_NOTE)

    recipient = match_score.job.application_email
    if not recipient:
        raise ValueError("This job/employer has no application email.")

    resume_docs = CandidateDocument.objects.filter(
        candidate=match_score.candidate,
        document_type=CandidateDocument.DocumentType.RESUME,
    )
    attachments = [
        {
            "name": doc.file.name.split("/")[-1],
            "path": doc.file.name,
            "type": doc.document_type,
        }
        for doc in resume_docs
    ]

    return ApplicationDraft.objects.create(
        match_score=match_score,
        recipient_email=recipient,
        subject=render_template_string(email_template.subject, context),
        email_body=render_template_string(email_template.body, context),
        cover_letter=render_template_string(cover_template.body, context),
        cv_letter=render_template_string(cv_template.body, context),
        generated_resume_note=render_template_string(resume_note_template.body, context),
        attachments=attachments,
    )


def approve_draft(draft):
    draft.status = ApplicationDraft.Status.APPROVED
    draft.approved_at = timezone.now()
    draft.failure_message = ""
    draft.save(update_fields=["status", "approved_at", "failure_message", "updated_at"])
    return draft


def send_application_draft(draft):
    if draft.status == ApplicationDraft.Status.DRAFT:
        approve_draft(draft)

    message = EmailMessage(
        subject=draft.subject,
        body=draft.email_body,
        to=[draft.recipient_email],
    )
    for attachment in draft.attachments:
        document = CandidateDocument.objects.filter(file=attachment.get("path")).first()
        if document:
            message.attach_file(document.file.path)

    try:
        message.send(fail_silently=False)
    except Exception as exc:
        draft.status = ApplicationDraft.Status.FAILED
        draft.failure_message = str(exc)
        draft.save(update_fields=["status", "failure_message", "updated_at"])
        ApplicationSendLog.objects.create(
            draft=draft,
            recipient_email=draft.recipient_email,
            subject=draft.subject,
            status=ApplicationDraft.Status.FAILED,
            message=str(exc),
            attachment_snapshot=draft.attachments,
        )
        raise

    draft.status = ApplicationDraft.Status.SENT
    draft.sent_at = timezone.now()
    draft.failure_message = ""
    draft.save(update_fields=["status", "sent_at", "failure_message", "updated_at"])
    ApplicationSendLog.objects.create(
        draft=draft,
        recipient_email=draft.recipient_email,
        subject=draft.subject,
        status=ApplicationDraft.Status.SENT,
        message="Sent successfully.",
        attachment_snapshot=draft.attachments,
    )
    return draft
