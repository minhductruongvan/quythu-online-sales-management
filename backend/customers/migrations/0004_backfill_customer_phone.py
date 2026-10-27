from django.db import migrations


def backfill_customer_phone(apps, schema_editor):
    KhachHang = apps.get_model("customers", "KhachHang")

    for khach_hang in KhachHang.objects.select_related("tai_khoan").all():
        if (
            not khach_hang.so_dien_thoai
            and khach_hang.tai_khoan
            and khach_hang.tai_khoan.so_dien_thoai
        ):
            khach_hang.so_dien_thoai = khach_hang.tai_khoan.so_dien_thoai
            khach_hang.save(update_fields=["so_dien_thoai"])


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0003_seed_customer_types"),
    ]

    operations = [
        migrations.RunPython(
            backfill_customer_phone,
            migrations.RunPython.noop,
        ),
    ]