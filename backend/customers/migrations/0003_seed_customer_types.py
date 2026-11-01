from django.db import migrations


def seed_customer_types(apps, schema_editor):
    LoaiKhachHang = apps.get_model(
        "customers",
        "LoaiKhachHang"
    )

    LoaiKhachHang.objects.update_or_create(
        ma_loai_kh="LKH001",
        defaults={
            "ten_loai_kh": "Khách lẻ",
            "mo_ta": "Khách hàng bán lẻ",
        }
    )

    LoaiKhachHang.objects.update_or_create(
        ma_loai_kh="LKH002",
        defaults={
            "ten_loai_kh": "Khách sỉ",
            "mo_ta": "Khách hàng bán sỉ",
        }
    )


def remove_customer_types(apps, schema_editor):
    LoaiKhachHang = apps.get_model(
        "customers",
        "LoaiKhachHang"
    )

    LoaiKhachHang.objects.filter(
        ma_loai_kh__in=["LKH001", "LKH002"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0002_khachhang_so_dien_thoai"),
    ]

    operations = [
        migrations.RunPython(
            seed_customer_types,
            remove_customer_types
        ),
    ]