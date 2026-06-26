# Absol Jobs Application Matching Platform

Internal Django app for scoring candidates against employer/job requirements, generating reviewed application drafts, and sending approved applications by email.

## What V1 Does

- Imports candidates from CSV/XLSX.
- Imports jobs and employers from CSV/XLSX or manual forms.
- Stores resume/CV documents for candidates.
- Scores active candidates against jobs using transparent, editable rule weights.
- Shows match breakdowns, reasons, and must-have failures.
- Generates email, cover letter, CV letter, and resume notes from editable templates.
- Requires a human review screen before sending.
- Sends via SMTP and stores an application send audit log.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and log in with the superuser account.

## Import Formats

Candidate CSV/XLSX minimum columns:

```csv
first_name,last_name,email,skills
Maya,Singh,maya@example.com,"Python, Django, SQL"
```

Useful candidate columns:

```text
phone, location, willing_remote, work_authorization, years_experience,
salary_expectation, education, certifications, summary, relevant_experience, status
```

Job CSV/XLSX minimum columns:

```csv
employer,title,required_skills
Northwind,Django Developer,"Python, Django"
```

Useful job columns:

```text
contact_name, employer_email, job_email, website, location, remote_allowed,
min_years_experience, salary_min, salary_max, preferred_skills,
work_authorization, education_requirements, certification_requirements,
description, must_have_notes, status
```

## PythonAnywhere Deployment Notes

1. Upload or clone this project into PythonAnywhere.
2. Create a virtualenv and run `pip install -r requirements.txt`.
3. Create a MySQL database.
4. Set environment variables based on `.env.example`.
5. Use a `DATABASE_URL` like:

```text
mysql://username:password@username.mysql.pythonanywhere-services.com/username$absol_jobs
```

6. Run:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

7. Configure the PythonAnywhere WSGI file to point at `absol_jobs.wsgi`.
8. Configure SMTP credentials with an app password or provider-specific SMTP password.

## Safety Notes

- Do not enable automatic sending without review. The app is intentionally draft-first.
- Uploaded media should be treated as sensitive candidate data.
- The rule-based scoring engine is transparent but not a legal hiring decision system. Use it as an internal prioritization aid and keep human review in the loop.
