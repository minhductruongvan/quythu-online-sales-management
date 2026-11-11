# File: backend/orders/views.py
# Module 3 – View của API giỏ hàng, trang thanh toán, đặt hàng, đơn hàng.
#
# Mỗi view chỉ làm 4 việc, theo khuôn của M1 (customers/views.py):
#   1. Lấy khách hàng từ tài khoản đang đăng nhập.
#   2. Đưa dữ liệu gửi lên qua serializer để kiểm tra định dạng.
#   3. Gọi hàm trong services.py (nghiệp vụ nằm hết ở đó).
#   4. Trả Response {"message": ..., "data": ...} kèm mã trạng thái HTTP.
#
# Phần 1: giỏ hàng – M3-UC01, M3-UC02.
# Phần 2: trang thanh toán, đặt hàng – M3-UC03, M3-UC04.
# Phần 3: đơn hàng phía khách – M3-UC05, M3-UC06, cổng thanh toán giả lập (M3-UC11).
# Phần 4: phía nhân viên – M3-UC07 tra cứu và chi tiết đơn.
#         View phía nhân viên lấy NHÂN VIÊN ở bước 1 (request.user.nhan_vien).

from decimal import Decimal

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PhuongThucThanhToan, TrangThaiDonHang
from .permissions import KhachHangCoHoSo, NhanVienCoHoSo
from .serializers import (
    BanGiaoSerializer,
    CapNhatSoLuongSerializer,
    ChiTietDonKhachSerializer,
    ChiTietDonNhanVienSerializer,
    DatHangSerializer,
    DonHangSerializer,
    DonNhanVienSerializer,
    GhiChuSerializer,
    GiaoThanhCongSerializer,
    GioHangSerializer,
    GhiNhanChuyenKhoanSerializer,
    HenCungCapSerializer,
    KiemTraHangSerializer,
    LocDonCuaToiSerializer,
    ThanhToanGiaLapSerializer,
    ThemVaoGioSerializer,
    ThuCodSerializer,
    TraCuuDonSerializer,
    TrangThanhToanSerializer,
)
from .services import (
    DichVuDatHang,
    DichVuGiaoHang,
    DichVuGioHang,
    DichVuKetThucDon,
    DichVuThanhToan,
    DichVuTinhTien,
    DichVuTraCuuDon,
    DichVuTrangThanhToan,
    DichVuXuLyDon,
    LoiNghiepVuDonHang,
    LoiQuyenDonHang,
)


# ==========================================================
# Hàm dùng chung cho mọi view của M3
# ==========================================================
def phan_hoi_loi_nghiep_vu(loi):
    """
    Đổi lỗi do services.py raise thành Response.
    LoiQuyenDonHang là lớp con của LoiNghiepVuDonHang, nên view chỉ cần
    một khối `except LoiNghiepVuDonHang`; hàm này phân biệt 403 và 400.
    """
    if isinstance(loi, LoiQuyenDonHang):
        ma_trang_thai = status.HTTP_403_FORBIDDEN  # đụng vào dữ liệu không phải của mình
    else:
        ma_trang_thai = status.HTTP_400_BAD_REQUEST  # vi phạm quy tắc nghiệp vụ

    return Response({"message": str(loi)}, status=ma_trang_thai)


