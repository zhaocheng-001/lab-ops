from django.urls import path

from . import views

urlpatterns = [
    path("overview/", views.overview, name="statistics-overview"),
    path("dashboard/", views.dashboard, name="statistics-dashboard"),
    path("by-laboratory/", views.by_laboratory, name="statistics-by-laboratory"),
    path("by-category/", views.by_category, name="statistics-by-category"),
    path("trend/", views.trend, name="statistics-trend"),
    path("device-ranking/", views.device_ranking, name="statistics-device-ranking"),
    path("applicant-ranking/", views.applicant_ranking, name="statistics-applicant-ranking"),
    path("export/", views.export_report, name="statistics-export"),
]
