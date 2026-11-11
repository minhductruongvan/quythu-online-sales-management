from django.db import migrations


CATEGORY_DESCRIPTIONS = {
    "DM001": "Giữ trọn hương vị bánh dừa nướng thủ công lâu đời của vùng đất Quế Sơn, Quảng Nam – thơm lừng mùi dừa tươi nướng lửa hồng, giòn tan trong từng miếng bánh.",
    "DM002": "Các mẫu hộp quà được thiết kế chỉn chu, sang trọng, gói trọn nét văn hóa miền Trung để bạn tự tin mang đi biếu tặng đối tác, khách quý hay người thân phương xa.",
    "DM003": "Thử trọn các hương vị bánh dừa nướng Quý Thu giòn rụm – từ vị truyền thống quen thuộc đến mè đen bùi béo, vị gừng ấm nồng hay lá dứa thanh mát.",
    "DM004": "Những giỏ quà đã được kết hợp sẵn giữa bánh ngon và trà thơm, giúp bạn chuẩn bị nhanh gọn một món quà tươm tất cho những dịp sum họp gia đình, lễ Tết.",
    "DM005": "Góc nhỏ gom góp những thức quà quê mộc mạc, đậm đà của dải đất miền Trung như bánh dừa nướng, mè xửng, bánh khô... để gửi đến người thương ở khắp mọi miền.",
}

PRODUCT_DESCRIPTIONS = {
    "SP001": "Nhắc đến bánh dừa nướng xứ Quảng là nhớ ngay đến cái vị mộc mạc, nguyên bản này. Không cầu kỳ, bánh chỉ làm từ cơm dừa tươi xay nhuyễn trộn với bột nếp và đường trắng, đem nướng đến khi vàng ươm, dậy mùi thơm phức. Cắn một miếng thấy giòn rụm, vị béo bùi của dừa quyện với vị ngọt thanh vừa vặn, không bị gắt cổ. Bánh này mà bày ra đĩa, pha thêm ấm trà xanh chát dịu ngồi nhâm nhi trò chuyện thì đúng chuẩn vị quê nhà.",
    "SP002": "Vẫn là miếng bánh dừa giòn tan quen thuộc nhưng được điểm thêm cốt gừng tươi và những lát gừng băm nhuyễn trên mặt bánh. Khi ăn, vị ngọt béo của dừa quyện cùng chút cay the, ấm nồng nơi đầu lưỡi rất thú vị. Những ngày trời trở gió hay se lạnh, hoặc những lúc đi xa cần chút gì đó nhấm nháp cho ấm bụng thì vị gừng này là hợp nhất.",
    "SP003": "Hộp quà đặc sản Quý Thu được tuyển chọn chỉn chu, kết hợp các gói bánh dừa nướng thơm giòn để gửi trao trong những dịp sum họp và lễ Tết.",
    "SP004": "Dành cho những ai mê bánh dừa nhưng lại ngại đồ ngọt. Ở dòng này, tỷ lệ dừa tươi chiếm đến 60%, kết hợp cùng thật nhiều hạt mè đen rang chín tới. Miếng bánh nướng lên mỏng hơn, ăn vào thấy độ giòn xốp rất vui miệng, vị ngọt được tiết chế lại để nhường chỗ cho cái bùi béo, thơm lừng của mè đen. Bánh hoàn toàn không dùng chất bảo quản hay phẩm màu, chuẩn sạch lành để ông bà, bố mẹ hay những người đang giữ dáng đều có thể yên tâm thưởng thức mỗi ngày.",
    "SP005": "Nếu bạn thích một hương vị nhẹ nhàng, thanh mát thì đừng bỏ qua vị lá dứa. Nhờ có cốt lá dứa tươi tự nhiên, miếng bánh không chỉ mang sắc xanh dịu mắt mà còn thoang thoảng mùi thơm thảo mộc rất dễ chịu. Chính hương lá dứa này đã làm dịu đi cái béo đậm của cốt dừa, để lại hậu vị ngọt dịu, thơm lâu mà ăn mãi không thấy ngấy.",
    "SP008": "Đúng như tên gọi, hộp quà mang sắc đỏ ấm cúng với họa tiết trống đồng, mây tre in nhũ vàng đậm không khí Tết cổ truyền. Mở hộp ra là sự kết hợp trọn vẹn của câu chuyện \"có bánh, có trà\": những gói bánh dừa nướng thơm giòn nằm cạnh hộp trà ngon đậm vị. Không cần những lời chúc hoa mỹ, món quà này tự nó đã gửi gắm trọn vẹn tấm lòng và mong ước về những giây phút đoàn viên, sum họp bên gia đình.",
    "SP009": "Một chiếc túi giấy Kraft mộc mạc, in hình tre trúc quê hương với quai xách dây thừng chắc chắn. Bên trong đã có sẵn đủ các vị bánh đặc trưng nhất của Quý Thu từ Truyền thống, Mè đen đến Vị gừng. Đi du lịch hay đi công tác miền Trung về, chỉ cần xách theo vài túi quà gọn gàng, giản dị mà tinh tế này để chia cho bạn bè, đồng nghiệp thì ai cũng quý.",
    "SP010": "Đây là dòng bánh được Quý Thu chăm chút nhất, gom đủ các nguyên liệu ngon vào trong một miếng bánh: vừa có cái giòn ngọt của dừa nướng, cái bùi của mè đen, lại thêm chút sợi gừng thơm ấm. Bánh được đặt trong chiếc hộp cứng màu đỏ đô điểm họa tiết ánh kim rất trang trọng. Nếu bạn đang tìm một món quà đặc sản chỉn chu để biếu đối tác, tặng người thân hay dâng lên bàn thờ gia tiên ngày Tết thì hộp bánh này vừa đẹp lòng người trao, vừa ấm lòng người nhận.",
}


def update_catalog_descriptions(apps, schema_editor):
    Category = apps.get_model("products", "DanhMucSanPham")
    Product = apps.get_model("products", "SanPham")

    for code, description in CATEGORY_DESCRIPTIONS.items():
        Category.objects.filter(pk=code).update(mo_ta=description)
    for code, description in PRODUCT_DESCRIPTIONS.items():
        Product.objects.filter(pk=code).update(mo_ta=description)


class Migration(migrations.Migration):
    dependencies = [("products", "0001_initial")]

    operations = [
        migrations.RunPython(update_catalog_descriptions, migrations.RunPython.noop),
    ]