def phan_hoi_du_lieu_sai(serializer):
    """Serializer báo dữ liệu sai định dạng -> 400 kèm lỗi từng trường (như M1)."""
    return Response(
        {"message": "Dữ liệu không hợp lệ.", "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ==========================================================
# GIỎ HÀNG – M3-UC01, M3-UC02
# Mọi thao tác trên giỏ đều trả về NGUYÊN GIỎ sau thay đổi, cùng một định dạng,
# để trình duyệt vẽ lại giá từng dòng và tạm tính mà không tự tính tiền.
# Các dòng đang tích chọn gửi trên URL: ?chon=CG001&chon=CG002
# (tích chọn không lưu CSDL – đã chốt ở giai đoạn 2).
# ==========================================================
def phan_hoi_gio_hang(request, khach_hang, message):
    cac_ma_dang_chon = request.query_params.getlist("chon")
    gio = DichVuTinhTien.xem_gio_hang(khach_hang, cac_ma_dang_chon)

    return Response(
        {"message": message, "data": GioHangSerializer(gio).data},
        status=status.HTTP_200_OK,
    )


class GioHangView(APIView):
    """
    URL: /api/orders/cart/
    GET  – xem giỏ (UC02 bước 1–2)
    POST – thêm sản phẩm vào giỏ (UC01), body {"ma_bien_the": "BT001", "so_luong": 2}
    """

    permission_classes = [KhachHangCoHoSo]

    def get(self, request):
        khach_hang = request.user.khach_hang

        try:
            return phan_hoi_gio_hang(request, khach_hang, "Lấy giỏ hàng thành công.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

    def post(self, request):
        khach_hang = request.user.khach_hang

        serializer = ThemVaoGioSerializer(data=request.data)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        try:
            DichVuGioHang.them_vao_gio(
                khach_hang,
                serializer.validated_data["bien_the"],
                serializer.validated_data["so_luong"],
            )
            return phan_hoi_gio_hang(request, khach_hang, "Đã thêm sản phẩm vào giỏ hàng.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)


class DongGioHangView(APIView):
    """
    URL: /api/orders/cart/<ma_ctgh>/
    PATCH  – sửa số lượng một dòng (UC02), body {"so_luong": 5}
    DELETE – xóa một dòng khỏi giỏ (UC02)
    """

    permission_classes = [KhachHangCoHoSo]

    def patch(self, request, ma_ctgh):
        khach_hang = request.user.khach_hang

        serializer = CapNhatSoLuongSerializer(data=request.data)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        try:
            DichVuGioHang.cap_nhat_so_luong(
                khach_hang, ma_ctgh, serializer.validated_data["so_luong"]
            )
            return phan_hoi_gio_hang(request, khach_hang, "Đã cập nhật số lượng.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

    def delete(self, request, ma_ctgh):
        khach_hang = request.user.khach_hang

        try:
            DichVuGioHang.xoa_dong(khach_hang, ma_ctgh)
            return phan_hoi_gio_hang(request, khach_hang, "Đã xóa sản phẩm khỏi giỏ hàng.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

# ==========================================================
# TRANG THANH TOÁN, ĐẶT HÀNG – M3-UC03, M3-UC04
# ==========================================================
class TrangThanhToanView(APIView):
    """
    URL: /api/orders/checkout/?chon=CG001&chon=CG002&ma_dia_chi=DC001
    GET – mở trang thanh toán (UC02 bước 3, UC03 bước 1) và đổi địa chỉ (UC04).
    Không gửi ma_dia_chi -> dùng địa chỉ hiển thị sẵn. Chỉ đọc, không ghi CSDL.
    """

    permission_classes = [KhachHangCoHoSo]

    def get(self, request):
        khach_hang = request.user.khach_hang
        cac_ma_chon = request.query_params.getlist("chon")
        ma_dia_chi = request.query_params.get("ma_dia_chi")  # không có -> None

        try:
            trang = DichVuTrangThanhToan.xem_trang_thanh_toan(
                khach_hang, cac_ma_chon, ma_dia_chi
            )
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

        return Response(
            {"message": "Lấy thông tin thanh toán thành công.",
             "data": TrangThanhToanSerializer(trang).data},
            status=status.HTTP_200_OK,
        )


class DonHangView(APIView):
    """
    URL: /api/orders/
    GET  – danh sách đơn của tôi (UC05 bước 1–2), lọc: ?trang_thai=DANG_GIAO
    POST – đặt hàng (UC03 bước 3–4),
           body {"chon": ["CG001"], "ma_dia_chi": "DC001", "ma_pttt": "PT002"}
    """

    permission_classes = [KhachHangCoHoSo]

    def get(self, request):
        khach_hang = request.user.khach_hang

        serializer = LocDonCuaToiSerializer(data=request.query_params)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        trang_thai = serializer.validated_data.get("trang_thai")
        cac_don = DichVuTraCuuDon.danh_sach_don_cua_khach(khach_hang, trang_thai)
        # UC05-E1: khách chưa có đơn nào thì vẫn 200, danh sách rỗng, kèm câu báo của UC
        if not cac_don and not trang_thai:
            message = "Bạn chưa có đơn hàng nào."
        else:
            message = "Lấy danh sách đơn hàng thành công."
        return Response(
            {"message": message, "data": DonHangSerializer(cac_don, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        khach_hang = request.user.khach_hang

        serializer = DatHangSerializer(data=request.data)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        du_lieu = serializer.validated_data
        try:
            don = DichVuDatHang.dat_hang(
                khach_hang, du_lieu["chon"], du_lieu["ma_dia_chi"], du_lieu["ma_pttt"]
            )
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

        message = f"Đặt hàng thành công. Mã đơn hàng: {don.ma_dh}."
        if don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_CHUYEN_KHOAN:
            # UC03-A2: chuyển khoản thì thanh toán sau khi nhân viên xác nhận đơn
            message += " Bạn sẽ thanh toán sau khi đơn hàng được nhân viên xác nhận."

        return Response(
            {"message": message, "data": DonHangSerializer(don).data},
            status=status.HTTP_201_CREATED,
        )


# ==========================================================
# ĐƠN HÀNG PHÍA KHÁCH – M3-UC05, M3-UC06, cổng giả lập M3-UC11
# Mọi thao tác trên một đơn đều trả về NGUYÊN CHI TIẾT ĐƠN sau thay đổi
# (cùng ý tưởng với giỏ hàng), để trang vẽ lại trạng thái, lịch sử, nút bấm.
# ==========================================================
def phan_hoi_chi_tiet_don(don, message):
    don.refresh_from_db()  # đọc lại từ CSDL: service ghi bằng .update() nên đối tượng có thể cũ
    return Response(
        {"message": message, "data": ChiTietDonKhachSerializer(don).data},
        status=status.HTTP_200_OK,
    )


class ChiTietDonView(APIView):
    """
    URL: /api/orders/<ma_dh>/
    GET – chi tiết một đơn của tôi (UC05 bước 3). Đơn của người khác -> 403 (E2).
    """

    permission_classes = [KhachHangCoHoSo]

    def get(self, request, ma_dh):
        khach_hang = request.user.khach_hang

        try:
            don = DichVuTraCuuDon.chi_tiet_don_cua_khach(khach_hang, ma_dh)
            return phan_hoi_chi_tiet_don(don, "Lấy chi tiết đơn hàng thành công.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)


class DaNhanHangView(APIView):
    """
    URL: /api/orders/<ma_dh>/da-nhan-hang/
    POST – khách bấm [Đã nhận hàng] (UC06). Không cần body.
    """

    permission_classes = [KhachHangCoHoSo]

    def post(self, request, ma_dh):
        khach_hang = request.user.khach_hang

        try:
            don = DichVuTraCuuDon.lay_don(ma_dh)
            DichVuKetThucDon.khach_xac_nhan_da_nhan(don, khach_hang)
            return phan_hoi_chi_tiet_don(don, "Đã xác nhận nhận hàng.")
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)


class ThanhToanGiaLapView(APIView):
    """
    URL: /api/orders/<ma_dh>/payment/
    POST – cổng thanh toán giả lập cho đơn chuyển khoản (UC11, thay việc nhân viên đối soát),
           body {"ket_qua": "THANH_CONG"} hoặc {"ket_qua": "THAT_BAI"}
    """

    permission_classes = [KhachHangCoHoSo]

    def post(self, request, ma_dh):
        khach_hang = request.user.khach_hang

        serializer = ThanhToanGiaLapSerializer(data=request.data)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)
        thanh_cong = serializer.validated_data["ket_qua"] == "THANH_CONG"

        try:
            don = DichVuTraCuuDon.lay_don(ma_dh)
            DichVuThanhToan.thanh_toan_gia_lap(don, khach_hang, thanh_cong)
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

        if thanh_cong:
            message = "Thanh toán thành công. Đơn hàng đang chờ chuẩn bị."
        else:
            message = "Thanh toán không thành công. Bạn có thể thử lại trước hạn thanh toán."
        return phan_hoi_chi_tiet_don(don, message)


# ==========================================================
# PHÍA NHÂN VIÊN – M3-UC07 xem và tra cứu đơn hàng
# Đường dẫn bắt đầu bằng "staff/" để tách hẳn khỏi API của khách.
# ==========================================================
class DanhSachDonNhanVienView(APIView):
    """
    URL: /api/orders/staff/?tu_khoa=&trang_thai=&tu_ngay=&den_ngay=&loai_khach=&trang=
    GET – danh sách đơn có tìm kiếm, lọc, phân trang 20 đơn/trang (UC07 bước 1–2).
    Tiếp nhận đơn mới (A1): ?trang_thai=CHO_XAC_NHAN
    """

    permission_classes = [NhanVienCoHoSo]

    def get(self, request):
        serializer = TraCuuDonSerializer(data=request.query_params)
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        loc = serializer.validated_data
        trang = DichVuTraCuuDon.tra_cuu_don(
            tu_khoa=loc["tu_khoa"],
            trang_thai=loc.get("trang_thai"),
            tu_ngay=loc.get("tu_ngay"),
            den_ngay=loc.get("den_ngay"),
            ma_loai_kh=loc.get("loai_khach"),
            trang=loc["trang"],
        )
        tong_so_don = trang.paginator.count
        if tong_so_don == 0:
            message = "Không tìm thấy đơn phù hợp."  # E2
        else:
            message = "Lấy danh sách đơn hàng thành công."

        return Response(
            {
                "message": message,
                "data": DonNhanVienSerializer(trang.object_list, many=True).data,
                "tong_so_don": tong_so_don,
                "so_trang": trang.paginator.num_pages,
                "trang_hien_tai": trang.number,
            },
            status=status.HTTP_200_OK,
        )


class ChiTietDonNhanVienView(APIView):
    """
    URL: /api/orders/staff/<ma_dh>/
    GET – chi tiết đơn cho nhân viên (UC07 bước 3): dòng hàng kèm kết quả kiểm tra,
    lịch sử có tên người thao tác, các lần giao, bản ghi thanh toán, gợi ý hình thức giao.
    """

    permission_classes = [NhanVienCoHoSo]

    def get(self, request, ma_dh):
        try:
            don = DichVuTraCuuDon.lay_don(ma_dh)
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)

        return Response(
            {"message": "Lấy chi tiết đơn hàng thành công.",
             "data": ChiTietDonNhanVienSerializer(don).data},
            status=status.HTTP_200_OK,
        )

# ==========================================================
# THAO TÁC CỦA NHÂN VIÊN TRÊN MỘT ĐƠN – M3-UC08 đến M3-UC13 (bước 8C)
# URL: POST /api/orders/staff/<ma_dh>/<thao_tac>/   ví dụ .../staff/DH001/xac-nhan/
# Mười thao tác dùng CHUNG một view. Bảng CAC_THAO_TAC cho biết mỗi thao tác
# dùng serializer nào để đọc body và gọi hàm "nv_..." nào. Mỗi hàm "nv_..."
# gọi đúng một hàm service rồi trả câu thông báo.
# Sau thao tác luôn trả NGUYÊN CHI TIẾT ĐƠN phía nhân viên (giống phía khách).
# ==========================================================
def phan_hoi_chi_tiet_don_nv(don, message):
    don.refresh_from_db()  # service ghi bằng .update() nên đọc lại cho chắc
    return Response(
        {"message": message, "data": ChiTietDonNhanVienSerializer(don).data},
        status=status.HTTP_200_OK,
    )


def nv_kiem_tra_hang(don, nhan_vien, du_lieu):  # M3-UC09
    du_hang = DichVuXuLyDon.kiem_tra_kha_nang_cung_ung(
        don, nhan_vien, du_lieu["ket_qua"], du_lieu["ghi_chu"]
    )
    if du_hang:
        return "Đã lưu kết quả kiểm tra: đủ hàng."
    return "Đã lưu kết quả kiểm tra: thiếu hàng. Hãy chuyển đơn sang chờ bổ sung hàng."


def nv_xac_nhan(don, nhan_vien, du_lieu):  # M3-UC08
    DichVuXuLyDon.xac_nhan_don(don, nhan_vien, du_lieu["ghi_chu"])
    if don.trang_thai == TrangThaiDonHang.CHO_THANH_TOAN:
        return "Đã xác nhận đơn. Đơn chuyển khoản đang chờ khách thanh toán."
    return "Đã xác nhận đơn. Đơn chờ bắt đầu chuẩn bị hàng."


def nv_cho_bo_sung(don, nhan_vien, du_lieu):  # M3-UC10 bước 1–3
    DichVuXuLyDon.chuyen_cho_bo_sung(don, nhan_vien, du_lieu["thoi_diem_hen"], du_lieu["ghi_chu"])
    return "Đã chuyển đơn sang chờ bổ sung hàng."


def nv_gia_han(don, nhan_vien, du_lieu):  # M3-UC10 A1
    DichVuXuLyDon.gia_han_hen(don, nhan_vien, du_lieu["thoi_diem_hen"], du_lieu["ghi_chu"])
    return "Đã gia hạn thời điểm hẹn cung cấp."


def nv_da_du_hang(don, nhan_vien, du_lieu):  # M3-UC10 bước 4
    DichVuXuLyDon.da_du_hang(don, nhan_vien, du_lieu["ghi_chu"])
    return "Đã xác nhận đủ hàng. Đơn quay về bước trước khi chờ bổ sung."


def nv_thu_cod(don, nhan_vien, du_lieu):  # M3-UC11 (COD)
    so_tien = Decimal(du_lieu["so_tien_thuc_nhan"])  # tiền luôn dùng Decimal
    DichVuThanhToan.ghi_nhan_thu_cod(don, nhan_vien, so_tien, du_lieu["ghi_chu"])
    if don.trang_thai == TrangThaiDonHang.HOAN_THANH:
        return "Đã ghi nhận thu tiền COD. Đơn hàng đã hoàn thành."
    return "Đã ghi nhận thu tiền COD."


def nv_ghi_nhan_chuyen_khoan(don, nhan_vien, du_lieu):  # M3-UC11 (chuyển khoản)
    DichVuThanhToan.ghi_nhan_chuyen_khoan(
        don,
        nhan_vien,
        du_lieu["so_tien_thuc_nhan"],
        du_lieu["ma_giao_dich_ngan_hang"],
        du_lieu["ghi_chu"],
        du_lieu["ly_do_dieu_chinh"],
    )
    return "Đã lưu thông tin thanh toán chuyển khoản."


def nv_bat_dau_chuan_bi(don, nhan_vien, du_lieu):  # M3-UC12 bước 1
    DichVuGiaoHang.bat_dau_chuan_bi(don, nhan_vien, du_lieu["ghi_chu"])
    return "Đã bắt đầu chuẩn bị hàng."


def nv_san_sang_giao(don, nhan_vien, du_lieu):  # M3-UC12 bước 2
    DichVuGiaoHang.san_sang_giao(don, nhan_vien, du_lieu["ghi_chu"])
    return "Đơn đã sẵn sàng giao."


def nv_ban_giao(don, nhan_vien, du_lieu):  # M3-UC12 bước 3–4
    DichVuGiaoHang.ban_giao(
        don, nhan_vien, du_lieu["hinh_thuc_giao"], du_lieu["don_vi_van_chuyen"],
        du_lieu["sdt_shipper"], du_lieu["ma_van_don"], du_lieu["ghi_chu"],
    )
    return "Đã bàn giao vận chuyển. Đơn đang giao."


def nv_giao_thanh_cong(don, nhan_vien, du_lieu):  # M3-UC13
    DichVuKetThucDon.giao_thanh_cong(don, nhan_vien, du_lieu["thoi_diem_giao"], du_lieu["ghi_chu"])
    if don.phuong_thuc_thanh_toan_id == PhuongThucThanhToan.MA_COD:
        return "Đã ghi nhận giao thành công. Vui lòng ghi nhận thu tiền COD."  # UC13 bước 3
    return "Đã ghi nhận giao thành công."


# Tên thao tác trên URL -> (serializer đọc body, hàm thực hiện)
CAC_THAO_TAC = {
    "kiem-tra-hang": (KiemTraHangSerializer, nv_kiem_tra_hang),
    "xac-nhan": (GhiChuSerializer, nv_xac_nhan),
    "cho-bo-sung": (HenCungCapSerializer, nv_cho_bo_sung),
    "gia-han": (HenCungCapSerializer, nv_gia_han),
    "da-du-hang": (GhiChuSerializer, nv_da_du_hang),
    "thu-cod": (ThuCodSerializer, nv_thu_cod),
    "ghi-nhan-thanh-toan": (GhiNhanChuyenKhoanSerializer, nv_ghi_nhan_chuyen_khoan),
    "bat-dau-chuan-bi": (GhiChuSerializer, nv_bat_dau_chuan_bi),
    "san-sang-giao": (GhiChuSerializer, nv_san_sang_giao),
    "ban-giao": (BanGiaoSerializer, nv_ban_giao),
    "giao-thanh-cong": (GiaoThanhCongSerializer, nv_giao_thanh_cong),
}


class ThaoTacNhanVienView(APIView):
    """
    URL: /api/orders/staff/<ma_dh>/<thao_tac>/
    POST – một thao tác xử lý đơn của nhân viên (UC08–UC13), body JSON tùy thao tác.
    Thao tác không có trong CAC_THAO_TAC -> 404.
    """

    permission_classes = [NhanVienCoHoSo]

    def post(self, request, ma_dh, thao_tac):
        nhan_vien = request.user.nhan_vien                              # 1. người thao tác
        if thao_tac not in CAC_THAO_TAC:
            return Response({"message": "Thao tác không hợp lệ."}, status=status.HTTP_404_NOT_FOUND)
        lop_serializer, ham_thuc_hien = CAC_THAO_TAC[thao_tac]

        serializer = lop_serializer(data=request.data)                  # 2. định dạng body
        if not serializer.is_valid():
            return phan_hoi_du_lieu_sai(serializer)

        try:
            don = DichVuTraCuuDon.lay_don(ma_dh)                        # 3. nghiệp vụ
            message = ham_thuc_hien(don, nhan_vien, serializer.validated_data)
        except LoiNghiepVuDonHang as loi:
            return phan_hoi_loi_nghiep_vu(loi)
        return phan_hoi_chi_tiet_don_nv(don, message)                   # 4. trả chi tiết đơn