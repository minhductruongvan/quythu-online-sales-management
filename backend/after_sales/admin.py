# File: backend/after_sales/admin.py
# Module 4 – Đăng ký các bảng hậu mãi vào Django Admin để xem dữ liệu khi kiểm thử.
from django.contrib import admin

from . import models as m

for mo_hinh in (m.NguyenNhan, m.LichSuNguyenNhan, m.YeuCauHuy, m.XuLyGiaoThatBai, m.YeuCauDoiTra, m.DongDoiTra,
                m.AnhMinhChung, m.GiaoDichHoanTien, m.BienDongKho, m.LichSuHauMai, m.ThongBaoHauMai):
    admin.site.register(mo_hinh)
