from django.db import migrations


def backfill_don_vi_tinh(apps, schema_editor):
    DonViTinh = apps.get_model("products", "DonViTinh")
    BienTheSanPham = apps.get_model("products", "BienTheSanPham")
    db_alias = schema_editor.connection.alias

    don_vi_goi, _ = DonViTinh.objects.using(db_alias).get_or_create(
        ma_dvt="DVT001",
        defaults={"ten_dvt": "Gói", "ky_hieu": "goi"},
    )
    don_vi_hop, _ = DonViTinh.objects.using(db_alias).get_or_create(
        ma_dvt="DVT002",
        defaults={"ten_dvt": "Hộp", "ky_hieu": "hop"},
    )
    DonViTinh.objects.using(db_alias).get_or_create(
        ma_dvt="DVT003",
        defaults={"ten_dvt": "Thùng", "ky_hieu": "thung"},
    )

    bien_the_thieu = BienTheSanPham.objects.using(db_alias).select_related("san_pham").filter(
        don_vi_tinh__isnull=True
    )
    for bien_the in bien_the_thieu:
        ten_sp = (bien_the.san_pham.ten_sp or "").lower()
        la_hop = bien_the.quy_cach in ("150g", "300g") or "hộp" in ten_sp
        bien_the.don_vi_tinh = don_vi_hop if la_hop else don_vi_goi
        bien_the.save(update_fields=["don_vi_tinh"])


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0005_rang_buoc_toan_ven_san_pham"),
    ]

    operations = [
        migrations.RunPython(backfill_don_vi_tinh, migrations.RunPython.noop),
    ]
