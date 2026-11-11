# File: backend/after_sales/views.py
# Module 4 – View của API hậu mãi. Mỗi view chỉ làm 4 việc, theo khuôn của M1 và M3:
#   1. Lấy khách hàng / nhân viên từ tài khoản đang đăng nhập.
#   2. Đưa dữ liệu gửi lên qua serializer để kiểm tra định dạng.
#   3. Gọi hàm trong services.py (nghiệp vụ nằm hết ở đó).
#   4. Trả Response {"message": ..., "data": ...} kèm mã trạng thái HTTP.

from functools import wraps

from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.models import TaiKhoan
from orders.models import DonHang
from orders.permissions import NhanVienCoHoSo
from orders.services import LoiNghiepVuDonHang, LoiQuyenDonHang

from . import serializers as sr
from .models import LoaiXuLy, LoaiYeuCau
from .permissions import (
    KhachHangHauMai,
    KhachHoacNhanVienXemLichSu,
    NhanVienHauMai,
    QuyenHauMai,
)
from .services import (
    DichVuDoiTra,
    DichVuGiaoThatBai,
    DichVuHoanTien,
    DichVuHuyDon,
    DichVuLichSu,
    DichVuNguyenNhan,
    DichVuThongBao,
    DichVuThongKe,
    LoiNghiepVuHauMai,
    LoiQuyenHauMai,
    SO_LAN_GIAO_TOI_DA,
)


# ==========================================================
# Hàm dùng chung
# ==========================================================
def bat_loi(ham):
    """Đổi lỗi nghiệp vụ do services.py raise thành Response: 403 nếu đụng dữ liệu không phải của mình, 400 nếu vi phạm quy tắc."""
    @wraps(ham)
    def boc(self, request, *args, **kwargs):
        try:
            return ham(self, request, *args, **kwargs)
        except (LoiQuyenHauMai, LoiQuyenDonHang) as loi:
            return Response({"message": str(loi)}, status=status.HTTP_403_FORBIDDEN)
        except LoiNghiepVuDonHang as loi:
            return Response({"message": str(loi)}, status=status.HTTP_400_BAD_REQUEST)
    return boc


