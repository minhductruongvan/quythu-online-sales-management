# File: backend/after_sales/urls.py
# Module 4 – Bảng định tuyến URL. Mọi URL nằm sau tiền tố "api/after-sales/" khai báo trong config/urls.py.
# Django thử các dòng TỪ TRÊN XUỐNG và dừng ở dòng khớp đầu tiên, nên đường dẫn cố định
# (ví dụ "xu-ly-hang-loat/", "thanh-toan-thua/", "xuat/") phải đứng TRƯỚC đường dẫn có tham số.

from django.urls import path

from . import views as v

app_name = "after_sales"

urlpatterns = [
    # ----- Khách hàng: UC01, UC04 -----
    path("nguyen-nhan/", v.NguyenNhanChoKhachView.as_view(), name="nguyen-nhan-khach"),
    path("huy/", v.GuiYeuCauHuyView.as_view(), name="gui-yeu-cau-huy"),
    path("huy/<str:ma_yc_huy>/thu-hoi/", v.ThuHoiHuyView.as_view(), name="thu-hoi-huy"),
    path("doi-tra/", v.GuiYeuCauDoiTraView.as_view(), name="gui-yeu-cau-doi-tra"),
    path("doi-tra/dong/<str:ma_dh>/", v.DongDoiTraKhachView.as_view(), name="dong-doi-tra"),
    path("doi-tra/<str:ma_yc_doi_tra>/thu-hoi/", v.ThuHoiDoiTraView.as_view(), name="thu-hoi-doi-tra"),
    path("thong-bao/", v.ThongBaoKhachView.as_view(), name="thong-bao-khach"),
    path("thong-bao/<str:ma_thong_bao>/da-doc/", v.ThongBaoKhachView.as_view(), name="thong-bao-khach-da-doc"),

    # ----- Khách hàng và nhân viên: UC09 -----
    path("lich-su/", v.LichSuView.as_view(), name="lich-su"),
    path("lich-su/<str:loai>/<str:ma_yeu_cau>/", v.TimelineView.as_view(), name="timeline"),

    # ----- Nhân viên: UC07 danh mục nguyên nhân -----
    path("staff/nguyen-nhan/", v.NguyenNhanView.as_view(), name="nv-nguyen-nhan"),
    path("staff/nguyen-nhan/<str:ma_nguyen_nhan>/", v.NguyenNhanChiTietView.as_view(), name="nv-nguyen-nhan-chi-tiet"),
    path("staff/nguyen-nhan/<str:ma_nguyen_nhan>/<str:thao_tac>/", v.NguyenNhanTrangThaiView.as_view(), name="nv-nguyen-nhan-trang-thai"),

    # ----- Nhân viên: UC02 xử lý hủy đơn -----
    path("staff/huy/", v.HuyDanhSachView.as_view(), name="nv-huy-danh-sach"),
    path("staff/huy/xu-ly-hang-loat/", v.HuyHangLoatView.as_view(), name="nv-huy-hang-loat"),
    path("staff/huy/<str:ma_yc_huy>/", v.HuyChiTietView.as_view(), name="nv-huy-chi-tiet"),
    path("staff/huy/<str:ma_yc_huy>/xu-ly/", v.HuyXuLyView.as_view(), name="nv-huy-xu-ly"),

    # ----- Nhân viên: UC03 giao hàng không thành công -----
    path("staff/giao-that-bai/", v.GiaoThatBaiDanhSachView.as_view(), name="nv-giao-that-bai"),
    path("staff/giao-that-bai/xu-ly/<str:ma_xu_ly>/nhap-kho/", v.GiaoThatBaiNhapKhoView.as_view(), name="nv-nhap-kho"),
    path("staff/giao-that-bai/<str:ma_dh>/", v.GiaoThatBaiXuLyView.as_view(), name="nv-giao-that-bai-don"),
    path("staff/giao-that-bai/<str:ma_dh>/xu-ly/", v.GiaoThatBaiXuLyView.as_view(), name="nv-giao-that-bai-xu-ly"),

    # ----- Nhân viên: UC05 đổi/trả -----
    path("staff/doi-tra/", v.DoiTraDanhSachView.as_view(), name="nv-doi-tra-danh-sach"),
    path("staff/doi-tra/<str:ma_yc_doi_tra>/", v.DoiTraChiTietView.as_view(), name="nv-doi-tra-chi-tiet"),
    path("staff/doi-tra/<str:ma_yc_doi_tra>/<str:thao_tac>/", v.DoiTraThaoTacView.as_view(), name="nv-doi-tra-thao-tac"),

    # ----- Nhân viên: UC06 hoàn tiền -----
    path("staff/hoan-tien/", v.HoanTienDanhSachView.as_view(), name="nv-hoan-tien-danh-sach"),
    path("staff/hoan-tien/thanh-toan-thua/", v.HoanTienThanhToanThuaView.as_view(), name="nv-hoan-tien-thua"),
    path("staff/hoan-tien/<str:ma_hoan_tien>/", v.HoanTienChiTietView.as_view(), name="nv-hoan-tien-chi-tiet"),
    path("staff/hoan-tien/<str:ma_hoan_tien>/<str:thao_tac>/", v.HoanTienThaoTacView.as_view(), name="nv-hoan-tien-thao-tac"),

    # ----- Nhân viên: UC08 thống kê, thông báo -----
    path("staff/thong-ke/", v.ThongKeView.as_view(), name="nv-thong-ke"),
    path("staff/thong-ke/xuat/", v.ThongKeXuatView.as_view(), name="nv-thong-ke-xuat"),
    path("staff/thong-bao/", v.ThongBaoNhanVienView.as_view(), name="nv-thong-bao"),
    path("staff/thong-bao/<str:ma_thong_bao>/da-doc/", v.ThongBaoNhanVienView.as_view(), name="nv-thong-bao-da-doc"),
]
