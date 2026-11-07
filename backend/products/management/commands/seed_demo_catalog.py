from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import BienTheSanPham, DanhMucSanPham, SanPham


def barcode_for(sequence):
    body = f"8938501{sequence:05d}"
    checksum = sum(
        int(digit) * (1 if index % 2 == 0 else 3)
        for index, digit in enumerate(body)
    )
    return f"{body}{(10 - checksum % 10) % 10}"


class Command(BaseCommand):
    help = "Seed a reusable Quý Thu catalog with varied products for local development."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Demo catalog data may only be seeded when DEBUG=True.")

        categories = {}
        for code, name, description in (
            ("DM001", "Đặc sản dừa nướng", "Hương vị dừa nướng truyền thống Quý Thu."),
            ("DM002", "Quà tặng đặc sản", "Hộp quà đặc sản miền Trung."),
            ("DM003", "Bánh dừa nướng", "Các dòng bánh dừa nướng với nhiều hương vị và quy cách."),
            ("DM004", "Combo quà tặng", "Bộ quà đặc sản được phối sẵn cho dịp sum họp."),
            ("DM005", "Đặc sản miền Trung", "Hương vị đặc sản được tuyển chọn từ miền Trung."),
        ):
            categories[code], _ = DanhMucSanPham.objects.get_or_create(
                ma_dm=code,
                defaults={
                    "ten_dm": name,
                    "mo_ta": description,
                    "trang_thai": "ACTIVE",
                },
            )

        products = (
            (
                "SP001",
                categories["DM001"],
                "Bánh dừa nướng Quý Thu",
                "Bánh dừa nướng thơm giòn, làm từ dừa chọn lọc và công thức truyền thống.",
                (
                    ("Truyền thống", "120g", 35000, 29000, 10),
                    ("Mè đen", "150g", 49000, 42000, 10),
                ),
            ),
            (
                "SP002",
                categories["DM001"],
                "Bánh dừa nướng vị gừng",
                "Vị gừng ấm nhẹ kết hợp cùng dừa nướng giòn thơm.",
                (
                    ("Gừng", "120g", 39000, 33000, 10),
                    ("Gừng", "225g", 69000, 59000, 12),
                ),
            ),
            (
                "SP003",
                categories["DM002"],
                "Hộp quà Quý Thu",
                "Hộp quà đặc sản chỉn chu, phù hợp cho những dịp sum vầy.",
                (
                    ("Truyền thống", "225g", 89000, 76000, 8),
                    ("Lá dứa", "150g", 52000, 45000, 10),
                ),
            ),
            (
                "SP004",
                categories["DM003"],
                "Bánh dừa nướng mè rang",
                "Bánh dừa nướng giòn thơm, điểm mè rang bùi nhẹ.",
                (
                    ("Mè rang", "120g", 39000, 33000, 10),
                    ("Mè rang", "225g", 72000, 61000, 12),
                    ("Mè rang", "450g", 135000, 116000, 12),
                ),
            ),
            (
                "SP005",
                categories["DM003"],
                "Bánh dừa nướng lá dứa",
                "Hương lá dứa dịu nhẹ hòa cùng vị dừa nướng truyền thống.",
                (
                    ("Lá dứa", "120g", 39000, 33000, 10),
                    ("Lá dứa", "225g", 72000, 61000, 12),
                ),
            ),
            (
                "SP006",
                categories["DM003"],
                "Bánh dừa nướng cacao",
                "Vị cacao thơm đậm, cân bằng cùng độ giòn của bánh dừa.",
                (
                    ("Cacao", "120g", 42000, 36000, 10),
                    ("Cacao", "225g", 78000, 66000, 12),
                ),
            ),
            (
                "SP007",
                categories["DM003"],
                "Bánh dừa nướng vị sầu riêng",
                "Mùi thơm đặc trưng của sầu riêng trong từng miếng bánh giòn.",
                (
                    ("Sầu riêng", "120g", 49000, 42000, 10),
                    ("Sầu riêng", "225g", 92000, 79000, 12),
                ),
            ),
            (
                "SP008",
                categories["DM004"],
                "Hộp quà sum vầy",
                "Hộp quà kết hợp nhiều hương vị bánh dừa nướng Quý Thu.",
                (
                    ("Thập cẩm", "3 gói", 159000, 138000, 8),
                    ("Thập cẩm", "6 gói", 299000, 260000, 8),
                ),
            ),
            (
                "SP009",
                categories["DM004"],
                "Túi quà đặc sản Quý Thu",
                (
                    "Túi quà gồm các gói bánh dừa nướng Quý Thu, gọn nhẹ và phù hợp "
                    "để biếu tặng trong những dịp sum họp. Sản phẩm có lựa chọn vị "
                    "truyền thống hoặc mè đen; vui lòng chọn phiên bản để xem số gói "
                    "và giá tương ứng."
                ),
                (
                    ("Truyền thống", "2 gói", 99000, 85000, 8),
                    ("Mè đen", "4 gói", 189000, 165000, 8),
                ),
            ),
            (
                "SP010",
                categories["DM005"],
                "Bánh dừa nướng đặc biệt",
                "Phiên bản tuyển chọn với dừa thơm và độ giòn đậm vị.",
                (
                    ("Đặc biệt", "150g", 59000, 50000, 10),
                    ("Đặc biệt", "300g", 109000, 94000, 12),
                ),
            ),
        )

        created_variants = 0
        for product_code, category, name, description, variants in products:
            product, _ = SanPham.objects.get_or_create(
                ma_sp=product_code,
                defaults={
                    "danh_muc": category,
                    "ten_sp": name,
                    "mo_ta": description,
                    "trang_thai": "ACTIVE",
                },
            )
            for index, (flavor, pack, retail, wholesale, minimum) in enumerate(
                variants, start=1
            ):
                variant_code = f"BT{product_code[-3:]}{index:02d}"
                _, created = BienTheSanPham.objects.get_or_create(
                    ma_bien_the=variant_code,
                    defaults={
                        "san_pham": product,
                        "huong_vi": flavor,
                        "quy_cach": pack,
                        "barcode": barcode_for(int(product_code[-3:]) * 10 + index),
                        "gia_ban_le": retail,
                        "gia_ban_si": wholesale,
                        "so_luong_toi_thieu_si": minimum,
                        "trang_thai": "ACTIVE",
                    },
                )
                created_variants += int(created)

        demo_product_codes = [f"SP{index:03d}" for index in range(1, 11)]
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo catalog ready: {SanPham.objects.filter(ma_sp__in=demo_product_codes).count()} "
                f"products; {created_variants} variants added."
            )
        )
