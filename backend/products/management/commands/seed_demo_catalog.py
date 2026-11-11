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
            ("DM001", "Đặc sản dừa nướng", "Giữ trọn hương vị bánh dừa nướng thủ công lâu đời của vùng đất Quế Sơn, Quảng Nam – thơm lừng mùi dừa tươi nướng lửa hồng, giòn tan trong từng miếng bánh."),
            ("DM002", "Quà tặng đặc sản", "Các mẫu hộp quà được thiết kế chỉn chu, sang trọng, gói trọn nét văn hóa miền Trung để bạn tự tin mang đi biếu tặng đối tác, khách quý hay người thân phương xa."),
            ("DM003", "Bánh dừa nướng", "Thử trọn các hương vị bánh dừa nướng Quý Thu giòn rụm – từ vị truyền thống quen thuộc đến mè đen bùi béo, vị gừng ấm nồng hay lá dứa thanh mát."),
            ("DM004", "Combo quà tặng", "Những giỏ quà đã được kết hợp sẵn giữa bánh ngon và trà thơm, giúp bạn chuẩn bị nhanh gọn một món quà tươm tất cho những dịp sum họp gia đình, lễ Tết."),
            ("DM005", "Đặc sản miền Trung", "Góc nhỏ gom góp những thức quà quê mộc mạc, đậm đà của dải đất miền Trung như bánh dừa nướng, mè xửng, bánh khô... để gửi đến người thương ở khắp mọi miền."),
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
                "Nhắc đến bánh dừa nướng xứ Quảng là nhớ ngay đến cái vị mộc mạc, nguyên bản này. Không cầu kỳ, bánh chỉ làm từ cơm dừa tươi xay nhuyễn trộn với bột nếp và đường trắng, đem nướng đến khi vàng ươm, dậy mùi thơm phức. Cắn một miếng thấy giòn rụm, vị béo bùi của dừa quyện với vị ngọt thanh vừa vặn, không bị gắt cổ. Bánh này mà bày ra đĩa, pha thêm ấm trà xanh chát dịu ngồi nhâm nhi trò chuyện thì đúng chuẩn vị quê nhà.",
                (
                    ("Truyền thống", "120g", 35000, 29000, 10),
                    ("Mè đen", "150g", 49000, 42000, 10),
                ),
            ),
            (
                "SP002",
                categories["DM001"],
                "Bánh dừa nướng vị gừng",
                "Vẫn là miếng bánh dừa giòn tan quen thuộc nhưng được điểm thêm cốt gừng tươi và những lát gừng băm nhuyễn trên mặt bánh. Khi ăn, vị ngọt béo của dừa quyện cùng chút cay the, ấm nồng nơi đầu lưỡi rất thú vị. Những ngày trời trở gió hay se lạnh, hoặc những lúc đi xa cần chút gì đó nhấm nháp cho ấm bụng thì vị gừng này là hợp nhất.",
                (
                    ("Gừng", "120g", 39000, 33000, 10),
                    ("Gừng", "225g", 69000, 59000, 12),
                ),
            ),
            (
                "SP003",
                categories["DM002"],
                "Hộp quà Quý Thu",
                "Hộp quà đặc sản Quý Thu được tuyển chọn chỉn chu, kết hợp các gói bánh dừa nướng thơm giòn để gửi trao trong những dịp sum họp và lễ Tết.",
                (
                    ("Truyền thống", "225g", 89000, 76000, 8),
                    ("Lá dứa", "150g", 52000, 45000, 10),
                ),
            ),
            (
                "SP004",
                categories["DM003"],
                "Bánh dừa nướng mè rang",
                "Dành cho những ai mê bánh dừa nhưng lại ngại đồ ngọt. Ở dòng này, tỷ lệ dừa tươi chiếm đến 60%, kết hợp cùng thật nhiều hạt mè đen rang chín tới. Miếng bánh nướng lên mỏng hơn, ăn vào thấy độ giòn xốp rất vui miệng, vị ngọt được tiết chế lại để nhường chỗ cho cái bùi béo, thơm lừng của mè đen. Bánh hoàn toàn không dùng chất bảo quản hay phẩm màu, chuẩn sạch lành để ông bà, bố mẹ hay những người đang giữ dáng đều có thể yên tâm thưởng thức mỗi ngày.",
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
                "Nếu bạn thích một hương vị nhẹ nhàng, thanh mát thì đừng bỏ qua vị lá dứa. Nhờ có cốt lá dứa tươi tự nhiên, miếng bánh không chỉ mang sắc xanh dịu mắt mà còn thoang thoảng mùi thơm thảo mộc rất dễ chịu. Chính hương lá dứa này đã làm dịu đi cái béo đậm của cốt dừa, để lại hậu vị ngọt dịu, thơm lâu mà ăn mãi không thấy ngấy.",
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
                "Đúng như tên gọi, hộp quà mang sắc đỏ ấm cúng với họa tiết trống đồng, mây tre in nhũ vàng đậm không khí Tết cổ truyền. Mở hộp ra là sự kết hợp trọn vẹn của câu chuyện \"có bánh, có trà\": những gói bánh dừa nướng thơm giòn nằm cạnh hộp trà ngon đậm vị. Không cần những lời chúc hoa mỹ, món quà này tự nó đã gửi gắm trọn vẹn tấm lòng và mong ước về những giây phút đoàn viên, sum họp bên gia đình.",
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
                    "Một chiếc túi giấy Kraft mộc mạc, in hình tre trúc quê hương với "
                    "quai xách dây thừng chắc chắn. Bên trong đã có sẵn đủ các vị bánh "
                    "đặc trưng nhất của Quý Thu từ Truyền thống, Mè đen đến Vị gừng. "
                    "Đi du lịch hay đi công tác miền Trung về, chỉ cần xách theo vài túi "
                    "quà gọn gàng, giản dị mà tinh tế này để chia cho bạn bè, đồng nghiệp "
                    "thì ai cũng quý."
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
                "Đây là dòng bánh được Quý Thu chăm chút nhất, gom đủ các nguyên liệu ngon vào trong một miếng bánh: vừa có cái giòn ngọt của dừa nướng, cái bùi của mè đen, lại thêm chút sợi gừng thơm ấm. Bánh được đặt trong chiếc hộp cứng màu đỏ đô điểm họa tiết ánh kim rất trang trọng. Nếu bạn đang tìm một món quà đặc sản chỉn chu để biếu đối tác, tặng người thân hay dâng lên bàn thờ gia tiên ngày Tết thì hộp bánh này vừa đẹp lòng người trao, vừa ấm lòng người nhận.",
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
