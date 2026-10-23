from django.urls import path

from .views import DangKyKhachHangView

urlpatterns = [
    path(
        "register/",
        DangKyKhachHangView.as_view(),
        name="dang-ky-khach-hang",
    ),
]