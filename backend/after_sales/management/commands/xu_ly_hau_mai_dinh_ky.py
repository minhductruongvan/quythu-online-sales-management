# File: backend/after_sales/management/commands/xu_ly_hau_mai_dinh_ky.py
# Chạy định kỳ (ví dụ mỗi giờ): đóng các yêu cầu đổi/trả quá hạn gửi hàng 7 ngày (M4-BR06) và trả lại số lượng đã giữ.
#   python manage.py xu_ly_hau_mai_dinh_ky
from django.core.management.base import BaseCommand

from after_sales.services import DichVuDoiTra


class Command(BaseCommand):
    help = "Đóng yêu cầu đổi/trả quá hạn gửi hàng."

    def handle(self, *args, **options):
        so_luong = DichVuDoiTra.dong_yeu_cau_het_han()
        self.stdout.write(self.style.SUCCESS(f"Đã đóng {so_luong or 0} yêu cầu quá hạn."))
