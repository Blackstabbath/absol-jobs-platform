from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("candidates/directory/", views.candidate_directory, name="candidate_directory"),
    path("candidates/new/", views.candidate_create, name="candidate_create"),
    path("candidates/import/", views.import_candidates_view, name="import_candidates"),
    path("candidates/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidates/<int:pk>/edit/", views.candidate_edit, name="candidate_edit"),
    path("candidates/<int:pk>/documents/add/", views.candidate_document_add, name="candidate_document_add"),
    path("employers/", views.employer_list, name="employer_list"),
    path("employers/new/", views.employer_create, name="employer_create"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/new/", views.job_create, name="job_create"),
    path("jobs/import/", views.import_jobs_view, name="import_jobs"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/edit/", views.job_edit, name="job_edit"),
    path("jobs/<int:pk>/score/", views.score_job_view, name="score_job"),
    path("matches/", views.match_list, name="match_list"),
    path("matches/<int:pk>/", views.match_detail, name="match_detail"),
    path("matches/<int:pk>/draft/", views.create_draft_view, name="create_draft"),
    path("applications/", views.application_list, name="application_list"),
    path("applications/<int:pk>/", views.application_detail, name="application_detail"),
    path("applications/<int:pk>/send/", views.send_application_view, name="send_application"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("settings/weights/", views.weight_list, name="weight_list"),
    path("settings/weights/<int:pk>/edit/", views.weight_edit, name="weight_edit"),
]
