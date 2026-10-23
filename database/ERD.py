import sqlite3
import os

# =========================================================
# TÊN FILE CSDL
# =========================================================
TEN_FILE_CSDL = "qlbh.db"


# =========================================================
# HÀM TẠO MÃ EAN-13 CHO SẢN PHẨM
# =========================================================
def tao_ean13(so_thu_tu):
    """
    Tạo mã EAN-13 chuẩn: 12 số đầu + 1 số kiểm tra
    """
    phan_12_so = f"893850123{so_thu_tu:03d}"
    tong = 0
    for i, ky_tu in enumerate(phan_12_so):
        so = int(ky_tu)
        tong += so if i % 2 == 0 else so * 3
    check_digit = (10 - (tong % 10)) % 10
    return phan_12_so + str(check_digit)


# =========================================================
# HÀM TẠO CSDL VÀ NHẬP DỮ LIỆU
# =========================================================
def tao_csdl_qlbh():
    # -----------------------------------------------------
    # 1. Làm mới file CSDL cũ nếu tồn tại
    # -----------------------------------------------------
    if os.path.exists(TEN_FILE_CSDL):
        os.remove(TEN_FILE_CSDL)
        print(f"[-] Đã làm mới file CSDL: {TEN_FILE_CSDL}")

    # -----------------------------------------------------
    # 2. Kết nối SQLite & Bật khóa ngoại
    # -----------------------------------------------------
    ket_noi = sqlite3.connect(TEN_FILE_CSDL)
    con_tro = ket_noi.cursor()
    con_tro.execute("PRAGMA foreign_keys = ON;")

    print("[+] Đang tạo cấu trúc 20 bảng CSDL Quản lý bán hàng Quý Thu...")

    # =====================================================
    # PHẦN I. MODULE 1: QUẢN LÝ TÀI KHOẢN & KHÁCH HÀNG
    # =====================================================

    # 1. Tài khoản dùng chung cho khách hàng, nhân viên và quản lý
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS TAIKHOAN (
        MaTK NVARCHAR(10) PRIMARY KEY,
        Email NVARCHAR(100) NOT NULL UNIQUE,
        SoDienThoai NVARCHAR(15) UNIQUE,
        MatKhau NVARCHAR(255) NOT NULL,
        VaiTro NVARCHAR(20) NOT NULL
            CHECK (VaiTro IN ('CUSTOMER', 'EMPLOYEE', 'MANAGER')),
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'LOCKED')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        LanDangNhapCuoi DATETIME
    );
    """)

    # 2. Loại khách hàng: khách lẻ / khách sỉ
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS LOAIKHACHHANG (
        MaLoaiKH NVARCHAR(10) PRIMARY KEY,
        TenLoaiKH NVARCHAR(50) NOT NULL UNIQUE
            CHECK (TenLoaiKH IN ('Khách lẻ', 'Khách sỉ')),
        MoTa NVARCHAR(255)
    );
    """)

    # 3. Hồ sơ khách hàng
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS KHACHHANG (
        MaKH NVARCHAR(10) PRIMARY KEY,
        MaTK NVARCHAR(10) UNIQUE,
        MaLoaiKH NVARCHAR(10) NOT NULL,
        HoTen NVARCHAR(100) NOT NULL,
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'INACTIVE')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaTK)
            REFERENCES TAIKHOAN(MaTK)
            ON UPDATE CASCADE
            ON DELETE SET NULL,
        FOREIGN KEY (MaLoaiKH)
            REFERENCES LOAIKHACHHANG(MaLoaiKH)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    );
    """)

    # 4. Hồ sơ nhân viên
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS NHANVIEN (
        MaNV NVARCHAR(10) PRIMARY KEY,
        MaTK NVARCHAR(10) NOT NULL UNIQUE,
        HoTen NVARCHAR(100) NOT NULL,
        SoDienThoai NVARCHAR(15),
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'INACTIVE')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaTK)
            REFERENCES TAIKHOAN(MaTK)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    );
    """)

    # 5. Địa chỉ giao hàng của khách hàng
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS DIACHIKH (
        MaDiaChi NVARCHAR(10) PRIMARY KEY,
        MaKH NVARCHAR(10) NOT NULL,
        TenNguoiNhan NVARCHAR(100) NOT NULL,
        SoDienThoai NVARCHAR(15) NOT NULL,
        DiaChiChiTiet NVARCHAR(255) NOT NULL,
        PhuongXa NVARCHAR(100),
        QuanHuyen NVARCHAR(100),
        TinhThanh NVARCHAR(100) NOT NULL,
        MacDinh INTEGER NOT NULL DEFAULT 0
            CHECK (MacDinh IN (0, 1)),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaKH)
            REFERENCES KHACHHANG(MaKH)
            ON UPDATE CASCADE
            ON DELETE CASCADE
    );
    """)

    # 6. Lịch sử thay đổi hồ sơ khách hàng
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS LICHSU_KHACHHANG (
        MaLichSu NVARCHAR(10) PRIMARY KEY,
        MaKH NVARCHAR(10) NOT NULL,
        MaNguoiThucHien NVARCHAR(10),
        LoaiThayDoi NVARCHAR(30) NOT NULL
            CHECK (
                LoaiThayDoi IN (
                    'PROFILE_UPDATE',
                    'CUSTOMER_TYPE',
                    'STATUS',
                    'ACCOUNT_LOCK',
                    'ACCOUNT_UNLOCK',
                    'IMPORT'
                )
            ),
        NoiDungCu NVARCHAR(500),
        NoiDungMoi NVARCHAR(500),
        ThoiGian DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaKH)
            REFERENCES KHACHHANG(MaKH)
            ON UPDATE CASCADE
            ON DELETE CASCADE,
        FOREIGN KEY (MaNguoiThucHien)
            REFERENCES TAIKHOAN(MaTK)
            ON UPDATE CASCADE
            ON DELETE SET NULL
    );
    """)
    # =====================================================
    # PHẦN II. MODULE 2: QUẢN LÝ SẢN PHẨM & DANH MỤC
    # =====================================================

    # 1. Danh mục sản phẩm
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS DANHMUCSANPHAM (
        MaDM NVARCHAR(10) PRIMARY KEY,
        TenDM NVARCHAR(100) NOT NULL UNIQUE,
        MoTa NVARCHAR(500),
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'INACTIVE')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Thông tin sản phẩm chung
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS SANPHAM (
        MaSP NVARCHAR(10) PRIMARY KEY,
        MaDM NVARCHAR(10) NOT NULL,
        TenSP NVARCHAR(200) NOT NULL,
        MoTa TEXT,
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'INACTIVE')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaDM)
            REFERENCES DANHMUCSANPHAM(MaDM)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    );
    """)

    # 3. Biến thể sản phẩm theo hương vị và quy cách
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS BIENTHE_SANPHAM (
        MaBienTheSP NVARCHAR(10) PRIMARY KEY,
        MaSP NVARCHAR(10) NOT NULL,
        HuongVi NVARCHAR(50) NOT NULL
            CHECK (HuongVi IN ('Truyền thống', 'Mè đen', 'Gừng')),
        QuyCach NVARCHAR(20) NOT NULL
            CHECK (QuyCach IN ('120g', '125g', '150g', '225g')),
        BarCode NVARCHAR(50) NOT NULL UNIQUE,
        GiaBanLe DECIMAL(15,2) NOT NULL
            CHECK (GiaBanLe >= 0),
        GiaBanSi DECIMAL(15,2)
            CHECK (GiaBanSi IS NULL OR GiaBanSi >= 0),
        TrangThai NVARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
            CHECK (TrangThai IN ('ACTIVE', 'INACTIVE')),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT UQ_BIENTHE
            UNIQUE (MaSP, HuongVi, QuyCach),

        FOREIGN KEY (MaSP)
            REFERENCES SANPHAM(MaSP)
            ON UPDATE CASCADE
            ON DELETE CASCADE
    );
    """)

    # 4. Hình ảnh sản phẩm
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS HINHANH_SANPHAM (
        MaHinhAnh NVARCHAR(10) PRIMARY KEY,
        MaSP NVARCHAR(10) NOT NULL,
        DuongDan NVARCHAR(500) NOT NULL,
        AnhChinh INTEGER NOT NULL DEFAULT 0
            CHECK (AnhChinh IN (0, 1)),
        ThuTu INTEGER NOT NULL DEFAULT 0
            CHECK (ThuTu >= 0),
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (MaSP)
            REFERENCES SANPHAM(MaSP)
            ON UPDATE CASCADE
            ON DELETE CASCADE
    );
    """)
    # =====================================================
    # PHẦN III. MODULE 3: GIỎ HÀNG & ĐƠN HÀNG
    # =====================================================
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS GIOHANG (
        MaGioHang NVARCHAR(10) PRIMARY KEY,
        MaKH NVARCHAR(10) NOT NULL UNIQUE,
        NgayTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY (MaKH)
            REFERENCES KHACHHANG(MaKH)
            ON UPDATE CASCADE
            ON DELETE CASCADE
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS CT_GIOHANG (
        MaCTGH NVARCHAR(10) PRIMARY KEY,
        MaGioHang NVARCHAR(10) NOT NULL,
        MaBienTheSP NVARCHAR(10) NOT NULL,
        SoLuong INT NOT NULL DEFAULT 1
            CHECK (SoLuong > 0),
        NgayCapNhat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT UQ_CTGH
            UNIQUE (MaGioHang, MaBienTheSP),

        FOREIGN KEY (MaGioHang)
            REFERENCES GIOHANG(MaGioHang)
            ON UPDATE CASCADE
            ON DELETE CASCADE,

        FOREIGN KEY (MaBienTheSP)
            REFERENCES BIENTHE_SANPHAM(MaBienTheSP)
            ON UPDATE CASCADE
            ON DELETE RESTRICT
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS PHUONGTHUCTHANHTOAN (
        MaPTTT NVARCHAR(10) PRIMARY KEY,
        TenPTTT NVARCHAR(50) NOT NULL UNIQUE,
        ThongTinTaiKhoan NVARCHAR(255),
        TrangThaiKichHoat INT NOT NULL DEFAULT 1 CHECK (TrangThaiKichHoat IN (0, 1)),
        GhiChuHuongDan NVARCHAR(255)
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS DONHANG (
        MaDH NVARCHAR(10) PRIMARY KEY,
        MaKH NVARCHAR(10) NOT NULL,
        MaLoaiKH_ApDung NVARCHAR(10) NOT NULL,
        HoTenNguoiNhan NVARCHAR(50) NOT NULL,
        SDTNguoiNhan NVARCHAR(15) NOT NULL,
        DiaChiGiaoHang NVARCHAR(500) NOT NULL,
        TongTienHang DECIMAL(15,2) NOT NULL DEFAULT 0 CHECK (TongTienHang >= 0),
        PhiVanChuyen DECIMAL(15,2) NOT NULL DEFAULT 0 CHECK (PhiVanChuyen >= 0),
        TinhGiao VARCHAR(50) NOT NULL,
        TongThanhToan DECIMAL(15,2) NOT NULL DEFAULT 0,
        MaPTTT NVARCHAR(10) NOT NULL,
        TrangThaiThanhToan NVARCHAR(25) NOT NULL DEFAULT 'Chưa thanh toán' 
            CHECK (TrangThaiThanhToan IN ('Chưa thanh toán', 'Đã thanh toán', 'Thanh toán thất bại')),
        TrangThaiDonHang NVARCHAR(30) NOT NULL DEFAULT 'Chờ xác nhận'
            CHECK (TrangThaiDonHang IN ('Chờ xác nhận', 'Đã xác nhận', 'Đang chuẩn bị hàng', 'Chờ bổ sung hàng', 
                                        'Sẵn sàng giao', 'Đang giao', 'Giao thành công', 'Giao thất bại', 'Hoàn thành', 'Đã hủy')),
        GhiChu NVARCHAR(255),
        NgayDat DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        MaNV_XacNhan NVARCHAR(10),
        ThoiDiemBatDauChuanBi DATETIME,
        SoLanGiaoLai INT NOT NULL DEFAULT 0 CHECK (SoLanGiaoLai BETWEEN 0 AND 2),
        ThoiDiemGiaoThanhCong DATETIME,
        ThoiDiemXacNhanNhanHang DATETIME,
        ThoiDiemHoanThanh DATETIME,
        CHECK (TongThanhToan = TongTienHang + PhiVanChuyen),
        FOREIGN KEY (MaKH) REFERENCES KHACHHANG(MaKH) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (MaLoaiKH_ApDung) REFERENCES LOAIKHACHHANG(MaLoaiKH) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (MaPTTT) REFERENCES PHUONGTHUCTHANHTOAN(MaPTTT) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (MaNV_XacNhan) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS CT_DONHANG (
        MaCTDH NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        MaBienTheSP NVARCHAR(10) NOT NULL,
        SoLuong INT NOT NULL CHECK (SoLuong > 0),
        LoaiGiaApDung NVARCHAR(20) NOT NULL CHECK (LoaiGiaApDung IN ('Giá lẻ', 'Giá sỉ')),
        DonGia DECIMAL(15,2) NOT NULL CHECK (DonGia >= 0),
        ThanhTien DECIMAL(15,2) NOT NULL CHECK (ThanhTien >= 0),
        CHECK (ThanhTien = SoLuong * DonGia),
        CONSTRAINT UQ_CTDH UNIQUE (MaDH, MaBienTheSP),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaBienTheSP) REFERENCES BIENTHE_SANPHAM(MaBienTheSP) ON UPDATE CASCADE ON DELETE RESTRICT
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS LICHSUTRANGTHAI_DH (
        MaLSTT NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        TrangThai NVARCHAR(30) NOT NULL,
        ThoiDiem DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        TacNhan NVARCHAR(20) NOT NULL CHECK (TacNhan IN ('Khách hàng', 'Hệ thống', 'Nhân viên')),
        MaNV NVARCHAR(10),
        GhiChu NVARCHAR(255),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaNV) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    # =====================================================
    # PHẦN IV. MODULE 4: THANH TOÁN, HỦY & ĐỔI TRẢ
    # =====================================================
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS GIAODICH_THANHTOAN (
        MaGiaoDich NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        MaPTTT NVARCHAR(10) NOT NULL,
        SoTien DECIMAL(15,2) NOT NULL CHECK (SoTien >= 0),
        TrangThaiGiaoDich NVARCHAR(30) NOT NULL DEFAULT 'Chưa thanh toán'
            CHECK (TrangThaiGiaoDich IN ('Chưa thanh toán', 'Đã thanh toán', 'Thanh toán thất bại')),
        ThoiDiemTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ThoiDiemThanhToan DATETIME,
        MaNV_GhiNhan NVARCHAR(10),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaPTTT) REFERENCES PHUONGTHUCTHANHTOAN(MaPTTT) ON UPDATE CASCADE ON DELETE RESTRICT,
        FOREIGN KEY (MaNV_GhiNhan) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS YEUCAU_HUYDON (
        MaYCHuy NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        NguonHuy NVARCHAR(50) NOT NULL CHECK (NguonHuy IN ('Khách yêu cầu', 'Hệ thống/Giao thất bại')),
        LyDoHuy NVARCHAR(255),
        TrangThaiYCHuy NVARCHAR(30) NOT NULL DEFAULT 'Chờ kiểm tra'
            CHECK (TrangThaiYCHuy IN ('Chờ kiểm tra', 'Được phép hủy', 'Từ chối hủy', 'Đã hủy hoàn tất')),
        ThoiDiemYeuCau DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        MaNV_XuLy NVARCHAR(10),
        ThoiDiemXuLy DATETIME,
        LyDoTuChoi NVARCHAR(255),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaNV_XuLy) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS YEUCAU_DOITRA (
        MaYCDoiTra NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        LoaiYeuCau NVARCHAR(20) NOT NULL CHECK (LoaiYeuCau IN ('Đổi hàng', 'Trả hàng')),
        LyDoDoiTra NVARCHAR(500) NOT NULL,
        HinhAnhChungMinh NVARCHAR(255),
        TrangThaiYeuCau NVARCHAR(30) NOT NULL DEFAULT 'Chờ xác nhận'
            CHECK (TrangThaiYeuCau IN ('Chờ xác nhận', 'Đã chấp nhận', 'Hoàn tất')),
        LaHaiDonDau INT NOT NULL DEFAULT 0 CHECK (LaHaiDonDau IN (0, 1)),
        PhiVanChuyenDoiTra DECIMAL(15,2) NOT NULL DEFAULT 0 CHECK (PhiVanChuyenDoiTra >= 0),
        MaNV_XuLy NVARCHAR(10),
        ThoiDiemYeuCau DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ThoiDiemXuLy DATETIME,
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaNV_XuLy) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS GIAODICH_HOANTIEN (
        MaHoanTien NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        NguonHoanTien NVARCHAR(30) NOT NULL CHECK (NguonHoanTien IN ('Hủy đơn', 'Đổi/trả')),
        MaYCHuy NVARCHAR(10),
        MaYCDoiTra NVARCHAR(10),
        SoTienDaThanhToan DECIMAL(15,2) NOT NULL CHECK (SoTienDaThanhToan > 0),
        SoTienHoan DECIMAL(15,2) NOT NULL CHECK (SoTienHoan > 0 AND SoTienHoan <= SoTienDaThanhToan),
        TrangThaiHoan NVARCHAR(20) NOT NULL DEFAULT 'Đang xử lý' CHECK (TrangThaiHoan IN ('Đang xử lý', 'Đã hoàn', 'Thất bại')),
        ThoiDiemHoan DATETIME,
        MaNV_ThucHien NVARCHAR(10),
        GhiChu NVARCHAR(255),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaYCHuy) REFERENCES YEUCAU_HUYDON(MaYCHuy) ON UPDATE CASCADE ON DELETE SET NULL,
        FOREIGN KEY (MaYCDoiTra) REFERENCES YEUCAU_DOITRA(MaYCDoiTra) ON UPDATE CASCADE ON DELETE SET NULL,
        FOREIGN KEY (MaNV_ThucHien) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    # =====================================================
    # PHẦN V. MODULE 5: GIAO HÀNG & THÔNG BÁO
    # =====================================================
    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS GIAOHANG (
        MaGiaoHang NVARCHAR(10) PRIMARY KEY,
        MaDH NVARCHAR(10) NOT NULL,
        LanGiao INT NOT NULL DEFAULT 1 CHECK (LanGiao BETWEEN 1 AND 3),
        HinhThucGiao NVARCHAR(30) NOT NULL CHECK (HinhThucGiao IN ('Xe tải nội bộ', 'Shipper giao nhanh', 'ĐVVC TMĐT')),
        DonViVanChuyen NVARCHAR(100) NOT NULL,
        SDTShipper NVARCHAR(15),
        MaVanDon NVARCHAR(50),
        ThoiDiemBanGiao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        KetQuaGiao NVARCHAR(30) NOT NULL DEFAULT 'Đang giao' CHECK (KetQuaGiao IN ('Đang giao', 'Thành công', 'Thất bại', 'Khách từ chối nhận')),
        ThoiDiemGiaoXong DATETIME,
        LyDoThatBai NVARCHAR(255),
        PhiPhatSinh DECIMAL(15,2) NOT NULL DEFAULT 0 CHECK (PhiPhatSinh >= 0),
        MaNV_XacNhan NVARCHAR(10),
        CONSTRAINT UQ_GIAOHANG UNIQUE (MaDH, LanGiao),
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaNV_XacNhan) REFERENCES NHANVIEN(MaNV) ON UPDATE CASCADE ON DELETE SET NULL
    );
    """)

    con_tro.execute("""
    CREATE TABLE IF NOT EXISTS THONGBAO_DONHANG (
        MaThongBao NVARCHAR(10) PRIMARY KEY,
        MaKH NVARCHAR(10) NOT NULL,
        MaDH NVARCHAR(10) NOT NULL,
        TieuDe NVARCHAR(150) NOT NULL,
        NoiDung NVARCHAR(500) NOT NULL,
        LoaiThongBao NVARCHAR(50) NOT NULL CHECK (LoaiThongBao IN ('Xác nhận đơn', 'Thiếu hàng', 'Giao hàng', 'Giao thất bại')),
        DaDoc INT NOT NULL DEFAULT 0 CHECK (DaDoc IN (0, 1)),
        ThoiDiemGui DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (MaKH) REFERENCES KHACHHANG(MaKH) ON UPDATE CASCADE ON DELETE CASCADE,
        FOREIGN KEY (MaDH) REFERENCES DONHANG(MaDH) ON UPDATE CASCADE ON DELETE CASCADE
    );
    """)

    print("[+] Đang nạp dữ liệu mẫu (10 dòng/bảng)...")

    # =====================================================
    # NẠP DỮ LIỆU MẪU (10 DÒNG KHỚP CÁC BẢNG)
    # =====================================================
    # =====================================================
    # DỮ LIỆU MẪU MODULE 1
    # Lưu ý: dữ liệu dưới đây chỉ phục vụ demo/test hệ thống
    # =====================================================

    # 1. TAIKHOAN
    con_tro.executemany("""
        INSERT INTO TAIKHOAN
        (MaTK, Email, SoDienThoai, MatKhau, VaiTro, TrangThai)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        ('TK001', 'vy.tran@quythubakery.vn', '0905000001', 'demo_password_hash', 'MANAGER', 'ACTIVE'),
        ('TK002', 'hung.nguyen@quythubakery.vn', '0905000002', 'demo_password_hash', 'EMPLOYEE', 'ACTIVE'),
        ('TK003', 'thao.le@quythubakery.vn', '0905000003', 'demo_password_hash', 'EMPLOYEE', 'ACTIVE'),

        ('TK004', 'nhung.pham@gmail.com', '0973851052', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK005', 'minhchau.food@gmail.com', '0905777999', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK006', 'banhngoclan@gmail.com', '0912888777', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK007', 'thuanphat.dn@gmail.com', '0978456123', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK008', 'khoa.nguyen@gmail.com', '0868111222', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK009', 'hoangmai.le@gmail.com', '0935222333', 'demo_password_hash', 'CUSTOMER', 'ACTIVE'),
        ('TK010', 'thuylinh.vu@gmail.com', '0933654321', 'demo_password_hash', 'CUSTOMER', 'LOCKED')
    ])

    # 2. LOAIKHACHHANG
    con_tro.executemany("""
        INSERT INTO LOAIKHACHHANG
        (MaLoaiKH, TenLoaiKH, MoTa)
        VALUES (?, ?, ?)
    """, [
        ('LKH001', 'Khách lẻ', 'Khách hàng mua lẻ'),
        ('LKH002', 'Khách sỉ', 'Khách hàng mua sỉ')
    ])

    # 3. KHACHHANG
    con_tro.executemany("""
        INSERT INTO KHACHHANG
        (MaKH, MaTK, MaLoaiKH, HoTen, TrangThai)
        VALUES (?, ?, ?, ?, ?)
    """, [
        ('KH001', 'TK004', 'LKH001', 'Phạm Hồng Nhung', 'ACTIVE'),
        ('KH002', 'TK005', 'LKH002', 'Đại lý Bánh Minh Châu', 'ACTIVE'),
        ('KH003', 'TK006', 'LKH002', 'Cửa hàng Bánh Ngọc Lan', 'ACTIVE'),
        ('KH004', 'TK007', 'LKH002', 'Công ty Thuận Phát', 'ACTIVE'),
        ('KH005', 'TK008', 'LKH002', 'Nguyễn Văn Khoa', 'ACTIVE'),
        ('KH008', 'TK009', 'LKH001', 'Lê Hoàng Mai', 'ACTIVE'),
        ('KH010', 'TK010', 'LKH001', 'Vũ Thùy Linh', 'ACTIVE')
    ])

    # 4. NHANVIEN
    con_tro.executemany("""
        INSERT INTO NHANVIEN
        (MaNV, MaTK, HoTen, SoDienThoai, TrangThai)
        VALUES (?, ?, ?, ?, ?)
    """, [
        ('NV001', 'TK001', 'Trần Thị Yến Vy', '0905000001', 'ACTIVE'),
        ('NV002', 'TK002', 'Nguyễn Văn Hùng', '0905000002', 'ACTIVE'),
        ('NV003', 'TK003', 'Lê Thị Thu Thảo', '0905000003', 'ACTIVE')
    ])

    # 5. DIACHIKH
    con_tro.executemany("""
        INSERT INTO DIACHIKH
        (
            MaDiaChi, MaKH, TenNguoiNhan, SoDienThoai,
            DiaChiChiTiet, PhuongXa, QuanHuyen, TinhThanh, MacDinh
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('DC001', 'KH001', 'Phạm Hồng Nhung', '0973851052',
         '123 Nguyễn Tất Thành', 'Thanh Khê Tây', 'Thanh Khê', 'Đà Nẵng', 1),

        ('DC002', 'KH002', 'Cửa hàng Minh Châu', '0905777999',
         '45 Hùng Vương', 'Hải Châu 1', 'Hải Châu', 'Đà Nẵng', 1),

        ('DC003', 'KH003', 'Nguyễn Ngọc Lan', '0912888777',
         '88 Lê Lợi', 'Hải Châu 1', 'Hải Châu', 'Đà Nẵng', 1),

        ('DC004', 'KH003', 'Chi nhánh Hội An', '0912888777',
         '15 Phan Chu Trinh', 'Minh An', 'Hội An', 'Quảng Nam', 0),

        ('DC005', 'KH004', 'Kho Thuận Phát', '0978456123',
         'KCN Hòa Khánh', 'Hòa Khánh Bắc', 'Liên Chiểu', 'Đà Nẵng', 1),

        ('DC006', 'KH005', 'Nguyễn Văn Khoa', '0868111222',
         '204 Trần Phú', 'Phước Ninh', 'Hải Châu', 'Đà Nẵng', 1),

        ('DC007', 'KH008', 'Lê Hoàng Mai', '0935222333',
         '78 Núi Thành', 'Hòa Cường Bắc', 'Hải Châu', 'Đà Nẵng', 1),

        ('DC008', 'KH010', 'Vũ Thùy Linh', '0933654321',
         '89 Hà Huy Tập', 'Xuân Hà', 'Thanh Khê', 'Đà Nẵng', 1)
    ])

    # 6. LICHSU_KHACHHANG
    con_tro.executemany("""
        INSERT INTO LICHSU_KHACHHANG
        (
            MaLichSu, MaKH, MaNguoiThucHien,
            LoaiThayDoi, NoiDungCu, NoiDungMoi
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        (
            'LS001',
            'KH001',
            'TK004',
            'PROFILE_UPDATE',
            'Số điện thoại cũ',
            'Cập nhật thông tin hồ sơ'
        ),
        (
            'LS002',
            'KH002',
            'TK001',
            'CUSTOMER_TYPE',
            'Khách lẻ',
            'Khách sỉ'
        ),
        (
            'LS003',
            'KH010',
            'TK001',
            'ACCOUNT_LOCK',
            'ACTIVE',
            'LOCKED'
        )
    ])

    # =====================================================
    # DỮ LIỆU MẪU MODULE 2
    # Lưu ý: barcode và giá chỉ phục vụ demo/test
    # =====================================================

    # 7. DANHMUCSANPHAM
    con_tro.executemany("""
        INSERT INTO DANHMUCSANPHAM
        (MaDM, TenDM, MoTa, TrangThai)
        VALUES (?, ?, ?, ?)
    """, [
        (
            'DM001',
            'Bánh dừa nướng',
            'Các sản phẩm bánh dừa nướng Quý Thu',
            'ACTIVE'
        )
    ])

    # 8. SANPHAM
    con_tro.executemany("""
        INSERT INTO SANPHAM
        (MaSP, MaDM, TenSP, MoTa, TrangThai)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (
            'SP001',
            'DM001',
            'Bánh dừa nướng Quý Thu',
            'Sản phẩm bánh dừa nướng Quý Thu',
            'ACTIVE'
        )
    ])

    # 9. BIENTHE_SANPHAM
    # Các dòng dưới đây chỉ là dữ liệu demo, không đại diện
    # cho danh sách 12 barcode thực tế của doanh nghiệp.
    con_tro.executemany("""
        INSERT INTO BIENTHE_SANPHAM
        (
            MaBienTheSP, MaSP, HuongVi, QuyCach,
            BarCode, GiaBanLe, GiaBanSi, TrangThai
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ('BT001', 'SP001', 'Truyền thống', '120g',
         tao_ean13(1), 55000, 42000, 'ACTIVE'),

        ('BT002', 'SP001', 'Truyền thống', '125g',
         tao_ean13(2), 60000, 45000, 'ACTIVE'),

        ('BT003', 'SP001', 'Truyền thống', '150g',
         tao_ean13(3), 65000, 50000, 'ACTIVE'),

        ('BT004', 'SP001', 'Truyền thống', '225g',
         tao_ean13(4), 90000, 70000, 'ACTIVE'),

        ('BT005', 'SP001', 'Mè đen', '120g',
         tao_ean13(5), 60000, 47000, 'ACTIVE'),

        ('BT006', 'SP001', 'Gừng', '120g',
         tao_ean13(6), 60000, 47000, 'ACTIVE')
    ])

    # 10. HINHANH_SANPHAM
    con_tro.executemany("""
        INSERT INTO HINHANH_SANPHAM
        (MaHinhAnh, MaSP, DuongDan, AnhChinh, ThuTu)
        VALUES (?, ?, ?, ?, ?)
    """, [
        (
            'HA001',
            'SP001',
            'products/banh-dua-nuong-quy-thu.jpg',
            1,
            1
        )
    ])
    # =====================================================
    # DỮ LIỆU MẪU MODULE 3
    # =====================================================

    # GIOHANG
    con_tro.executemany("""
        INSERT INTO GIOHANG
        (MaGioHang, MaKH)
        VALUES (?, ?)
    """, [
        ('CART001', 'KH001'),
        ('CART002', 'KH003'),
        ('CART003', 'KH008')
    ])

    # CT_GIOHANG
    con_tro.executemany("""
        INSERT INTO CT_GIOHANG
        (MaCTGH, MaGioHang, MaBienTheSP, SoLuong)
        VALUES (?, ?, ?, ?)
    """, [
        ('CG001', 'CART001', 'BT001', 2),
        ('CG002', 'CART001', 'BT005', 1),
        ('CG003', 'CART002', 'BT003', 5),
        ('CG004', 'CART003', 'BT006', 2)
    ])
    # 8. PHUONGTHUCTHANHTOAN
    con_tro.executemany("INSERT INTO PHUONGTHUCTHANHTOAN VALUES (?, ?, ?, ?, ?)", [
        ('PT001', 'Chuyển khoản', 'VCB 0041000888999 - Banh Dua Quy Thu', 1, 'Ghi nội dung: Mã đơn hàng'),
        ('PT002', 'COD', None, 1, 'Thanh toán trực tiếp cho bưu tá khi nhận hàng')
    ])

    # 9. DONHANG
    # Dữ liệu phục vụ demo/test luồng xử lý đơn hàng
    con_tro.executemany("""
        INSERT INTO DONHANG
        (
            MaDH, MaKH, MaLoaiKH_ApDung,
            HoTenNguoiNhan, SDTNguoiNhan, DiaChiGiaoHang,
            TongTienHang, PhiVanChuyen, TinhGiao, TongThanhToan,
            MaPTTT, TrangThaiThanhToan, TrangThaiDonHang,
            GhiChu, NgayDat, MaNV_XacNhan,
            ThoiDiemBatDauChuanBi, SoLanGiaoLai,
            ThoiDiemGiaoThanhCong, ThoiDiemXacNhanNhanHang,
            ThoiDiemHoanThanh
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, [
        (
            'DH001', 'KH001', 'LKH001',
            'Phạm Hồng Nhung', '0973851052',
            '123 Nguyễn Tất Thành, Đà Nẵng',
            110000, 30000, 'Đà Nẵng', 140000,
            'PT002', 'Chưa thanh toán', 'Chờ xác nhận',
            None, '2026-10-04 08:12:45',
            None, None, 0, None, None, None
        ),

        (
            'DH002', 'KH002', 'LKH002',
            'Cửa hàng Minh Châu', '0905777999',
            '45 Hùng Vương, Đà Nẵng',
            840000, 50000, 'Đà Nẵng', 890000,
            'PT001', 'Đã thanh toán', 'Đã xác nhận',
            None, '2026-10-03 09:20:00',
            'NV001', None, 0, None, None, None
        ),

        (
            'DH003', 'KH003', 'LKH002',
            'Nguyễn Ngọc Lan', '0912888777',
            '88 Lê Lợi, Đà Nẵng',
            500000, 50000, 'Đà Nẵng', 550000,
            'PT001', 'Đã thanh toán', 'Đang chuẩn bị hàng',
            None, '2026-10-02 10:00:00',
            'NV002', '2026-10-02 10:30:00',
            0, None, None, None
        ),

        (
            'DH004', 'KH004', 'LKH002',
            'Kho Thuận Phát', '0978456123',
            'KCN Hòa Khánh, Đà Nẵng',
            700000, 50000, 'Đà Nẵng', 750000,
            'PT001', 'Đã thanh toán', 'Chờ bổ sung hàng',
            'Dự kiến bổ sung hàng trong 1-2 ngày.',
            '2026-10-02 11:00:00',
            'NV001', '2026-10-02 11:30:00',
            0, None, None, None
        ),

        (
            'DH005', 'KH008', 'LKH001',
            'Lê Hoàng Mai', '0935222333',
            '78 Núi Thành, Đà Nẵng',
            120000, 30000, 'Đà Nẵng', 150000,
            'PT002', 'Chưa thanh toán', 'Sẵn sàng giao',
            None, '2026-10-01 08:30:00',
            'NV002', '2026-10-01 09:00:00',
            0, None, None, None
        ),

        (
            'DH006', 'KH010', 'LKH001',
            'Vũ Thùy Linh', '0933654321',
            '89 Hà Huy Tập, Đà Nẵng',
            180000, 30000, 'Đà Nẵng', 210000,
            'PT002', 'Chưa thanh toán', 'Đang giao',
            None, '2026-09-30 08:00:00',
            'NV001', '2026-09-30 09:00:00',
            0, None, None, None
        )
    ])

    # 10. CT_DONHANG
    con_tro.executemany("""
        INSERT INTO CT_DONHANG
        (
            MaCTDH, MaDH, MaBienTheSP,
            SoLuong, LoaiGiaApDung, DonGia, ThanhTien
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        # DH001: khách lẻ
        ('CT001', 'DH001', 'BT001', 2, 'Giá lẻ', 55000, 110000),

        # DH002: khách sỉ
        ('CT002', 'DH002', 'BT001', 20, 'Giá sỉ', 42000, 840000),

        # DH003: khách sỉ
        ('CT003', 'DH003', 'BT003', 10, 'Giá sỉ', 50000, 500000),

        # DH004: khách sỉ
        ('CT004', 'DH004', 'BT004', 10, 'Giá sỉ', 70000, 700000),

        # DH005: khách lẻ
        ('CT005', 'DH005', 'BT005', 2, 'Giá lẻ', 60000, 120000),

        # DH006: khách lẻ
        ('CT006', 'DH006', 'BT006', 3, 'Giá lẻ', 60000, 180000)
    ])

    # 11. GIAOHANG
    # Tạm giữ để phục vụ dữ liệu giao hàng của M3.
    # Vị trí module chính thức sẽ được chốt khi thiết kế hoàn chỉnh M3-M5.
    con_tro.executemany("""
        INSERT INTO GIAOHANG
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            'GH001', 'DH006', 1,
            'Shipper giao nhanh',
            'Nguyễn Văn Tâm',
            '0905321321',
            'GHN123456789',
            '2026-09-30 10:00:00',
            'Đang giao',
            None,
            None,
            0,
            'NV001'
        )
    ])

    # 12. THONGBAO_DONHANG
    # Tạm giữ, sẽ xem lại khi thiết kế hoàn chỉnh M3-M5.
    con_tro.executemany("""
        INSERT INTO THONGBAO_DONHANG
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (
            'TB001',
            'KH001',
            'DH001',
            'Đơn hàng tiếp nhận',
            'Đơn DH001 đang chờ xác nhận.',
            'Xác nhận đơn',
            0,
            '2026-10-04 08:15:00'
        ),

        (
            'TB002',
            'KH004',
            'DH004',
            'Đơn hàng tạm chậm',
            'Đơn DH004 đang chờ bổ sung hàng.',
            'Thiếu hàng',
            0,
            '2026-10-02 11:35:00'
        )
    ])

    # =====================================================
    # LƯU VÀ HOÀN TẤT
    # =====================================================
    ket_noi.commit()

    # Kiểm tra danh sách các bảng đã tạo trong SQLite
    con_tro.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    danh_sach_bang = con_tro.fetchall()

    print("\n[+] DANH SÁCH BẢNG ĐÃ TẠO THÀNH CÔNG TRONG CSDL:")
    for i, bang in enumerate(danh_sach_bang, start=1):
        # Đếm số dòng dữ liệu trong từng bảng
        con_tro.execute(f"SELECT COUNT(*) FROM {bang[0]};")
        so_dong = con_tro.fetchone()[0]
        print(f"    {i:02d}. Bảng: {bang[0]:<22} -> ({so_dong} dòng dữ liệu)")

    ket_noi.close()

    duong_dan = os.path.abspath(TEN_FILE_CSDL)
    print("\n" + "=" * 70)
    print(" [✓] HOÀN TẤT! ĐÃ TẠO XONG FILE CƠ SỞ DỮ LIỆU SQLITE:")
    print(f"     -> {duong_dan}")
    print(" [✓] Bạn có thể mở DB Browser for SQLite để xem cấu trúc và dữ liệu.")
    print("=" * 70)


# =========================================================
# CHẠY CHƯƠNG TRÌNH
# =========================================================
if __name__ == '__main__':
    tao_csdl_qlbh()