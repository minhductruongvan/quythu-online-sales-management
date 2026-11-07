from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from after_sales.models import YeuCauHuy
from after_sales.services import DichVuHuyDon
from customers.models import DiaChiKH, KhachHang, LoaiKhachHang, NhanVien
from orders.models import (
    ChiTietDonHang,
    DonHang,
    GiaoDichThanhToan,
    GiaoHang,
    HinhThucGiao,
    KetQuaGiao,
    KetQuaKiemTra,
    LichSuTrangThaiDonHang,
    LoaiGia,
    PhuongThucThanhToan,
    TacNhan,
    TinhThanh,
    TrangThaiDonHang,
    TrangThaiThanhToan,
)
from products.models import BienTheSanPham


CUSTOMERS = (
    ("TSTKH001", "Nguyễn Minh Anh", "minhanh@example.test", "0905000001", "LKH001", "TT021"),
    ("TSTKH002", "Trần Quốc Bảo", "quocbao@example.test", "0905000002", "LKH002", "TT001"),
    ("TSTKH003", "Lê Thu Hà", "thuha@example.test", "0905000003", "LKH001", "TT027"),
    ("TSTKH004", "Phạm Gia Huy", "giahuy@example.test", "0905000004", "LKH001", "TT021"),
    ("TSTKH005", "Võ Ngọc Lan", "ngoclan@example.test", "0905000005", "LKH002", "TT027"),
    ("TSTKH006", "Đặng Hoàng Long", "hoanglong@example.test", "0905000006", "LKH001", "TT001"),
    ("TSTKH007", "Bùi Khánh Linh", "khanhlinh@example.test", "0905000007", "LKH001", "TT021"),
    ("TSTKH008", "Hoàng Đức Nam", "ducnam@example.test", "0905000008", "LKH002", "TT027"),
)

ORDERS = (
    (TrangThaiDonHang.CHO_XAC_NHAN, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.CHO_THANH_TOAN, PhuongThucThanhToan.MA_CHUYEN_KHOAN, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.DANG_CHUAN_BI, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.CHO_BO_SUNG, PhuongThucThanhToan.MA_CHUYEN_KHOAN, TrangThaiThanhToan.DA_THANH_TOAN),
    (TrangThaiDonHang.SAN_SANG_GIAO, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.DANG_GIAO, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.GIAO_THANH_CONG, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.DA_THANH_TOAN),
    (TrangThaiDonHang.HOAN_THANH, PhuongThucThanhToan.MA_CHUYEN_KHOAN, TrangThaiThanhToan.DA_THANH_TOAN),
    (TrangThaiDonHang.DA_HUY, PhuongThucThanhToan.MA_CHUYEN_KHOAN, TrangThaiThanhToan.CHUA_THANH_TOAN),
    (TrangThaiDonHang.CHO_XAC_NHAN, PhuongThucThanhToan.MA_COD, TrangThaiThanhToan.CHUA_THANH_TOAN),
)


