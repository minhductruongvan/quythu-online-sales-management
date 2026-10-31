# File: backend/orders/migrations/0002_seed_danh_muc.py
# Nạp sẵn dữ liệu danh mục của M3:
# - 34 tỉnh/thành (đơn vị hành chính sau sáp nhập 2025) và phí giao hàng
# - 2 phương thức thanh toán
# Cách viết theo customers/migrations/0003_seed_customer_types.py của M1.

from django.db import migrations

# ---------------------------------------------------------
# Bảng phí giả lập, nơi gửi hàng là Đà Nẵng (nhóm chốt 31/10/2026)
# ---------------------------------------------------------
TINH_GUI_HANG = "Đà Nẵng"
PHI_CUNG_TINH = 30000
PHI_NOI_MIEN = 35000   # cùng miền Trung với Đà Nẵng
PHI_LIEN_MIEN = 40000  # miền Bắc, miền Nam

# (mã, tên, vùng) – xếp từ Bắc vào Nam
DANH_SACH_TINH = [
    ("TT001", "Hà Nội", "BAC"),
    ("TT002", "Hải Phòng", "BAC"),
    ("TT003", "Quảng Ninh", "BAC"),
    ("TT004", "Cao Bằng", "BAC"),
    ("TT005", "Lạng Sơn", "BAC"),
    ("TT006", "Lai Châu", "BAC"),
    ("TT007", "Điện Biên", "BAC"),
    ("TT008", "Sơn La", "BAC"),
    ("TT009", "Tuyên Quang", "BAC"),
    ("TT010", "Lào Cai", "BAC"),
    ("TT011", "Thái Nguyên", "BAC"),
    ("TT012", "Phú Thọ", "BAC"),
    ("TT013", "Bắc Ninh", "BAC"),
    ("TT014", "Hưng Yên", "BAC"),
    ("TT015", "Ninh Bình", "BAC"),
    ("TT016", "Thanh Hóa", "TRUNG"),
    ("TT017", "Nghệ An", "TRUNG"),
    ("TT018", "Hà Tĩnh", "TRUNG"),
    ("TT019", "Quảng Trị", "TRUNG"),
    ("TT020", "Huế", "TRUNG"),
    ("TT021", "Đà Nẵng", "TRUNG"),
    ("TT022", "Quảng Ngãi", "TRUNG"),
    ("TT023", "Gia Lai", "TRUNG"),
    ("TT024", "Đắk Lắk", "TRUNG"),
    ("TT025", "Khánh Hòa", "TRUNG"),
    ("TT026", "Lâm Đồng", "TRUNG"),
    ("TT027", "TP. Hồ Chí Minh", "NAM"),
    ("TT028", "Đồng Nai", "NAM"),
    ("TT029", "Tây Ninh", "NAM"),
    ("TT030", "Cần Thơ", "NAM"),
    ("TT031", "Vĩnh Long", "NAM"),
    ("TT032", "Đồng Tháp", "NAM"),
    ("TT033", "Cà Mau", "NAM"),
    ("TT034", "An Giang", "NAM"),
]


def tinh_phi(ten_tinh, vung_mien):
    """Quy tắc 3 mức: cùng tỉnh / cùng miền Trung / khác miền."""
    if ten_tinh == TINH_GUI_HANG:
        return PHI_CUNG_TINH
    if vung_mien == "TRUNG":
        return PHI_NOI_MIEN
    return PHI_LIEN_MIEN


def seed_danh_muc(apps, schema_editor):
    # Lấy model "lịch sử" tại thời điểm migration này, không import trực tiếp
    TinhThanh = apps.get_model("orders", "TinhThanh")
    PhuongThucThanhToan = apps.get_model("orders", "PhuongThucThanhToan")

    for ma_tinh, ten_tinh, vung_mien in DANH_SACH_TINH:
        TinhThanh.objects.update_or_create(
            ma_tinh=ma_tinh,
            defaults={
                "ten_tinh": ten_tinh,
                "vung_mien": vung_mien,
                "phi_van_chuyen": tinh_phi(ten_tinh, vung_mien),
                "dang_hoat_dong": True,
            },
        )

    PhuongThucThanhToan.objects.update_or_create(
        ma_pttt="PT001",
        defaults={
            "ten_pttt": "Chuyển khoản",
            "thong_tin_tai_khoan": "VCB 0041000888999 - Banh Dua Quy Thu",
            "dang_kich_hoat": True,
            "ghi_chu_huong_dan": "Thanh toán qua mã QR sau khi đơn được xác nhận; nội dung ghi mã đơn hàng",
        },
    )

    PhuongThucThanhToan.objects.update_or_create(
        ma_pttt="PT002",
        defaults={
            "ten_pttt": "COD",
            "thong_tin_tai_khoan": None,
            "dang_kich_hoat": True,
            "ghi_chu_huong_dan": "Thanh toán tiền mặt cho người giao hàng khi nhận hàng",
        },
    )


def xoa_danh_muc(apps, schema_editor):
    # Chạy khi lùi migration (python manage.py migrate orders 0001)
    TinhThanh = apps.get_model("orders", "TinhThanh")
    PhuongThucThanhToan = apps.get_model("orders", "PhuongThucThanhToan")

    TinhThanh.objects.filter(ma_tinh__in=[t[0] for t in DANH_SACH_TINH]).delete()
    PhuongThucThanhToan.objects.filter(ma_pttt__in=["PT001", "PT002"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_danh_muc, xoa_danh_muc),
    ]