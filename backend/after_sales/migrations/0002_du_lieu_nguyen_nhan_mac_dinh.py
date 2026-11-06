# Dữ liệu mẫu: danh mục nguyên nhân mặc định cho từng loại xử lý (mỗi loại có ít nhất một nguyên nhân đang áp dụng).
from django.db import migrations

# (mã, loại, tên, bắt buộc ảnh, bắt buộc ghi chú, lỗi do cửa hàng)
DU_LIEU = [
    ("NN001", "HUY_DON", "Đặt nhầm sản phẩm", False, False, False),
    ("NN002", "HUY_DON", "Muốn thay đổi địa chỉ hoặc thông tin nhận hàng", False, False, False),
    ("NN003", "HUY_DON", "Tìm được giá tốt hơn", False, False, False),
    ("NN004", "HUY_DON", "Khác", False, True, False),
    ("NN005", "GIAO_THAT_BAI", "Khách không nghe máy", False, False, False),
    ("NN006", "GIAO_THAT_BAI", "Khách từ chối nhận hàng", False, False, False),
    ("NN007", "GIAO_THAT_BAI", "Sai địa chỉ giao hàng", False, False, False),
    ("NN008", "GIAO_THAT_BAI", "Khác", False, True, False),
    ("NN009", "DOI_TRA", "Sản phẩm bị lỗi hoặc hư hỏng", True, False, True),
    ("NN010", "DOI_TRA", "Giao sai sản phẩm", True, False, True),
    ("NN011", "DOI_TRA", "Không đúng mô tả", True, False, True),
    ("NN012", "DOI_TRA", "Không còn nhu cầu", False, False, False),
    ("NN013", "DOI_TRA", "Khác", False, True, False),
]


def them_du_lieu(apps, schema_editor):
    NguyenNhan = apps.get_model("after_sales", "NguyenNhan")
    for thu_tu, (ma, loai, ten, anh, ghi_chu, loi_cua_hang) in enumerate(DU_LIEU, start=1):
        NguyenNhan.objects.get_or_create(
            ma_nguyen_nhan=ma,
            defaults=dict(loai_xu_ly=loai, ten_nguyen_nhan=ten, thu_tu_hien_thi=thu_tu, bat_buoc_anh=anh,
                          bat_buoc_ghi_chu=ghi_chu, loi_do_cua_hang=loi_cua_hang),
        )


def xoa_du_lieu(apps, schema_editor):
    apps.get_model("after_sales", "NguyenNhan").objects.filter(ma_nguyen_nhan__in=[d[0] for d in DU_LIEU]).delete()


class Migration(migrations.Migration):
    dependencies = [("after_sales", "0001_initial")]
    operations = [migrations.RunPython(them_du_lieu, xoa_du_lieu)]
