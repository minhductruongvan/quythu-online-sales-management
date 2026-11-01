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

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PhuongThucThanhToan
from .permissions import KhachHangCoHoSo
from .serializers import (
    CapNhatSoLuongSerializer,
    DatHangSerializer,
    DonHangSerializer,
    GioHangSerializer,
    ThemVaoGioSerializer,
    TrangThanhToanSerializer,
)
from .services import (
    DichVuDatHang,
    DichVuGioHang,
    DichVuTinhTien,
    DichVuTrangThanhToan,
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
    POST – đặt hàng (UC03 bước 3–4),
           body {"chon": ["CG001"], "ma_dia_chi": "DC001", "ma_pttt": "PT002"}
    (Giai đoạn 4 thêm GET – danh sách đơn của tôi, UC05.)
    """

    permission_classes = [KhachHangCoHoSo]

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