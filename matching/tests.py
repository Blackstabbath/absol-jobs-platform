from io import BytesIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import (
    ApplicationDraft,
    Candidate,
    CandidateDocument,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    DocumentTemplate,
    Employer,
    Job,
    MatchScore,
)
from .services.applications import create_application_draft, ensure_default_templates, render_template_string, send_application_draft
from .services.importers import import_candidates, import_jobs
from .services.scoring import refresh_match_score


class FixtureMixin:
    def make_candidate(self, **overrides):
        data = {
            "first_name": "Maya",
            "last_name": "Singh",
            "email": "maya@example.com",
            "location": "Toronto",
            "willing_remote": True,
            "work_authorization": "Canada",
            "years_experience": 5,
            "salary_expectation": 90000,
            "skills": "Python, Django, SQL, Excel",
            "education": "Bachelor of Computer Science",
            "certifications": "AWS Cloud Practitioner",
            "summary": "Backend developer with hiring platform experience.",
            "relevant_experience": "Built Django workflows and reporting tools.",
        }
        data.update(overrides)
        return Candidate.objects.create(**data)

    def make_job(self, **overrides):
        employer = overrides.pop(
            "employer",
            Employer.objects.create(name="Northwind", contact_email="jobs@northwind.test"),
        )
        data = {
            "employer": employer,
            "title": "Django Developer",
            "location": "Toronto",
            "remote_allowed": True,
            "min_years_experience": 3,
            "salary_max": 100000,
            "required_skills": "Python, Django",
            "preferred_skills": "SQL, AWS",
            "work_authorization": "Canada",
            "education_requirements": "Computer Science",
            "certification_requirements": "AWS",
        }
        data.update(overrides)
        return Job.objects.create(**data)


class ScoringTests(FixtureMixin, TestCase):
    def test_strong_match_scores_high_with_reasons(self):
        match = refresh_match_score(self.make_candidate(), self.make_job())

        self.assertGreaterEqual(match.total_score, 90)
        self.assertEqual(match.must_have_failures, [])
        self.assertIn("required_skills", match.breakdown)

    def test_missing_required_skill_records_failure(self):
        candidate = self.make_candidate(skills="Excel")
        match = refresh_match_score(candidate, self.make_job())

        self.assertLess(match.total_score, 80)
        self.assertTrue(match.must_have_failures)

    def test_missing_data_does_not_crash(self):
        candidate = self.make_candidate(skills="", location="", work_authorization="")
        job = self.make_job(required_skills="", preferred_skills="", work_authorization="")
        match = refresh_match_score(candidate, job)

        self.assertGreaterEqual(match.total_score, 0)
        self.assertLessEqual(match.total_score, 100)


