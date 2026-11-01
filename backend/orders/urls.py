# File: backend/orders/urls.py
# Module 3 – Bảng định tuyến URL của app orders.
# Mọi URL ở đây nằm sau tiền tố "api/orders/" khai báo trong config/urls.py.
#   /api/orders/                        -> DonHangView         (GET đơn của tôi, POST đặt hàng)
#   /api/orders/cart/                   -> GioHangView         (GET xem, POST thêm)
#   /api/orders/cart/CG001/             -> DongGioHangView     (PATCH sửa, DELETE xóa)
#   /api/orders/checkout/               -> TrangThanhToanView  (GET trang thanh toán)
#   /api/orders/DH001/                  -> ChiTietDonView      (GET chi tiết đơn của tôi)
#   /api/orders/DH001/da-nhan-hang/     -> DaNhanHangView      (POST đã nhận hàng)
#   /api/orders/DH001/payment/          -> ThanhToanGiaLapView (POST cổng thanh toán giả lập)
#
# Django thử các dòng TỪ TRÊN XUỐNG và dừng ở dòng khớp đầu tiên.
# "<str:ma_dh>/" khớp với MỌI chữ, kể cả "cart" và "checkout", nên các dòng
# có tham số ma_dh phải đứng SAU các đường dẫn cố định.

from django.urls import path

from .views import (
    ChiTietDonView,
    DaNhanHangView,
    DongGioHangView,
    DonHangView,
    GioHangView,
    ThanhToanGiaLapView,
    TrangThanhToanView,
)

# Tên nhóm URL: khi cần tạo đường dẫn trong code, gọi reverse("orders:gio-hang"),
# không trùng với tên URL của module khác.
app_name = "orders"

urlpatterns = [
    path("", DonHangView.as_view(), name="don-hang"),
    path("cart/", GioHangView.as_view(), name="gio-hang"),
    path("cart/<str:ma_ctgh>/", DongGioHangView.as_view(), name="dong-gio-hang"),
    path("checkout/", TrangThanhToanView.as_view(), name="thanh-toan"),
    # ----- Đơn hàng phía khách (giai đoạn 4, bước 8A) – luôn để cuối danh sách -----
    path("<str:ma_dh>/", ChiTietDonView.as_view(), name="chi-tiet-don"),
    path("<str:ma_dh>/da-nhan-hang/", DaNhanHangView.as_view(), name="da-nhan-hang"),
    path("<str:ma_dh>/payment/", ThanhToanGiaLapView.as_view(), name="thanh-toan-gia-lap"),
]