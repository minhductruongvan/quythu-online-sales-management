# File: backend/after_sales/serializers.py
# Module 4 – Serializer. Phần vào: kiểm tra định dạng dữ liệu gửi lên (nghiệp vụ nằm ở services.py).
# Phần ra: khách hàng và nhân viên dùng serializer KHÁC NHAU; khách không bao giờ thấy ghi chú
# nội bộ hay tên nhân viên (M4-BR12).

import json

from rest_framework import serializers

from .models import (
    DongDoiTra,
    GiaoDichHoanTien,
    HinhThucDoiTra,
    HuongXuLyGiao,
    LichSuHauMai,
    LoaiXuLy,
    NguyenNhan,
    XuLyGiaoThatBai,
    YeuCauDoiTra,
    YeuCauHuy,
)
from .services import DichVuHuyDon, tai_khoan_nhan_da_che


# ==========================================================
# A. ĐẦU VÀO
# ==========================================================
class GuiYeuCauHuySerializer(serializers.Serializer):
    ma_dh = serializers.CharField(max_length=10)
    ma_nguyen_nhan = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    ghi_chu = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class XuLyYeuCauHuySerializer(serializers.Serializer):
    quyet_dinh = serializers.ChoiceField(choices=["DUYET", "TU_CHOI"])
    ly_do_tu_choi = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class XuLyHangLoatSerializer(serializers.Serializer):
    ma_yeu_cau = serializers.ListField(child=serializers.CharField(max_length=10), allow_empty=False)
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class DongYeuCauField(serializers.Field):
    """Danh sách dòng sản phẩm. Nhận list (JSON) hoặc chuỗi JSON (khi gửi multipart cùng ảnh)."""

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                raise serializers.ValidationError("Danh sách sản phẩm không hợp lệ.")
        if not isinstance(data, list):
            raise serializers.ValidationError("Danh sách sản phẩm không hợp lệ.")
        ket_qua = []
        for d in data:
            if not isinstance(d, dict) or not isinstance(d.get("so_luong"), int) or isinstance(d.get("so_luong"), bool):
                raise serializers.ValidationError("Mỗi dòng cần ma_ctdh và so_luong là số nguyên.")
            ket_qua.append({"ma_ctdh": d.get("ma_ctdh"), "so_luong": d["so_luong"],
                            "ma_bien_the_doi": d.get("ma_bien_the_doi")})
        return ket_qua

    def to_representation(self, value):
        return value


class GuiYeuCauDoiTraSerializer(serializers.Serializer):
    ma_dh = serializers.CharField(max_length=10)
    hinh_thuc = serializers.ChoiceField(choices=HinhThucDoiTra.choices)
    ma_nguyen_nhan = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    mo_ta = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    dong = DongYeuCauField()


class DuyetDoiTraSerializer(serializers.Serializer):
    khong_thu_hoi_hang = serializers.BooleanField(required=False, default=False)
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    ma_van_don_doi = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class TuChoiSerializer(serializers.Serializer):
    ly_do = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class KetQuaDongSerializer(serializers.Serializer):
    ma_dong = serializers.CharField(max_length=10)
    ket_qua = serializers.ChoiceField(choices=["DAT", "KHONG_DAT"])
    so_luong_dat = serializers.IntegerField(required=False, min_value=1)
    kho_nhap = serializers.ChoiceField(choices=["KHO_BAN", "KHO_LOI"], required=False)
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True)