class ImportTests(TestCase):
    def test_candidate_csv_import_creates_and_updates(self):
        upload = SimpleUploadedFile(
            "candidates.csv",
            b"first_name,last_name,email,skills\nMaya,Singh,maya@example.com,Python\n",
            content_type="text/csv",
        )
        result = import_candidates(upload)

        self.assertEqual(result["created"], 1)
        self.assertEqual(Candidate.objects.get().email, "maya@example.com")

    def test_job_csv_import_requires_employer_and_title(self):
        upload = SimpleUploadedFile(
            "jobs.csv",
            b"employer,title,required_skills\nNorthwind,Django Developer,Python\n,Missing Employer,SQL\n",
            content_type="text/csv",
        )
        result = import_jobs(upload)

        self.assertEqual(result["created"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(Job.objects.get().title, "Django Developer")

    def test_sarp_csv_import_aggregates_repeated_skill_columns(self):
        upload = SimpleUploadedFile(
            "sarp.csv",
            (
                '"Full Name (as per UNHCR or ID)","Email Address","WhatsApp Number (active contact)",'
                '"Which place you are currently living in","What is the main field that you have skill in?",'
                '"How many years of work experience do you have in this field?\\n\\n(Do not include years spent studying in this occupation)",'
                '"Details of your work experience are required:\\nWrite about: Company Name",'
                '"What is the main field that you have skill 1 in?",'
                '"How many years of work experience do you have in this field?\\n\\n(Do not include years spent studying in this occupation)",'
                '"Details of your work experience are required:\\nWrite about: Company Name",'
                '"What is your highest level of education?   "\n'
                '"Ahmad Khan","ahmad@example.com","+1555000","Malaysia","Carpentry","4","Built furniture","Welding","2","Metal work","Diploma"\n'
            ).encode(),
            content_type="text/csv",
        )

        result = import_candidates(upload)
        candidate = Candidate.objects.get(email="ahmad@example.com")

        self.assertEqual(result["created"], 1)
        self.assertIn("Carpentry", candidate.skills)
        self.assertIn("Welding", candidate.skills)
        self.assertEqual(candidate.years_experience, 4)
        self.assertIn("Built furniture", candidate.relevant_experience)
        self.assertTrue(CandidateProfile.objects.filter(candidate=candidate).exists())
        self.assertEqual(CandidateSkill.objects.filter(candidate=candidate).count(), 2)
        self.assertEqual(CandidateExperience.objects.filter(candidate=candidate).count(), 2)
        self.assertIn("Full Name (as per UNHCR or ID)", candidate.profile.raw_answers)

    def test_sarp_profile_preserves_relocation_language_and_consent(self):
        upload = SimpleUploadedFile(
            "sarp-rich.csv",
            (
                '"Full Name (as per UNHCR or ID)","Email Address","Nationality","Which place you are currently living in",'
                '"How well do you speak English?","  Please select your computer skill level   ",'
                '"Are you willing to migrate if you are selected for a job-based opportunity?  ",'
                '"  Which countries are you interested in migrating to? (select all that apply)  ",'
                '"  Do you have a valid passport?  ",'
                '"   I authorize ARCMY/Humanity First to share my profile with verified employers and immigration platforms (such as Talent Beyond Boundaries, TalentLift)  ",'
                '"   I agree to be contacted via WhatsApp, phone, or email for opportunities matching my profile   "\n'
                '"Sara Ali","sara@example.com","Afghan","Malaysia","Good","Intermediate","Yes","Canada, Australia","Yes","Yes","Yes"\n'
            ).encode(),
            content_type="text/csv",
        )

        import_candidates(upload)
        profile = Candidate.objects.get(email="sara@example.com").profile

        self.assertEqual(profile.nationality, "Afghan")
        self.assertEqual(profile.english_speaking, "Good")
        self.assertEqual(profile.computer_skill_level, "Intermediate")
        self.assertIn("Canada", profile.migration_countries)
        self.assertEqual(profile.valid_passport, "Yes")


class ApplicationTests(FixtureMixin, TestCase):
    def test_template_rendering_tolerates_missing_values(self):
        candidate = self.make_candidate(phone="")
        job = self.make_job()
        match = refresh_match_score(candidate, job)

        rendered = render_template_string("{{ candidate.full_name }} - {{ candidate.phone|default:'n/a' }}", {"candidate": candidate, "match": match})

        self.assertIn("Maya Singh", rendered)

    def test_create_application_draft_without_sending(self):
        match = refresh_match_score(self.make_candidate(), self.make_job())
        draft = create_application_draft(match)

        self.assertEqual(draft.status, ApplicationDraft.Status.DRAFT)
        self.assertIn("Maya Singh", draft.subject)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_send_application_logs_success(self):
        candidate = self.make_candidate()
        upload = SimpleUploadedFile("resume.txt", b"Resume", content_type="text/plain")
        CandidateDocument.objects.create(candidate=candidate, document_type=CandidateDocument.DocumentType.RESUME, file=upload)
        match = refresh_match_score(candidate, self.make_job())
        draft = create_application_draft(match)

        send_application_draft(draft)

        draft.refresh_from_db()
        self.assertEqual(draft.status, ApplicationDraft.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(draft.send_logs.count(), 1)


class PermissionTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_logged_in_user_can_access_dashboard(self):
        User.objects.create_user(username="admin", password="pass12345")
        self.client.login(username="admin", password="pass12345")

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_candidate_directory_requires_login(self):
        response = self.client.get(reverse("candidate_directory"))

        self.assertEqual(response.status_code, 302)

    def test_candidate_directory_filters_by_skill(self):
        User.objects.create_user(username="admin", password="pass12345")
        self.client.login(username="admin", password="pass12345")
        candidate = Candidate.objects.create(
            first_name="Amina",
            last_name="Khan",
            email="amina@example.com",
            skills="Carpentry",
            location="Malaysia",
        )
        CandidateProfile.objects.create(candidate=candidate, nationality="Pakistani", english_speaking="Good")
        CandidateSkill.objects.create(candidate=candidate, name="Carpentry")

        response = self.client.get(reverse("candidate_directory"), {"skill": "Carpentry"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amina Khan")
        self.assertContains(response, "Carpentry")

    def test_candidate_detail_shows_original_answers(self):
        User.objects.create_user(username="admin", password="pass12345")
        self.client.login(username="admin", password="pass12345")
        candidate = Candidate.objects.create(first_name="Omar", last_name="Noor", email="omar@example.com")
        CandidateProfile.objects.create(candidate=candidate, raw_answers={"Original Question": "Original Answer"})

        response = self.client.get(reverse("candidate_detail", args=[candidate.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Original Question")
        self.assertContains(response, "Original Answer")

# Create your tests here.
