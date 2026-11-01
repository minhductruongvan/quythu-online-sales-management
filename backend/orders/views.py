# File: backend/orders/views.py
# Module 3 – View của API giỏ hàng, trang thanh toán, đặt hàng, đơn hàng.
#
# Mỗi view chỉ làm 4 việc, theo khuôn của M1 (customers/views.py):
#   1. Lấy khách hàng từ tài khoản đang đăng nhập.
#   2. Đưa dữ liệu gửi lên qua serializer để kiểm tra định dạng.
#   3. Gọi hàm trong services.py (nghiệp vụ nằm hết ở đó).
#   4. Trả Response {"message": ..., "data": ...} kèm mã trạng thái HTTP.
#
# Phần 1 (file này): giỏ hàng – M3-UC01, M3-UC02.
# Phần 2 (bước sau): trang thanh toán, đặt hàng – M3-UC03, M3-UC04.

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import KhachHangCoHoSo
from .serializers import (
    CapNhatSoLuongSerializer,
    GioHangSerializer,
    ThemVaoGioSerializer,
)
from .services import (
    DichVuGioHang,
    DichVuTinhTien,
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