class NhanHangSerializer(serializers.Serializer):
    ket_qua_dong = KetQuaDongSerializer(many=True, allow_empty=False)
    ghi_chu = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    ma_van_don_gui_lai = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class HoanTatDoiTraSerializer(serializers.Serializer):
    ma_van_don_doi = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class XuLyGiaoThatBaiSerializer(serializers.Serializer):
    ma_nguyen_nhan = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    huong_xu_ly = serializers.ChoiceField(choices=HuongXuLyGiao.choices)
    ghi_chu = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    phan_hoi_khach = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    ben_chiu_phi = serializers.ChoiceField(choices=["CUA_HANG", "KHACH_HANG"], required=False, default="CUA_HANG")
    khach_tu_choi = serializers.BooleanField(required=False, default=False)
    ngay_giao_lai = serializers.DateField(required=False, allow_null=True, default=None)
    ten_nguoi_nhan_moi = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    sdt_nguoi_nhan_moi = serializers.CharField(max_length=15, required=False, allow_blank=True, default="")
    dia_chi_giao_moi = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    hinh_thuc_giao = serializers.ChoiceField(choices=["XE_TAI", "SHIPPER", "DVVC"], required=False, allow_null=True, default=None)
    don_vi_van_chuyen = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    sdt_shipper = serializers.CharField(max_length=15, required=False, allow_blank=True, default="")
    ma_van_don = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")


class XacNhanHoanTienSerializer(serializers.Serializer):
    ma_giao_dich_hoan = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    so_tien = serializers.DecimalField(max_digits=15, decimal_places=0, required=False, allow_null=True, default=None)
    ly_do_dieu_chinh = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    phuong_thuc = serializers.ChoiceField(choices=["PHUONG_THUC_GOC", "CHUYEN_KHOAN"], required=False, allow_null=True, default=None)
    thong_tin_tai_khoan = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class HoanTienThatBaiSerializer(serializers.Serializer):
    ly_do = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class DieuChinhHoanTienSerializer(serializers.Serializer):
    so_tien = serializers.DecimalField(max_digits=15, decimal_places=0, min_value=1)
    ly_do = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class NguyenNhanGhiSerializer(serializers.Serializer):
    loai_xu_ly = serializers.ChoiceField(choices=LoaiXuLy.choices, required=False)
    ten_nguyen_nhan = serializers.CharField(max_length=100, required=False, allow_blank=True)
    mo_ta = serializers.CharField(max_length=255, required=False, allow_blank=True)
    thu_tu_hien_thi = serializers.IntegerField(min_value=0, required=False)
    bat_buoc_anh = serializers.BooleanField(required=False)
    bat_buoc_ghi_chu = serializers.BooleanField(required=False)
    loi_do_cua_hang = serializers.BooleanField(required=False)


class LocNgaySerializer(serializers.Serializer):
    tu_ngay = serializers.DateField(required=False)
    den_ngay = serializers.DateField(required=False)
    trang = serializers.IntegerField(required=False, min_value=1, default=1)


class TraCuuLichSuSerializer(LocNgaySerializer):
    tu_khoa = serializers.CharField(required=False, allow_blank=True, default="")
    loai = serializers.ChoiceField(choices=["HUY_DON", "GIAO_THAT_BAI", "DOI_TRA", "HOAN_TIEN"], required=False)
    trang_thai = serializers.CharField(required=False, allow_blank=True)
    ma_nguyen_nhan = serializers.CharField(required=False, allow_blank=True)


class ThongKeSerializer(serializers.Serializer):
    tu_ngay = serializers.DateField(required=False)
    den_ngay = serializers.DateField(required=False)
    loai_xu_ly = serializers.ChoiceField(choices=LoaiXuLy.choices, required=False)


# ==========================================================
# B. ĐẦU RA
# ==========================================================
class NguyenNhanSerializer(serializers.ModelSerializer):
    ten_loai_xu_ly = serializers.CharField(source="get_loai_xu_ly_display", read_only=True)
    so_lan_su_dung = serializers.SerializerMethodField()

    class Meta:
        model = NguyenNhan
        fields = ["ma_nguyen_nhan", "loai_xu_ly", "ten_loai_xu_ly", "ten_nguyen_nhan", "mo_ta",
                  "thu_tu_hien_thi", "bat_buoc_anh", "bat_buoc_ghi_chu", "loi_do_cua_hang", "dang_ap_dung",
                  "so_lan_su_dung"]

    def get_so_lan_su_dung(self, nn):
        from .services import DichVuNguyenNhan
        return DichVuNguyenNhan.so_lan_su_dung(nn)


