# File: backend/orders/urls.py
# Module 3 – Bảng định tuyến URL của app orders.
# Mọi URL ở đây nằm sau tiền tố "api/orders/" khai báo trong config/urls.py.
#   /api/orders/cart/          -> GioHangView      (GET xem, POST thêm)
#   /api/orders/cart/CG001/    -> DongGioHangView  (PATCH sửa, DELETE xóa)

from django.urls import path

from .views import DongGioHangView, GioHangView

# Tên nhóm URL: khi cần tạo đường dẫn trong code, gọi reverse("orders:gio-hang"),
# không trùng với tên URL của module khác.
app_name = "orders"

urlpatterns = [
    path("cart/", GioHangView.as_view(), name="gio-hang"),
    path("cart/<str:ma_ctgh>/", DongGioHangView.as_view(), name="dong-gio-hang"),
]