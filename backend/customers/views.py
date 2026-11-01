from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.db import transaction
from .models import TaiKhoan, KhachHang, NhanVien, LichSuKhachHang, DiaChiKH
from .serializers import (
    DangKyKhachHangSerializer,
    TrangThaiKhachHangSerializer,
    DangNhapSerializer,
    ThongTinCaNhanSerializer,
    HoSoKhachHangSerializer,
    ThemKhachHangSerializer,
    PhanLoaiKhachHangSerializer,
    DiaChiKHSerializer,
    TrangThaiTaiKhoanSerializer,
)
from .services import (
    DichVuTrangThaiTaiKhoan,
    DichVuLichSuHoSo,
    LoiNghiepVuTaiKhoan,
    LoiQuyenTaiKhoan,
)
from .permissions import (
    CoQuyenKhachHang,
    QuyenKhachHang,
    IsCustomer,
)

class DangKyKhachHangView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DangKyKhachHangSerializer(data=request.data)

        if serializer.is_valid():
            khach_hang = serializer.save()

            return Response(
                {
                    "message": "Đăng ký tài khoản thành công.",
                    "data": {
                        "ma_kh": khach_hang.ma_kh,
                        "ma_tk": khach_hang.tai_khoan.ma_tk,
                        "ho_ten": khach_hang.ho_ten,
                        "email": khach_hang.tai_khoan.email,
                        "so_dien_thoai": khach_hang.tai_khoan.so_dien_thoai,
                        "loai_khach_hang": khach_hang.loai_khach_hang.ten_loai_kh,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "message": "Đăng ký tài khoản thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
class DangNhapView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DangNhapSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        mat_khau = serializer.validated_data["mat_khau"]

        tai_khoan = TaiKhoan.objects.filter(
            email__iexact=email
        ).first()

        if tai_khoan and (
            tai_khoan.trang_thai == TaiKhoan.TrangThai.LOCKED
            or not tai_khoan.is_active
        ):
            return Response(
                {
                    "message": "Tài khoản đã bị khóa."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        user = authenticate(
            request=request,
            email=email,
            password=mat_khau,
        )

        if user is None:
            return Response(
                {
                    "message": "Email hoặc mật khẩu không chính xác."
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)

        return Response(
            {
                "message": "Đăng nhập thành công.",
                "data": {
                    "ma_tk": user.ma_tk,
                    "email": user.email,
                    "vai_tro": user.vai_tro,
                },
            },
            status=status.HTTP_200_OK,
        )

class DangXuatView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"message": "Bạn chưa đăng nhập."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        logout(request)

        return Response(
            {"message": "Đăng xuất thành công."},
            status=status.HTTP_200_OK,
        )

class ThongTinCaNhanView(APIView):
    permission_classes = [IsCustomer]
    def get(self, request):

        if not hasattr(request.user, "khach_hang"):
            return Response(
                {"message": "Tài khoản không có hồ sơ khách hàng."},
                status=status.HTTP_403_FORBIDDEN,
            )

        khach_hang = request.user.khach_hang
        serializer = ThongTinCaNhanSerializer(khach_hang)

        return Response(
            {
                "message": "Lấy thông tin cá nhân thành công.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):


        if not hasattr(request.user, "khach_hang"):
            return Response(
                {"message": "Tài khoản không có hồ sơ khách hàng."},
                status=status.HTTP_403_FORBIDDEN,
            )

        khach_hang = request.user.khach_hang

        serializer = ThongTinCaNhanSerializer(
            khach_hang,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            khach_hang = serializer.save()

            return Response(
                {
                    "message": "Cập nhật thông tin cá nhân thành công.",
                    "data": ThongTinCaNhanSerializer(khach_hang).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "message": "Cập nhật thông tin cá nhân thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

class DanhSachKhachHangView(APIView):
    permission_classes = [CoQuyenKhachHang]

    quyen_theo_method = {
        "GET": QuyenKhachHang.XEM_DANH_SACH,
        "POST": QuyenKhachHang.TAO_KHACH_HANG,
    }
    def get(self, request):


        danh_sach = KhachHang.objects.select_related(
            "tai_khoan",
            "loai_khach_hang",
        ).all()
        tu_khoa = request.query_params.get("search", "").strip()

        if tu_khoa:
            danh_sach = danh_sach.filter(
                Q(ma_kh__icontains=tu_khoa)
                | Q(ho_ten__icontains=tu_khoa)
                | Q(so_dien_thoai__icontains=tu_khoa)
                | Q(tai_khoan__email__icontains=tu_khoa)
            )
        loai_khach_hang = request.query_params.get(
            "loai_khach_hang", ""
        ).strip()
        trang_thai = request.query_params.get(
            "trang_thai", ""
        ).strip().upper()

        if trang_thai:
            danh_sach = danh_sach.filter(
                trang_thai=trang_thai
            )
        if loai_khach_hang:
            danh_sach = danh_sach.filter(
                loai_khach_hang__ten_loai_kh=loai_khach_hang
            )
        serializer = HoSoKhachHangSerializer(
            danh_sach,
            many=True,
        )

        return Response(
            {
                "message": "Lấy danh sách khách hàng thành công.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):

        serializer = ThemKhachHangSerializer(data=request.data)

        if serializer.is_valid():
            khach_hang = serializer.save()

            return Response(
                {
                    "message": "Thêm khách hàng thành công.",
                    "data": {
                        "ma_kh": khach_hang.ma_kh,
                        "ho_ten": khach_hang.ho_ten,
                        "so_dien_thoai": khach_hang.so_dien_thoai,
                        "loai_khach_hang": khach_hang.loai_khach_hang.ten_loai_kh,
                        "trang_thai": khach_hang.trang_thai,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "message": "Thêm khách hàng thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
class ChiTietKhachHangView(APIView):

    permission_classes = [CoQuyenKhachHang]

    quyen_theo_method = {
        "GET": QuyenKhachHang.XEM_CHI_TIET,
        "PATCH": QuyenKhachHang.CAP_NHAT_KHACH_HANG,
    }
    def get(self, request, ma_kh):


        khach_hang = KhachHang.objects.select_related(
            "tai_khoan",
            "loai_khach_hang",
        ).filter(
            ma_kh=ma_kh
        ).first()

        if khach_hang is None:
            return Response(
                {"message": "Không tìm thấy khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = HoSoKhachHangSerializer(khach_hang)

        return Response(
            {
                "message": "Lấy hồ sơ khách hàng thành công.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    @transaction.atomic
    def patch(self, request, ma_kh):

        khach_hang = KhachHang.objects.select_related(
            "tai_khoan",
            "loai_khach_hang",
        ).filter(
            ma_kh=ma_kh
        ).first()

        if khach_hang is None:
            return Response(
                {"message": "Không tìm thấy khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )
        du_lieu_cu = DichVuLichSuHoSo.lay_du_lieu_hien_tai(
            khach_hang
        )

        serializer = HoSoKhachHangSerializer(
            khach_hang,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            khach_hang = serializer.save()
            du_lieu_moi = DichVuLichSuHoSo.lay_du_lieu_hien_tai(
                khach_hang
            )

            DichVuLichSuHoSo.ghi_lich_su_cap_nhat(
                khach_hang=khach_hang,
                nguoi_thuc_hien=request.user,
                du_lieu_cu=du_lieu_cu,
                du_lieu_moi=du_lieu_moi,
            )
            return Response(
                {
                    "message": "Cập nhật hồ sơ khách hàng thành công.",
                    "data": HoSoKhachHangSerializer(khach_hang).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "message": "Cập nhật hồ sơ khách hàng thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

class PhanLoaiKhachHangView(APIView):
    permission_classes = [CoQuyenKhachHang]
    quyen_yeu_cau = QuyenKhachHang.PHAN_LOAI
    @transaction.atomic
    def patch(self, request, ma_kh):
        try:
            khach_hang = KhachHang.objects.select_related(
                "loai_khach_hang"
            ).get(ma_kh=ma_kh)
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy khách hàng."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = PhanLoaiKhachHangSerializer(
            khach_hang,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            loai_cu = khach_hang.loai_khach_hang.ten_loai_kh

            khach_hang = serializer.save()

            loai_moi = khach_hang.loai_khach_hang.ten_loai_kh

            if loai_cu != loai_moi:
                so_thu_tu = LichSuKhachHang.objects.count() + 1
                ma_lich_su = f"LS{so_thu_tu:03d}"

                while LichSuKhachHang.objects.filter(
                        ma_lich_su=ma_lich_su
                ).exists():
                    so_thu_tu += 1
                    ma_lich_su = f"LS{so_thu_tu:03d}"

                LichSuKhachHang.objects.create(
                    ma_lich_su=ma_lich_su,
                    khach_hang=khach_hang,
                    nguoi_thuc_hien=request.user,
                    loai_thay_doi=LichSuKhachHang.LoaiThayDoi.CUSTOMER_TYPE,
                    noi_dung_cu=loai_cu,
                    noi_dung_moi=loai_moi,
                )

            return Response(
                {
                    "message": "Cập nhật loại khách hàng thành công.",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                "message": "Cập nhật loại khách hàng thất bại.",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

class TrangThaiKhachHangView(APIView):
    permission_classes = [CoQuyenKhachHang]
    quyen_yeu_cau = QuyenKhachHang.DOI_TRANG_THAI

    @transaction.atomic
    def patch(self, request, ma_kh):

        try:
            khach_hang = KhachHang.objects.get(ma_kh=ma_kh)
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        trang_thai_cu = khach_hang.trang_thai

        serializer = TrangThaiKhachHangSerializer(
            khach_hang,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            khach_hang = serializer.save()

            if trang_thai_cu != khach_hang.trang_thai:
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
                    nguoi_thuc_hien=request.user,
                    loai_thay_doi=LichSuKhachHang.LoaiThayDoi.STATUS,
                    noi_dung_cu=trang_thai_cu,
                    noi_dung_moi=khach_hang.trang_thai,
                )

            return Response(
                {
                    "message": "Cập nhật trạng thái khách hàng thành công.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

class TrangThaiTaiKhoanView(APIView):
    permission_classes = [CoQuyenKhachHang]
    quyen_yeu_cau = QuyenKhachHang.KHOA_MO_TAI_KHOAN
    def patch(self, request, ma_kh):
        try:
            khach_hang = KhachHang.objects.select_related(
                "tai_khoan"
            ).get(ma_kh=ma_kh)
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TrangThaiTaiKhoanSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tai_khoan = (
                DichVuTrangThaiTaiKhoan.thay_doi_trang_thai(
                    khach_hang=khach_hang,
                    nguoi_thuc_hien=request.user,
                    hanh_dong=serializer.validated_data["hanh_dong"],
                )
            )

        except LoiQuyenTaiKhoan as exc:
            return Response(
                {"message": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        except LoiNghiepVuTaiKhoan as exc:
            return Response(
                {"message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": (
                    "Khóa tài khoản thành công."
                    if tai_khoan.trang_thai
                    == TaiKhoan.TrangThai.LOCKED
                    else "Mở khóa tài khoản thành công."
                ),
                "data": {
                    "ma_kh": khach_hang.ma_kh,
                    "ma_tk": tai_khoan.ma_tk,
                    "email": tai_khoan.email,
                    "trang_thai": tai_khoan.trang_thai,
                    "is_active": tai_khoan.is_active,
                },
            },
            status=status.HTTP_200_OK,
        )

class DanhSachDiaChiView(APIView):
    permission_classes = [IsCustomer]
    def get(self, request):

        try:
            khach_hang = request.user.khach_hang
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy hồ sơ khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        danh_sach_dia_chi = khach_hang.dia_chi.all().order_by(
            "-mac_dinh",
            "-ngay_cap_nhat",
        )

        serializer = DiaChiKHSerializer(
            danh_sach_dia_chi,
            many=True,
        )

        return Response(
            {
                "message": "Lấy danh sách địa chỉ thành công.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):

        try:
            khach_hang = request.user.khach_hang
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy hồ sơ khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DiaChiKHSerializer(data=request.data)

        if serializer.is_valid():
            so_thu_tu = DiaChiKH.objects.count() + 1
            ma_dia_chi = f"DC{so_thu_tu:03d}"

            while DiaChiKH.objects.filter(
                ma_dia_chi=ma_dia_chi
            ).exists():
                so_thu_tu += 1
                ma_dia_chi = f"DC{so_thu_tu:03d}"

            if serializer.validated_data.get("mac_dinh", False):
                khach_hang.dia_chi.filter(
                    mac_dinh=True
                ).update(mac_dinh=False)

            dia_chi = serializer.save(
                ma_dia_chi=ma_dia_chi,
                khach_hang=khach_hang,
            )

            return Response(
                {
                    "message": "Thêm địa chỉ thành công.",
                    "data": DiaChiKHSerializer(dia_chi).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            {
                "message": "Thêm địa chỉ thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

class ChiTietDiaChiView(APIView):
    permission_classes = [IsCustomer]
    def get(self, request, ma_dia_chi):

        try:
            khach_hang = request.user.khach_hang
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy hồ sơ khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            dia_chi = DiaChiKH.objects.get(
                ma_dia_chi=ma_dia_chi,
                khach_hang=khach_hang,
            )
        except DiaChiKH.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy địa chỉ."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DiaChiKHSerializer(dia_chi)

        return Response(
            {
                "message": "Lấy thông tin địa chỉ thành công.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
    def patch(self, request, ma_dia_chi):


        try:
            khach_hang = request.user.khach_hang
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy hồ sơ khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            dia_chi = DiaChiKH.objects.get(
                ma_dia_chi=ma_dia_chi,
                khach_hang=khach_hang,
            )
        except DiaChiKH.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy địa chỉ."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = DiaChiKHSerializer(
            dia_chi,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            if serializer.validated_data.get("mac_dinh") is True:
                khach_hang.dia_chi.filter(
                    mac_dinh=True
                ).exclude(
                    ma_dia_chi=ma_dia_chi
                ).update(mac_dinh=False)

            dia_chi = serializer.save()

            return Response(
                {
                    "message": "Cập nhật địa chỉ thành công.",
                    "data": DiaChiKHSerializer(dia_chi).data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "message": "Cập nhật địa chỉ thất bại.",
                "errors": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    def delete(self, request, ma_dia_chi):


        try:
            khach_hang = request.user.khach_hang
        except KhachHang.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy hồ sơ khách hàng."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            dia_chi = DiaChiKH.objects.get(
                ma_dia_chi=ma_dia_chi,
                khach_hang=khach_hang,
            )
        except DiaChiKH.DoesNotExist:
            return Response(
                {"message": "Không tìm thấy địa chỉ."},
                status=status.HTTP_404_NOT_FOUND,
            )

        dia_chi.delete()

        return Response(
            {"message": "Xóa địa chỉ thành công."},
            status=status.HTTP_200_OK,
        )