class NguyenNhanChoKhachSerializer(serializers.ModelSerializer):
    """Khách chỉ cần thấy những gì để chọn nguyên nhân và biết có phải đính ảnh/ghi chú."""

    class Meta:
        model = NguyenNhan
        fields = ["ma_nguyen_nhan", "ten_nguyen_nhan", "mo_ta", "bat_buoc_anh", "bat_buoc_ghi_chu"]


class YeuCauHuySerializer(serializers.ModelSerializer):
    ten_trang_thai = serializers.CharField(source="get_trang_thai_display", read_only=True)
    ten_nguyen_nhan = serializers.CharField(source="nguyen_nhan.ten_nguyen_nhan", read_only=True)
    khach_hang = serializers.CharField(source="don_hang.khach_hang.ho_ten", read_only=True)
    trang_thai_don = serializers.CharField(source="don_hang.trang_thai", read_only=True)
    trang_thai_thanh_toan = serializers.CharField(source="don_hang.trang_thai_thanh_toan", read_only=True)
    qua_han_xu_ly = serializers.SerializerMethodField()

    class Meta:
        model = YeuCauHuy
        fields = ["ma_yc_huy", "don_hang", "khach_hang", "nguyen_nhan", "ten_nguyen_nhan", "ghi_chu_khach",
                  "trang_thai", "ten_trang_thai", "thoi_diem_gui", "thoi_diem_xu_ly", "ly_do_tu_choi",
                  "ghi_chu_noi_bo", "trang_thai_don", "trang_thai_thanh_toan", "qua_han_xu_ly"]

    def get_qua_han_xu_ly(self, yc):
        return DichVuHuyDon.la_qua_han(yc)


class YeuCauHuyChoKhachSerializer(YeuCauHuySerializer):
    class Meta(YeuCauHuySerializer.Meta):
        fields = ["ma_yc_huy", "don_hang", "nguyen_nhan", "ten_nguyen_nhan", "ghi_chu_khach", "trang_thai",
                  "ten_trang_thai", "thoi_diem_gui", "thoi_diem_xu_ly", "ly_do_tu_choi"]  # không có ghi chú nội bộ


class DongDoiTraSerializer(serializers.ModelSerializer):
    ten_san_pham = serializers.CharField(source="chi_tiet_don_hang.bien_the", read_only=True)
    don_gia = serializers.DecimalField(source="chi_tiet_don_hang.don_gia", max_digits=15, decimal_places=0, read_only=True)

    class Meta:
        model = DongDoiTra
        fields = ["ma_dong", "chi_tiet_don_hang", "ten_san_pham", "don_gia", "so_luong", "bien_the_doi",
                  "ket_qua_kiem_tra", "so_luong_dat", "kho_nhap", "ghi_chu_kiem_tra"]


class YeuCauDoiTraSerializer(serializers.ModelSerializer):
    ten_trang_thai = serializers.CharField(source="get_trang_thai_display", read_only=True)
    ten_hinh_thuc = serializers.CharField(source="get_hinh_thuc_display", read_only=True)
    ten_nguyen_nhan = serializers.CharField(source="nguyen_nhan.ten_nguyen_nhan", read_only=True)
    dong = DongDoiTraSerializer(many=True, read_only=True)
    anh_minh_chung = serializers.SerializerMethodField()

    class Meta:
        model = YeuCauDoiTra
        fields = ["ma_yc_doi_tra", "don_hang", "hinh_thuc", "ten_hinh_thuc", "nguyen_nhan", "ten_nguyen_nhan",
                  "mo_ta", "trang_thai", "ten_trang_thai", "thoi_diem_gui", "thoi_diem_xu_ly", "ly_do_tu_choi",
                  "ghi_chu_noi_bo", "khong_thu_hoi_hang", "han_gui_hang", "thoi_diem_nhan_hang",
                  "ben_chiu_phi_van_chuyen", "ma_van_don_doi", "ma_van_don_gui_lai", "chenh_lech_gia",
                  "thoi_diem_hoan_tat", "dong", "anh_minh_chung"]

    def get_anh_minh_chung(self, yc):
        return [a.tep.url for a in yc.anh_minh_chung.all()]