def du_lieu_sai(serializer):
    return Response({"message": "Dữ liệu không hợp lệ.", "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


def ok(message, data=None, ma=status.HTTP_200_OK):
    return Response({"message": message, "data": data}, status=ma)


def kiem_tra(serializer_class, du_lieu):
    s = serializer_class(data=du_lieu)
    s.is_valid()
    return s


def trang_du_lieu(trang, serializer_class, **ngu_canh):
    """Gói một Page của Django thành dict phân trang."""
    return {"tong_so": trang.paginator.count, "so_trang": trang.paginator.num_pages, "trang": trang.number,
            "ket_qua": serializer_class(trang.object_list, many=True, **ngu_canh).data}


def lay_nhan_vien(request):
    return request.user.nhan_vien


def lay_khach(request):
    return request.user.khach_hang


# ==========================================================
# PHÍA KHÁCH HÀNG – M4-UC01, M4-UC04
# ==========================================================
class NguyenNhanChoKhachView(APIView):
    """GET /api/after-sales/nguyen-nhan/?loai=HUY_DON|DOI_TRA – danh sách nguyên nhân đang áp dụng để chọn."""
    permission_classes = [KhachHangHauMai]

    def get(self, request):
        loai = request.query_params.get("loai")
        if loai not in (LoaiXuLy.HUY_DON, LoaiXuLy.DOI_TRA):
            return Response({"message": "Loại xử lý không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)
        ds = DichVuNguyenNhan.danh_sach(loai, dang_ap_dung=True)
        return ok("Lấy danh sách nguyên nhân thành công.", sr.NguyenNhanChoKhachSerializer(ds, many=True).data)


class GuiYeuCauHuyView(APIView):
    """POST /api/after-sales/huy/ – body {"ma_dh", "ma_nguyen_nhan", "ghi_chu"} (UC01)."""
    permission_classes = [KhachHangHauMai]

    @bat_loi
    def post(self, request):
        s = kiem_tra(sr.GuiYeuCauHuySerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        yc = DichVuHuyDon.gui_yeu_cau(
            d["ma_dh"], lay_khach(request), d["ma_nguyen_nhan"], d["ghi_chu"],
            d["so_tai_khoan"], d["ten_nguoi_nhan_tien"], d["ngan_hang_nhan"],
        )
        return ok("Gửi yêu cầu hủy đơn thành công.", sr.YeuCauHuyChoKhachSerializer(yc).data, status.HTTP_201_CREATED)


class ThuHoiHuyView(APIView):
    """POST /api/after-sales/huy/<ma_yc_huy>/thu-hoi/ (UC01 A1)."""
    permission_classes = [KhachHangHauMai]

    @bat_loi
    def post(self, request, ma_yc_huy):
        yc = DichVuHuyDon.thu_hoi(ma_yc_huy, lay_khach(request))
        return ok("Đã thu hồi yêu cầu hủy.", sr.YeuCauHuyChoKhachSerializer(yc).data)


class DongDoiTraKhachView(APIView):
    """GET /api/after-sales/doi-tra/dong/<ma_dh>/ – các dòng còn có thể đổi/trả (UC04 bước 1–2)."""
    permission_classes = [KhachHangHauMai]

    @bat_loi
    def get(self, request, ma_dh):
        from .services import lay_don_cua_khach
        from products.models import BienTheSanPham

        don = lay_don_cua_khach(ma_dh, lay_khach(request))
        DichVuDoiTra.kiem_tra_thoi_han(don)
        dong = []
        for ct, con_lai in DichVuDoiTra.cac_dong_du_dieu_kien(don):
            variants = BienTheSanPham.objects.filter(
                san_pham=ct.bien_the.san_pham,
                trang_thai="ACTIVE",
            ).order_by("huong_vi", "quy_cach")
            dong.append({
                "ma_ctdh": ct.ma_ctdh,
                "ten_san_pham": str(ct.bien_the),
                "so_luong_da_mua": ct.so_luong,
                "so_luong_con_lai": con_lai,
                "bien_the_thay_the": [
                    {
                        "ma_bien_the": variant.ma_bien_the,
                        "ten_bien_the": str(variant),
                    }
                    for variant in variants
                ],
            })
        return ok("Lấy danh sách sản phẩm thành công.", dong)


class GuiYeuCauDoiTraView(APIView):
    """POST /api/after-sales/doi-tra/ (UC04). Gửi JSON hoặc multipart (ảnh trong trường "anh", tối đa 5 ảnh)."""
    permission_classes = [KhachHangHauMai]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @bat_loi
    def post(self, request):
        s = kiem_tra(sr.GuiYeuCauDoiTraSerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        yc = DichVuDoiTra.gui_yeu_cau(
            d["ma_dh"], lay_khach(request), d["hinh_thuc"], d["ma_nguyen_nhan"], d["mo_ta"], d["dong"],
            anh=request.FILES.getlist("anh"), so_tai_khoan=d["so_tai_khoan"],
            ten_nguoi_nhan_tien=d["ten_nguoi_nhan_tien"], ngan_hang_nhan=d["ngan_hang_nhan"])
        return ok("Gửi yêu cầu đổi/trả thành công.", sr.YeuCauDoiTraChoKhachSerializer(yc).data, status.HTTP_201_CREATED)


class ThuHoiDoiTraView(APIView):
    """POST /api/after-sales/doi-tra/<ma_yc_doi_tra>/thu-hoi/ (UC04 A2)."""
    permission_classes = [KhachHangHauMai]

    @bat_loi
    def post(self, request, ma_yc_doi_tra):
        yc = DichVuDoiTra.thu_hoi(ma_yc_doi_tra, lay_khach(request))
        return ok("Đã thu hồi yêu cầu đổi/trả.", sr.YeuCauDoiTraChoKhachSerializer(yc).data)


class ThongBaoKhachView(APIView):
    """GET /api/after-sales/thong-bao/?chua_doc=1; POST /api/after-sales/thong-bao/<ma>/da-doc/ (M4-BR18)."""
    permission_classes = [KhachHangHauMai]

    def get(self, request):
        ds = DichVuThongBao.cua_khach(lay_khach(request), request.query_params.get("chua_doc") == "1")
        return ok("Lấy thông báo thành công.", [
            {"ma_thong_bao": t.ma_thong_bao, "ma_dh": t.don_hang_id, "tieu_de": t.tieu_de, "noi_dung": t.noi_dung,
             "da_doc": t.da_doc, "thoi_diem_gui": t.thoi_diem_gui} for t in ds[:50]])

    @bat_loi
    def post(self, request, ma_thong_bao):
        DichVuThongBao.danh_dau_da_doc(ma_thong_bao, lay_khach(request))
        return ok("Đã đánh dấu đã đọc.")


# ==========================================================
# TRA CỨU LỊCH SỬ VÀ TIMELINE – M4-UC09 (khách hàng và nhân viên)
# ==========================================================
class LichSuView(APIView):
    """GET /api/after-sales/lich-su/?tu_khoa=&loai=&trang_thai=&tu_ngay=&den_ngay=&ma_nguyen_nhan=&trang="""
    permission_classes = [KhachHoacNhanVienXemLichSu]

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.TraCuuLichSuSerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        la_khach = request.user.vai_tro == TaiKhoan.VaiTro.CUSTOMER
        trang = DichVuLichSu.tra_cuu(
            khach_hang=lay_khach(request) if la_khach else None, tu_khoa=d.get("tu_khoa", ""), loai=d.get("loai"),
            trang_thai=d.get("trang_thai"), tu_ngay=d.get("tu_ngay"), den_ngay=d.get("den_ngay"),
            ma_nguyen_nhan=d.get("ma_nguyen_nhan"), trang=d.get("trang", 1))
        du_lieu = {"tong_so": trang.paginator.count, "so_trang": trang.paginator.num_pages, "trang": trang.number,
                   "ket_qua": list(trang.object_list)}
        return ok("Không tìm thấy yêu cầu phù hợp." if not du_lieu["ket_qua"] else "Lấy lịch sử thành công.", du_lieu)


class TimelineView(APIView):
    """GET /api/after-sales/lich-su/<loai>/<ma_yeu_cau>/ – timeline đầy đủ các mốc xử lý."""
    permission_classes = [KhachHoacNhanVienXemLichSu]

    @bat_loi
    def get(self, request, loai, ma_yeu_cau):
        la_khach = request.user.vai_tro == TaiKhoan.VaiTro.CUSTOMER
        don, _, cac_moc, lien_quan = DichVuLichSu.timeline(
            loai, ma_yeu_cau, khach_hang=lay_khach(request) if la_khach else None)
        out = sr.MocTimelineChoKhachSerializer if la_khach else sr.MocTimelineSerializer  # BR12
        return ok("Lấy timeline thành công.", {
            "ma_dh": don.ma_dh, "loai_yeu_cau": loai, "ma_yeu_cau": ma_yeu_cau, "cac_moc": out(cac_moc, many=True).data,
            "lien_quan": [{"loai_yeu_cau": lq[0], "ma_yeu_cau": lq[1]} for lq in lien_quan]})


# ==========================================================
# PHÍA NHÂN VIÊN – đường dẫn bắt đầu bằng staff/
# ==========================================================
class NguyenNhanView(APIView):
    """GET /api/after-sales/staff/nguyen-nhan/?loai_xu_ly=&dang_ap_dung=1; POST thêm mới (UC07)."""
    quyen_yeu_cau = QuyenHauMai.QUAN_LY_NGUYEN_NHAN

    def get_permissions(self):
        # Xem danh sách: mọi nhân viên (để chọn nguyên nhân khi xử lý); thêm/sửa/xóa: cần quyền quản lý danh mục
        return [NhanVienCoHoSo()] if self.request.method == "GET" else [NhanVienHauMai()]

    def get(self, request):
        dang = request.query_params.get("dang_ap_dung")
        ds = DichVuNguyenNhan.danh_sach(request.query_params.get("loai_xu_ly") or None,
                                        None if dang is None else dang == "1")
        return ok("Lấy danh mục nguyên nhân thành công.", sr.NguyenNhanSerializer(ds, many=True).data)

    @bat_loi
    def post(self, request):
        s = kiem_tra(sr.NguyenNhanGhiSerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        if "loai_xu_ly" not in d:
            return du_lieu_sai(s) if s.errors else Response(
                {"message": "Dữ liệu không hợp lệ.", "errors": {"loai_xu_ly": ["Trường này là bắt buộc."]}},
                status=status.HTTP_400_BAD_REQUEST)
        nn = DichVuNguyenNhan.them(request.user, d.pop("loai_xu_ly"), d.pop("ten_nguyen_nhan", ""), **d)
        return ok("Thêm nguyên nhân thành công.", sr.NguyenNhanSerializer(nn).data, status.HTTP_201_CREATED)


class NguyenNhanChiTietView(APIView):
    """PATCH /staff/nguyen-nhan/<ma>/ sửa (kể cả thu_tu_hien_thi); DELETE xóa nguyên nhân chưa từng dùng."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.QUAN_LY_NGUYEN_NHAN

    @bat_loi
    def patch(self, request, ma_nguyen_nhan):
        s = kiem_tra(sr.NguyenNhanGhiSerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        nn = DichVuNguyenNhan.sua(request.user, ma_nguyen_nhan, **s.validated_data)
        return ok("Cập nhật nguyên nhân thành công.", sr.NguyenNhanSerializer(nn).data)

    @bat_loi
    def delete(self, request, ma_nguyen_nhan):
        DichVuNguyenNhan.xoa(request.user, ma_nguyen_nhan)
        return ok("Đã xóa nguyên nhân.")


class NguyenNhanTrangThaiView(APIView):
    """POST /staff/nguyen-nhan/<ma>/ngung-su-dung/ hoặc /kich-hoat/."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.QUAN_LY_NGUYEN_NHAN

    @bat_loi
    def post(self, request, ma_nguyen_nhan, thao_tac):
        if thao_tac == "ngung-su-dung":
            nn = DichVuNguyenNhan.ngung_su_dung(request.user, ma_nguyen_nhan)
        elif thao_tac == "kich-hoat":
            nn = DichVuNguyenNhan.kich_hoat(request.user, ma_nguyen_nhan)
        else:
            return Response({"message": "Thao tác không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        return ok("Cập nhật trạng thái nguyên nhân thành công.", sr.NguyenNhanSerializer(nn).data)


# ----- Hủy đơn (UC02) -----
class HuyDanhSachView(APIView):
    """GET /staff/huy/?trang_thai=CHO_XU_LY&tu_ngay=&den_ngay=&trang="""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HUY_DON

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.LocNgaySerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        trang = DichVuHuyDon.danh_sach(request.query_params.get("trang_thai") or None, d.get("tu_ngay"),
                                       d.get("den_ngay"), d.get("trang", 1))
        return ok("Lấy danh sách yêu cầu hủy thành công.", trang_du_lieu(trang, sr.YeuCauHuySerializer))


class HuyChiTietView(APIView):
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HUY_DON

    @bat_loi
    def get(self, request, ma_yc_huy):
        return ok("Lấy chi tiết yêu cầu hủy thành công.", sr.YeuCauHuySerializer(DichVuHuyDon.chi_tiet(ma_yc_huy)).data)


class HuyXuLyView(APIView):
    """POST /staff/huy/<ma>/xu-ly/ – body {"quyet_dinh": "DUYET"|"TU_CHOI", "ly_do_tu_choi", "ghi_chu"}."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HUY_DON

    @bat_loi
    def post(self, request, ma_yc_huy):
        s = kiem_tra(sr.XuLyYeuCauHuySerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        yc = DichVuHuyDon.xu_ly(ma_yc_huy, lay_nhan_vien(request), d["quyet_dinh"], d["ly_do_tu_choi"], d["ghi_chu"])
        return ok("Đã xử lý yêu cầu hủy.", sr.YeuCauHuySerializer(yc).data)


class HuyHangLoatView(APIView):
    """POST /staff/huy/xu-ly-hang-loat/ – duyệt nhiều yêu cầu (UC02 A1)."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HUY_DON

    def post(self, request):
        s = kiem_tra(sr.XuLyHangLoatSerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        return ok("Đã xử lý hàng loạt.", DichVuHuyDon.xu_ly_hang_loat(d["ma_yeu_cau"], lay_nhan_vien(request), d["ghi_chu"]))


# ----- Giao hàng không thành công (UC03) -----
class GiaoThatBaiDanhSachView(APIView):
    """GET /staff/giao-that-bai/?trang= – đơn đang giao cần xử lý."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_GIAO_HANG

    def get(self, request):
        trang = DichVuGiaoThatBai.danh_sach_don(int(request.query_params.get("trang", 1) or 1))
        return ok("Lấy danh sách đơn thành công.", {
            "tong_so": trang.paginator.count, "so_trang": trang.paginator.num_pages, "trang": trang.number,
            "ket_qua": [{"ma_dh": d.ma_dh, "ho_ten_nguoi_nhan": d.ho_ten_nguoi_nhan, "dia_chi_giao_hang": d.dia_chi_giao_hang,
                         "thoi_diem_ban_giao": d.thoi_diem_ban_giao, "so_lan_giao_lai": d.so_lan_giao_lai}
                        for d in trang.object_list]})


class GiaoThatBaiXuLyView(APIView):
    """GET /staff/giao-that-bai/<ma_dh>/ xem lịch sử các lần giao; POST /staff/giao-that-bai/<ma_dh>/xu-ly/ ghi nhận và chọn hướng xử lý."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_GIAO_HANG

    @bat_loi
    def get(self, request, ma_dh):
        don, cac_lan, so_that_bai = DichVuGiaoThatBai.thong_tin_don(ma_dh)
        return ok("Lấy thông tin giao hàng thành công.", {
            "ma_dh": don.ma_dh, "trang_thai": don.trang_thai, "so_lan_that_bai": so_that_bai,
            "da_dat_gioi_han": so_that_bai >= SO_LAN_GIAO_TOI_DA,
            "cac_lan_giao": [{"lan_giao": g.lan_giao, "ket_qua_giao": g.ket_qua_giao, "ly_do_that_bai": g.ly_do_that_bai,
                              "thoi_diem_ban_giao": g.thoi_diem_ban_giao} for g in cac_lan]})

    @bat_loi
    def post(self, request, ma_dh):
        s = kiem_tra(sr.XuLyGiaoThatBaiSerializer, request.data)
        if not s.is_valid():
            return du_lieu_sai(s)
        xl = DichVuGiaoThatBai.xu_ly(ma_dh, lay_nhan_vien(request), **s.validated_data)
        return ok("Đã ghi nhận giao không thành công.", sr.XuLyGiaoThatBaiOutSerializer(xl).data, status.HTTP_201_CREATED)


class GiaoThatBaiNhapKhoView(APIView):
    """POST /staff/giao-that-bai/xu-ly/<ma_xu_ly>/nhap-kho/ (UC03 A1)."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_GIAO_HANG

    @bat_loi
    def post(self, request, ma_xu_ly):
        xl = DichVuGiaoThatBai.xac_nhan_nhap_kho(ma_xu_ly, lay_nhan_vien(request))
        return ok("Đã xác nhận nhập kho.", sr.XuLyGiaoThatBaiOutSerializer(xl).data)


# ----- Đổi/trả (UC05) -----
class DoiTraDanhSachView(APIView):
    """GET /staff/doi-tra/?trang_thai=&hinh_thuc=&tu_ngay=&den_ngay=&trang="""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_DOI_TRA

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.LocNgaySerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        trang = DichVuDoiTra.danh_sach(request.query_params.get("trang_thai") or None,
                                       request.query_params.get("hinh_thuc") or None,
                                       d.get("tu_ngay"), d.get("den_ngay"), d.get("trang", 1))
        return ok("Lấy danh sách yêu cầu đổi/trả thành công.", trang_du_lieu(trang, sr.YeuCauDoiTraSerializer))


class DoiTraChiTietView(APIView):
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_DOI_TRA

    @bat_loi
    def get(self, request, ma_yc_doi_tra):
        return ok("Lấy chi tiết yêu cầu thành công.", sr.YeuCauDoiTraSerializer(DichVuDoiTra.chi_tiet(ma_yc_doi_tra)).data)


class DoiTraThaoTacView(APIView):
    """POST /staff/doi-tra/<ma>/<thao_tac>/ với thao_tac = duyet | tu-choi | nhan-hang | hoan-tat."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_DOI_TRA

    @bat_loi
    def post(self, request, ma_yc_doi_tra, thao_tac):
        nv = lay_nhan_vien(request)
        if thao_tac == "duyet":
            s = kiem_tra(sr.DuyetDoiTraSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            d = s.validated_data
            yc = DichVuDoiTra.duyet(ma_yc_doi_tra, nv, d["khong_thu_hoi_hang"], d["ghi_chu"], d["ma_van_don_doi"])
        elif thao_tac == "tu-choi":
            s = kiem_tra(sr.TuChoiSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            yc = DichVuDoiTra.tu_choi(ma_yc_doi_tra, nv, s.validated_data["ly_do"], s.validated_data["ghi_chu"])
        elif thao_tac == "nhan-hang":
            s = kiem_tra(sr.NhanHangSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            d = s.validated_data
            yc = DichVuDoiTra.nhan_hang(ma_yc_doi_tra, nv, [dict(k) for k in d["ket_qua_dong"]], d["ghi_chu"],
                                        d["ma_van_don_gui_lai"])
        elif thao_tac == "hoan-tat":
            s = kiem_tra(sr.HoanTatDoiTraSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            yc = DichVuDoiTra.hoan_tat(ma_yc_doi_tra, nv, s.validated_data["ma_van_don_doi"])
        else:
            return Response({"message": "Thao tác không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        return ok("Đã xử lý yêu cầu đổi/trả.", sr.YeuCauDoiTraSerializer(yc).data)


# ----- Hoàn tiền (UC06) -----
class HoanTienDanhSachView(APIView):
    """GET /staff/hoan-tien/?trang_thai=CHO_HOAN&nguon=&tu_ngay=&den_ngay=&trang="""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HOAN_TIEN

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.LocNgaySerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        d = s.validated_data
        trang = DichVuHoanTien.danh_sach(request.query_params.get("trang_thai") or None,
                                         request.query_params.get("nguon") or None,
                                         d.get("tu_ngay"), d.get("den_ngay"), d.get("trang", 1))
        return ok("Lấy danh sách hoàn tiền thành công.", trang_du_lieu(trang, sr.HoanTienSerializer))


class HoanTienChiTietView(APIView):
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HOAN_TIEN

    @bat_loi
    def get(self, request, ma_hoan_tien):
        khoan, da_hoan_truoc = DichVuHoanTien.chi_tiet(ma_hoan_tien)
        du_lieu = sr.HoanTienSerializer(khoan).data
        du_lieu["so_tien_da_hoan_hoac_cho_hoan_truoc_do"] = da_hoan_truoc
        du_lieu["phuong_thuc_thanh_toan_goc"] = khoan.don_hang.phuong_thuc_thanh_toan_id
        return ok("Lấy chi tiết khoản hoàn thành công.", du_lieu)


class HoanTienThaoTacView(APIView):
    """POST /staff/hoan-tien/<ma>/<thao_tac>/ với thao_tac = xac-nhan | that-bai | dieu-chinh."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HOAN_TIEN

    @bat_loi
    def post(self, request, ma_hoan_tien, thao_tac):
        nv = lay_nhan_vien(request)
        if thao_tac == "xac-nhan":
            s = kiem_tra(sr.XacNhanHoanTienSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            khoan = DichVuHoanTien.xac_nhan_da_hoan(ma_hoan_tien, nv, **s.validated_data)
        elif thao_tac == "that-bai":
            s = kiem_tra(sr.HoanTienThatBaiSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            khoan = DichVuHoanTien.ghi_nhan_that_bai(ma_hoan_tien, nv, s.validated_data["ly_do"])
        elif thao_tac == "dieu-chinh":
            s = kiem_tra(sr.DieuChinhHoanTienSerializer, request.data)
            if not s.is_valid():
                return du_lieu_sai(s)
            khoan = DichVuHoanTien.dieu_chinh(ma_hoan_tien, nv, s.validated_data["so_tien"], s.validated_data["ly_do"])
        else:
            return Response({"message": "Thao tác không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        return ok("Đã xử lý khoản hoàn tiền.", sr.HoanTienSerializer(khoan).data)


class HoanTienThanhToanThuaView(APIView):
    """POST /staff/hoan-tien/thanh-toan-thua/ – body {"ma_dh"}: tạo khoản hoàn phần khách chuyển thừa."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XU_LY_HOAN_TIEN

    @bat_loi
    def post(self, request):
        ma_dh = request.data.get("ma_dh")
        if not ma_dh:
            return Response({"message": "Vui lòng nhập mã đơn hàng."}, status=status.HTTP_400_BAD_REQUEST)
        don = DonHang.objects.filter(ma_dh=ma_dh).first()
        if don is None:
            return Response({"message": f"Không tìm thấy đơn hàng {ma_dh}."}, status=status.HTTP_400_BAD_REQUEST)
        khoan = DichVuHoanTien.tao_tu_thanh_toan_thua(don, lay_nhan_vien(request))
        return ok("Đã tạo khoản hoàn.", sr.HoanTienSerializer(khoan).data, status.HTTP_201_CREATED)


# ----- Thống kê (UC08) và thông báo nhân viên -----
class ThongKeView(APIView):
    """GET /staff/thong-ke/?tu_ngay=&den_ngay=&loai_xu_ly= – mặc định tháng hiện tại."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XEM_THONG_KE

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.ThongKeSerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        return ok("Lấy thống kê thành công.", DichVuThongKe.thong_ke(**s.validated_data))


class ThongKeXuatView(APIView):
    """GET /staff/thong-ke/xuat/ – tải báo cáo CSV theo bộ lọc hiện tại."""
    permission_classes = [NhanVienHauMai]
    quyen_yeu_cau = QuyenHauMai.XEM_THONG_KE

    @bat_loi
    def get(self, request):
        s = kiem_tra(sr.ThongKeSerializer, request.query_params)
        if not s.is_valid():
            return du_lieu_sai(s)
        noi_dung = DichVuThongKe.xuat_csv(DichVuThongKe.thong_ke(**s.validated_data))
        phan_hoi = HttpResponse(noi_dung, content_type="text/csv; charset=utf-8")
        phan_hoi["Content-Disposition"] = 'attachment; filename="thong_ke_nguyen_nhan.csv"'
        return phan_hoi


class ThongBaoNhanVienView(APIView):
    """GET /staff/thong-bao/?chua_doc=1 – thông báo yêu cầu mới (M4-BR18); POST /staff/thong-bao/<ma>/da-doc/."""
    permission_classes = [NhanVienCoHoSo]

    def get(self, request):
        ds = DichVuThongBao.cua_nhan_vien(request.query_params.get("chua_doc") == "1")
        return ok("Lấy thông báo thành công.", [
            {"ma_thong_bao": t.ma_thong_bao, "ma_dh": t.don_hang_id, "tieu_de": t.tieu_de, "noi_dung": t.noi_dung,
             "da_doc": t.da_doc, "thoi_diem_gui": t.thoi_diem_gui} for t in ds[:50]])

    @bat_loi
    def post(self, request, ma_thong_bao):
        DichVuThongBao.danh_dau_da_doc(ma_thong_bao)
        return ok("Đã đánh dấu đã đọc.")
