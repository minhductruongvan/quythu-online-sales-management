from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    # Giao diện HTML
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("chi-tiet/", views.detail_report_view, name="detail"),

    # API JSON cho AJAX
    path("api/dashboard-data/", views.api_dashboard_data, name="api_dashboard_data"),
    path("api/detail-data/", views.api_detail_data, name="api_detail_data"),

    # Xuất báo cáo
    path("export/csv/", views.export_report_csv, name="export_csv"),
]