class Command(BaseCommand):
    help = "Create repeatable sample customers, addresses, orders and transactions."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo sales data may only be seeded when DEBUG=True.")

        variants = list(
            BienTheSanPham.objects.filter(
                trang_thai="ACTIVE", san_pham__trang_thai="ACTIVE"
            ).order_by("ma_bien_the")
        )
        if not variants:
            raise CommandError("Run seed_demo_catalog before creating demo sales data.")

        retail_type = LoaiKhachHang.objects.get(ma_loai_kh="LKH001")
        wholesale_type = LoaiKhachHang.objects.get(ma_loai_kh="LKH002")
        payments = {
            method.ma_pttt: method
            for method in PhuongThucThanhToan.objects.filter(
                ma_pttt__in=[
                    PhuongThucThanhToan.MA_COD,
                    PhuongThucThanhToan.MA_CHUYEN_KHOAN,
                ]
            )
        }
        cities = {city.ma_tinh: city for city in TinhThanh.objects.filter(
            ma_tinh__in={customer[5] for customer in CUSTOMERS}
        )}
        staff = NhanVien.objects.filter(
            tai_khoan__email="nhanvien@gmail.com"
        ).first()

        customers = []
        for code, name, email, phone, type_code, city_code in CUSTOMERS:
            customer, _ = KhachHang.objects.get_or_create(
                ma_kh=code,
                defaults={
                    "loai_khach_hang": wholesale_type if type_code == "LKH002" else retail_type,
                    "ho_ten": name,
                    "email": email,
                    "so_dien_thoai": phone,
                    "trang_thai": KhachHang.TrangThai.ACTIVE,
                },
            )
            address, _ = DiaChiKH.objects.get_or_create(
                ma_dia_chi=f"TSTDC{code[-3:]}",
                defaults={
                    "khach_hang": customer,
                    "ten_nguoi_nhan": name,
                    "so_dien_thoai": phone,
                    "dia_chi_chi_tiet": f"{10 + int(code[-1])} Đường Mẫu",
                    "phuong_xa": "Phường Hải Châu",
                    "quan_huyen": "Quận Hải Châu" if city_code == "TT021" else "",
                    "tinh_thanh": cities[city_code].ten_tinh,
                    "mac_dinh": True,
                },
            )
            customers.append((customer, address, cities[city_code]))

        demo_customer = (
            KhachHang.objects.select_related("loai_khach_hang").filter(
                tai_khoan__email="khachhang@gmail.com"
            ).first()
        )
        if demo_customer:
            demo_city = cities["TT021"]
            demo_address, _ = DiaChiKH.objects.get_or_create(
                ma_dia_chi="TSTDC009",
                defaults={
                    "khach_hang": demo_customer,
                    "ten_nguoi_nhan": demo_customer.ho_ten,
                    "so_dien_thoai": demo_customer.so_dien_thoai or "0905000009",
                    "dia_chi_chi_tiet": "09 Đường Mẫu",
                    "phuong_xa": "Phường Hải Châu",
                    "quan_huyen": "Quận Hải Châu",
                    "tinh_thanh": demo_city.ten_tinh,
                    "mac_dinh": True,
                },
            )
            customers.insert(0, (demo_customer, demo_address, demo_city))

        now = timezone.now()
        for index, (status, payment_code, payment_status) in enumerate(ORDERS, start=1):
            customer, address, city = customers[(index - 1) % len(customers)]
            method = payments[payment_code]
            created_at = now - timedelta(days=(index - 1) * 3, hours=index)
            variant = variants[(index - 1) % len(variants)]
            wholesale = customer.loai_khach_hang_id == wholesale_type.ma_loai_kh
            quantity = (
                max(variant.so_luong_toi_thieu_si, 10)
                if wholesale
                else 1 + (index % 3)
            )
            unit_price = (
                variant.gia_ban_si
                if wholesale and variant.gia_ban_si is not None
                else variant.gia_ban_le
            )
            subtotal = unit_price * quantity
            order_code = f"TSTDH{index:03d}"
            confirmed_at = created_at + timedelta(minutes=35)
            is_confirmed = status not in {
                TrangThaiDonHang.CHO_XAC_NHAN,
                TrangThaiDonHang.DA_HUY,
            }
            order, _ = DonHang.objects.get_or_create(
                ma_dh=order_code,
                defaults={
                    "khach_hang": customer,
                    "loai_khach_hang_ap_dung": customer.loai_khach_hang,
                    "ho_ten_nguoi_nhan": address.ten_nguoi_nhan,
                    "sdt_nguoi_nhan": address.so_dien_thoai,
                    "dia_chi_giao_hang": (
                        f"{address.dia_chi_chi_tiet}, {address.tinh_thanh}"
                    ),
                    "tinh_thanh": city,
                    "tong_tien_hang": subtotal,
                    "phi_van_chuyen": city.phi_van_chuyen,
                    "tong_thanh_toan": subtotal + city.phi_van_chuyen,
                    "phuong_thuc_thanh_toan": method,
                    "trang_thai_thanh_toan": payment_status,
                    "trang_thai": status,
                    "ghi_chu": "Dữ liệu mẫu để thử luồng xử lý đơn.",
                    "ngay_dat": created_at,
                    "nhan_vien_xac_nhan": staff if is_confirmed else None,
                    "thoi_diem_xac_nhan": confirmed_at if is_confirmed else None,
                    "thoi_diem_bat_dau_chuan_bi": (
                        confirmed_at + timedelta(minutes=20)
                        if status in {
                            TrangThaiDonHang.DANG_CHUAN_BI,
                            TrangThaiDonHang.CHO_BO_SUNG,
                            TrangThaiDonHang.SAN_SANG_GIAO,
                            TrangThaiDonHang.DANG_GIAO,
                            TrangThaiDonHang.GIAO_THANH_CONG,
                            TrangThaiDonHang.HOAN_THANH,
                        }
                        else None
                    ),
                    "thoi_diem_hen_cung_cap": (
                        now + timedelta(days=2)
                        if status == TrangThaiDonHang.CHO_BO_SUNG
                        else None
                    ),
                    "trang_thai_truoc_cho_bo_sung": (
                        TrangThaiDonHang.DANG_CHUAN_BI
                        if status == TrangThaiDonHang.CHO_BO_SUNG
                        else None
                    ),
                    "thoi_diem_ban_giao": (
                        created_at + timedelta(days=1)
                        if status in {
                            TrangThaiDonHang.DANG_GIAO,
                            TrangThaiDonHang.GIAO_THANH_CONG,
                            TrangThaiDonHang.HOAN_THANH,
                        }
                        else None
                    ),
                    "thoi_diem_giao_thanh_cong": (
                        created_at + timedelta(days=2)
                        if status in {
                            TrangThaiDonHang.GIAO_THANH_CONG,
                            TrangThaiDonHang.HOAN_THANH,
                        }
                        else None
                    ),
                    "thoi_diem_xac_nhan_nhan_hang": (
                        created_at + timedelta(days=3)
                        if status == TrangThaiDonHang.HOAN_THANH
                        else None
                    ),
                    "thoi_diem_hoan_thanh": (
                        created_at + timedelta(days=3)
                        if status == TrangThaiDonHang.HOAN_THANH
                        else None
                    ),
                },
            )
            detail, _ = ChiTietDonHang.objects.get_or_create(
                ma_ctdh=f"TSTCT{index:03d}",
                defaults={
                    "don_hang": order,
                    "bien_the": variant,
                    "so_luong": quantity,
                    "loai_gia_ap_dung": LoaiGia.GIA_SI if wholesale else LoaiGia.GIA_LE,
                    "don_gia": unit_price,
                    "thanh_tien": subtotal,
                    "ket_qua_kiem_tra": (
                        KetQuaKiemTra.THIEU
                        if status == TrangThaiDonHang.CHO_BO_SUNG
                        else KetQuaKiemTra.CHUA_KIEM_TRA
                    ),
                    "so_luong_thieu": 1 if status == TrangThaiDonHang.CHO_BO_SUNG else 0,
                },
            )
            del detail

            GiaoDichThanhToan.objects.get_or_create(
                ma_giao_dich=f"TSTGD{index:03d}",
                defaults={
                    "don_hang": order,
                    "phuong_thuc": method,
                    "so_tien_phai_thu": order.tong_thanh_toan,
                    "so_tien_thuc_nhan": (
                        order.tong_thanh_toan
                        if payment_status == TrangThaiThanhToan.DA_THANH_TOAN
                        else None
                    ),
                    "trang_thai": payment_status,
                    "ma_giao_dich_ngan_hang": (
                        f"QTDEMO{index:03d}"
                        if payment_code == PhuongThucThanhToan.MA_CHUYEN_KHOAN
                        and payment_status == TrangThaiThanhToan.DA_THANH_TOAN
                        else None
                    ),
                    "thoi_diem_tao": created_at,
                    "thoi_diem_thanh_toan": (
                        created_at + timedelta(days=2)
                        if payment_status == TrangThaiThanhToan.DA_THANH_TOAN
                        else None
                    ),
                    "nhan_vien_ghi_nhan": (
                        staff
                        if payment_status == TrangThaiThanhToan.DA_THANH_TOAN
                        and payment_code == PhuongThucThanhToan.MA_COD
                        else None
                    ),
                    "ghi_chu": "Giao dịch mẫu.",
                },
            )

            LichSuTrangThaiDonHang.objects.get_or_create(
                ma_lstt=f"TSTLS{index:03d}A",
                defaults={
                    "don_hang": order,
                    "trang_thai": TrangThaiDonHang.CHO_XAC_NHAN,
                    "thoi_diem": created_at,
                    "tac_nhan": TacNhan.KHACH_HANG,
                    "ghi_chu": "Khách hàng tạo đơn.",
                },
            )
            if status != TrangThaiDonHang.CHO_XAC_NHAN:
                LichSuTrangThaiDonHang.objects.get_or_create(
                    ma_lstt=f"TSTLS{index:03d}B",
                    defaults={
                        "don_hang": order,
                        "trang_thai_cu": TrangThaiDonHang.CHO_XAC_NHAN,
                        "trang_thai": status,
                        "thoi_diem": confirmed_at + timedelta(minutes=30),
                        "tac_nhan": TacNhan.NHAN_VIEN,
                        "nhan_vien": staff,
                        "ghi_chu": "Cập nhật trạng thái mẫu để thử giao diện.",
                    },
                )

            if status in {
                TrangThaiDonHang.DANG_GIAO,
                TrangThaiDonHang.GIAO_THANH_CONG,
                TrangThaiDonHang.HOAN_THANH,
            }:
                GiaoHang.objects.get_or_create(
                    ma_giao_hang=f"TSTGH{index:03d}",
                    defaults={
                        "don_hang": order,
                        "lan_giao": 1,
                        "hinh_thuc_giao": (
                            HinhThucGiao.SHIPPER if index % 2 else HinhThucGiao.DVVC
                        ),
                        "don_vi_van_chuyen": (
                            "Shipper Quý Thu" if index % 2 else "Vận chuyển mẫu"
                        ),
                        "sdt_shipper": "0905999999",
                        "ma_van_don": f"QTDEMO-{index:03d}",
                        "thoi_diem_ban_giao": created_at + timedelta(days=1),
                        "ket_qua_giao": (
                            KetQuaGiao.DANG_GIAO
                            if status == TrangThaiDonHang.DANG_GIAO
                            else KetQuaGiao.THANH_CONG
                        ),
                        "thoi_diem_giao_xong": (
                            created_at + timedelta(days=2)
                            if status != TrangThaiDonHang.DANG_GIAO
                            else None
                        ),
                        "nhan_vien_xac_nhan": staff,
                    },
                )

        customer_demo_order = DonHang.objects.filter(
            ma_dh="TSTDH010",
            khach_hang__tai_khoan__email="khachhang@gmail.com",
        ).first()
        if (
            customer_demo_order
            and not YeuCauHuy.objects.filter(don_hang=customer_demo_order).exists()
        ):
            DichVuHuyDon.gui_yeu_cau(
                customer_demo_order.ma_dh,
                customer_demo_order.khach_hang,
                "NN001",
                "Yêu cầu mẫu để thử chức năng chăm sóc sau mua.",
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Demo sales data ready: "
                f"{len(CUSTOMERS)} sample customers, {len(ORDERS)} orders across "
                f"{len({order[0] for order in ORDERS})} processing states."
            )
        )
