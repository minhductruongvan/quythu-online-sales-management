from django.db import transaction

from .models import TaiKhoan, KhachHang, LichSuKhachHang


class LoiNghiepVuTaiKhoan(Exception):
    """Lỗi phát sinh khi vi phạm quy tắc nghiệp vụ tài khoản."""
    pass

class LoiQuyenTaiKhoan(LoiNghiepVuTaiKhoan):
    """Lỗi khi người dùng không có quyền thực hiện nghiệp vụ tài khoản."""
    pass

class DichVuTrangThaiTaiKhoan:
    HANH_DONG_LOCK = "LOCK"
    HANH_DONG_UNLOCK = "UNLOCK"

    @staticmethod
    def lay_tai_khoan_khach_hang(khach_hang):
        if khach_hang.tai_khoan is None:
            raise LoiQuyenTaiKhoan(
                "Khách hàng này chưa có tài khoản để khóa hoặc mở khóa."
            )

        return khach_hang.tai_khoan

    @staticmethod
    def kiem_tra_chuyen_trang_thai(tai_khoan, hanh_dong):
        if hanh_dong == DichVuTrangThaiTaiKhoan.HANH_DONG_LOCK:
            if tai_khoan.trang_thai == TaiKhoan.TrangThai.LOCKED:
                raise LoiNghiepVuTaiKhoan(
                    "Tài khoản đã bị khóa trước đó."
                )

            return TaiKhoan.TrangThai.LOCKED

        if hanh_dong == DichVuTrangThaiTaiKhoan.HANH_DONG_UNLOCK:
            if tai_khoan.trang_thai == TaiKhoan.TrangThai.ACTIVE:
                raise LoiNghiepVuTaiKhoan(
                    "Tài khoản hiện đang hoạt động."
                )

            return TaiKhoan.TrangThai.ACTIVE

        raise LoiNghiepVuTaiKhoan(
            "Hành động thay đổi trạng thái tài khoản không hợp lệ."
        )

    @staticmethod
    @transaction.atomic
    def thay_doi_trang_thai(khach_hang, nguoi_thuc_hien, hanh_dong):
        tai_khoan = DichVuTrangThaiTaiKhoan.lay_tai_khoan_khach_hang(
            khach_hang
        )

        DichVuTrangThaiTaiKhoan.kiem_tra_quyen_thao_tac(
            nguoi_thuc_hien,
            tai_khoan,
        )

        trang_thai_cu = tai_khoan.trang_thai

        trang_thai_moi = (
            DichVuTrangThaiTaiKhoan.kiem_tra_chuyen_trang_thai(
                tai_khoan,
                hanh_dong,
            )
        )

        # Đồng bộ trạng thái nghiệp vụ với trạng thái đăng nhập Django
        tai_khoan.trang_thai = trang_thai_moi
        tai_khoan.is_active = (
            trang_thai_moi == TaiKhoan.TrangThai.ACTIVE
        )

        tai_khoan.save(
            update_fields=[
                "trang_thai",
                "is_active",
            ]
        )

        # Xác định loại lịch sử
        if hanh_dong == DichVuTrangThaiTaiKhoan.HANH_DONG_LOCK:
            loai_thay_doi = (
                LichSuKhachHang.LoaiThayDoi.ACCOUNT_LOCK
            )
        else:
            loai_thay_doi = (
                LichSuKhachHang.LoaiThayDoi.ACCOUNT_UNLOCK
            )

        # Sinh mã lịch sử
        so_thu_tu = LichSuKhachHang.objects.count() + 1

        while True:
            ma_lich_su = f"LS{so_thu_tu:03d}"

            if not LichSuKhachHang.objects.filter(
                ma_lich_su=ma_lich_su
            ).exists():
                break

            so_thu_tu += 1

        LichSuKhachHang.objects.create(
            ma_lich_su=ma_lich_su,
            khach_hang=khach_hang,
            nguoi_thuc_hien=nguoi_thuc_hien,
            loai_thay_doi=loai_thay_doi,
            noi_dung_cu=trang_thai_cu,
            noi_dung_moi=trang_thai_moi,
        )

        return tai_khoan

    @staticmethod
    def kiem_tra_quyen_thao_tac(nguoi_thuc_hien, tai_khoan_muc_tieu):
        if nguoi_thuc_hien.vai_tro not in [
            TaiKhoan.VaiTro.EMPLOYEE,
            TaiKhoan.VaiTro.MANAGER,
        ]:
            raise LoiQuyenTaiKhoan(
                "Bạn không có quyền khóa hoặc mở khóa tài khoản khách hàng."
            )

        if tai_khoan_muc_tieu.vai_tro != TaiKhoan.VaiTro.CUSTOMER:
            raise LoiQuyenTaiKhoan(
                "Chức năng này chỉ áp dụng cho tài khoản khách hàng."
            )

        if nguoi_thuc_hien.pk == tai_khoan_muc_tieu.pk:
            raise LoiQuyenTaiKhoan(
                "Không thể thay đổi trạng thái của chính tài khoản đang đăng nhập."
            )