class YeuCauDoiTraChoKhachSerializer(YeuCauDoiTraSerializer):
    class Meta(YeuCauDoiTraSerializer.Meta):
        fields = [f for f in YeuCauDoiTraSerializer.Meta.fields if f != "ghi_chu_noi_bo"]


class XuLyGiaoThatBaiOutSerializer(serializers.ModelSerializer):
    ten_nguyen_nhan = serializers.CharField(source="nguyen_nhan.ten_nguyen_nhan", read_only=True)
    ten_huong_xu_ly = serializers.CharField(source="get_huong_xu_ly_display", read_only=True)

    class Meta:
        model = XuLyGiaoThatBai
        fields = ["ma_xu_ly", "don_hang", "giao_hang", "lan_giao", "nguyen_nhan", "ten_nguyen_nhan", "ghi_chu",
                  "phan_hoi_khach", "huong_xu_ly", "ten_huong_xu_ly", "ben_chiu_phi", "ngay_giao_lai_du_kien",
                  "ten_nguoi_nhan_moi", "sdt_nguoi_nhan_moi", "dia_chi_giao_moi", "thoi_diem", "da_nhap_kho",
                  "thoi_diem_nhap_kho"]


class HoanTienSerializer(serializers.ModelSerializer):
    ten_trang_thai = serializers.CharField(source="get_trang_thai_display", read_only=True)
    ten_nguon = serializers.CharField(source="get_nguon_display", read_only=True)
    tai_khoan_nhan = serializers.SerializerMethodField()  # luôn che bớt, không bao giờ trả bản đầy đủ

    class Meta:
        model = GiaoDichHoanTien
        fields = ["ma_hoan_tien", "don_hang", "nguon", "ten_nguon", "yeu_cau_huy", "yeu_cau_doi_tra",
                  "xu_ly_giao_that_bai", "giao_dich_goc", "la_dieu_chinh", "so_tien_da_thanh_toan",
                  "so_tien_de_xuat", "so_tien_hoan", "ly_do_dieu_chinh", "phuong_thuc_hoan", "tai_khoan_nhan",
                  "ma_giao_dich_hoan", "trang_thai", "ten_trang_thai", "ly_do_that_bai", "thoi_diem_tao",
                  "thoi_diem_hoan"]

    def get_tai_khoan_nhan(self, khoan):
        return tai_khoan_nhan_da_che(khoan)


class MocTimelineSerializer(serializers.ModelSerializer):
    """Dành cho nhân viên: đầy đủ, có người thực hiện và ghi chú nội bộ."""
    nhan_vien_ho_ten = serializers.CharField(source="nhan_vien.ho_ten", read_only=True, default=None)

    class Meta:
        model = LichSuHauMai
        fields = ["ma_lich_su", "moc", "trang_thai", "tac_nhan", "nhan_vien", "nhan_vien_ho_ten", "thoi_diem",
                  "ghi_chu", "ghi_chu_noi_bo"]


class MocTimelineChoKhachSerializer(serializers.ModelSerializer):
    """Dành cho khách: chỉ loại người thực hiện (khách hàng/nhân viên/hệ thống), không thấy ghi chú nội bộ."""
    ten_tac_nhan = serializers.SerializerMethodField()

    class Meta:
        model = LichSuHauMai
        fields = ["ma_lich_su", "moc", "trang_thai", "tac_nhan", "ten_tac_nhan", "thoi_diem", "ghi_chu"]

    def get_ten_tac_nhan(self, moc):
        return {"KHACH_HANG": "Khách hàng", "NHAN_VIEN": "Nhân viên", "HE_THONG": "Hệ thống"}.get(moc.tac_nhan, moc.tac_nhan)
