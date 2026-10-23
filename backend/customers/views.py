from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DangKyKhachHangSerializer


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