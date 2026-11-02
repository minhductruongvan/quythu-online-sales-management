# File: backend/orders/management/commands/xu_ly_don_dinh_ky.py
# Lệnh quản trị chạy các tác vụ định kỳ của Module 3:
#   - M3-UC11 A2, M3-BR17: hủy đơn chuyển khoản quá hạn thanh toán 24 giờ
#   - M3-UC13 A2, M3-BR21: tự xác nhận đã nhận hàng khi hết cửa sổ 7 ngày
# Chạy: python manage.py xu_ly_don_dinh_ky
# Chạy lại nhiều lần không làm đổi kết quả của đơn đã xử lý.

from django.core.management.base import BaseCommand

from orders.services import DichVuKetThucDon


class Command(BaseCommand):
    help = "Hủy đơn chuyển khoản quá hạn thanh toán và tự xác nhận đã nhận hàng sau 7 ngày."

    def handle(self, *args, **options):
        ket_qua = DichVuKetThucDon.chay_tac_vu_dinh_ky()
        self.stdout.write(
            f"Đã hủy {ket_qua['so_don_huy_qua_han']} đơn quá hạn thanh toán; "
            f"đã tự xác nhận nhận hàng {ket_qua['so_don_tu_xac_nhan']} đơn."
        )