from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_cap_nhat_don_vi_tinh_bien_the"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="bienthesanpham",
            name="ck_bienthe_gia_le_khong_am",
        ),
        migrations.RemoveConstraint(
            model_name="bienthesanpham",
            name="ck_bienthe_gia_si_khong_am",
        ),
        migrations.AddConstraint(
            model_name="bienthesanpham",
            constraint=models.CheckConstraint(
                condition=models.Q(("gia_ban_le__gt", 0)),
                name="ck_bienthe_gia_le_duong",
            ),
        ),
        migrations.AddConstraint(
            model_name="bienthesanpham",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("gia_ban_si__isnull", True),
                    ("gia_ban_si__gt", 0),
                    _connector="OR",
                ),
                name="ck_bienthe_gia_si_duong",
            ),
        ),
    ]