class DichVuLichSuHoSo:
    CAC_TRUONG_THEO_DOI = {
        "ho_ten": "Họ tên",
        "email": "Email",
        "so_dien_thoai": "Số điện thoại",
    }
    @staticmethod
    def lay_du_lieu_hien_tai(khach_hang):
        return {
            "ho_ten": khach_hang.ho_ten,
            "email": (
                khach_hang.tai_khoan.email
                if khach_hang.tai_khoan is not None
                else None
            ),
            "so_dien_thoai": khach_hang.so_dien_thoai,
        }
    @staticmethod
    def tim_cac_thay_doi(du_lieu_cu, du_lieu_moi):
        cac_thay_doi = []

        for ten_truong, ten_hien_thi in DichVuLichSuHoSo.CAC_TRUONG_THEO_DOI.items():
            gia_tri_cu = du_lieu_cu.get(ten_truong)
            gia_tri_moi = du_lieu_moi.get(ten_truong)

            if gia_tri_cu != gia_tri_moi:
                cac_thay_doi.append({
                    "truong": ten_truong,
                    "ten_hien_thi": ten_hien_thi,
                    "gia_tri_cu": gia_tri_cu,
                    "gia_tri_moi": gia_tri_moi,
                })

        return cac_thay_doi
    @staticmethod
    def tao_noi_dung_thay_doi(cac_thay_doi):
        noi_dung_cu = []
        noi_dung_moi = []

        for thay_doi in cac_thay_doi:
            ten_hien_thi = thay_doi["ten_hien_thi"]

            gia_tri_cu = thay_doi["gia_tri_cu"]
            gia_tri_moi = thay_doi["gia_tri_moi"]

            noi_dung_cu.append(
                f"{ten_hien_thi}: {gia_tri_cu if gia_tri_cu not in [None, ''] else '(trống)'}"
            )

            noi_dung_moi.append(
                f"{ten_hien_thi}: {gia_tri_moi if gia_tri_moi not in [None, ''] else '(trống)'}"
            )

        return "; ".join(noi_dung_cu), "; ".join(noi_dung_moi)

    @staticmethod
    def tao_ma_lich_su():
        so_thu_tu = LichSuKhachHang.objects.count() + 1

        while True:
            ma_lich_su = f"LS{so_thu_tu:03d}"

            if not LichSuKhachHang.objects.filter(
                ma_lich_su=ma_lich_su
            ).exists():
                return ma_lich_su

            so_thu_tu += 1

    @staticmethod
    def ghi_lich_su_cap_nhat(
        khach_hang,
        nguoi_thuc_hien,
        du_lieu_cu,
        du_lieu_moi,
    ):
        cac_thay_doi = DichVuLichSuHoSo.tim_cac_thay_doi(
            du_lieu_cu,
            du_lieu_moi,
        )

        if not cac_thay_doi:
            return None

        noi_dung_cu, noi_dung_moi = (
            DichVuLichSuHoSo.tao_noi_dung_thay_doi(
                cac_thay_doi
            )
        )

        return LichSuKhachHang.objects.create(
            ma_lich_su=DichVuLichSuHoSo.tao_ma_lich_su(),
            khach_hang=khach_hang,
            nguoi_thuc_hien=nguoi_thuc_hien,
            loai_thay_doi=LichSuKhachHang.LoaiThayDoi.PROFILE_UPDATE,
            noi_dung_cu=noi_dung_cu,
            noi_dung_moi=noi_dung_moi,
        )