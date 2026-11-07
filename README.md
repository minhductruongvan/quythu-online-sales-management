# Quý Thu Online Sales Management

Hệ thống quản lý bán hàng trực tuyến Quý Thu, xây dựng bằng Django.

## Chuẩn bị môi trường

Yêu cầu Python 3.12 trở lên và Git. Các lệnh dưới đây dùng PowerShell trên Windows:

```powershell
git clone --branch feature/customer-storefront-workflows https://github.com/minhductruongvan/quythu-online-sales-management.git
cd quythu-online-sales-management
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn kích hoạt môi trường ảo, có thể gọi trực tiếp `.\.venv\Scripts\python.exe` thay cho `python`.

## Chạy hệ thống

Từ thư mục dự án:

```powershell
cd backend
python manage.py migrate
python manage.py seed_m1_demo_accounts
python manage.py seed_demo_catalog
python manage.py seed_demo_sales
python manage.py runserver
```

Mở `http://127.0.0.1:8000/`. Cơ sở dữ liệu SQLite cục bộ được tạo tại `backend/db.sqlite3`; các lệnh seed chỉ thêm dữ liệu mẫu trong môi trường phát triển.

## Chạy kiểm thử

Từ thư mục `backend`:

```powershell
python manage.py test
```

## Tài khoản dùng thử

Khi chạy môi trường phát triển (`DEBUG=True`), lệnh tạo tài khoản mẫu đặt mật khẩu dùng thử là `Quythu123!`. Chạy lệnh từ thư mục `backend`:

```powershell
python manage.py seed_m1_demo_accounts
```

Tài khoản: `khachhang@gmail.com` (khách hàng), `nhanvien@gmail.com` (nhân viên) và `quanly@gmail.com` (quản lý). Lệnh chỉ chạy khi `DEBUG=True`; không dùng tài khoản mẫu cho môi trường triển khai.

## Khôi phục mật khẩu qua Gmail

Trang đăng nhập hỗ trợ gửi OTP đặt lại mật khẩu đến email khách hàng. Để gửi email thật bằng Gmail:

1. Bật Xác minh 2 bước cho tài khoản Google và tạo Mật khẩu ứng dụng.
2. Tại thư mục gốc dự án, chạy `Copy-Item .env.example .env`, rồi mở `.env` và điền địa chỉ Gmail cùng Mật khẩu ứng dụng vào `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL`. Không dùng mật khẩu đăng nhập Google thông thường hoặc đưa `.env` lên Git.
3. Khởi động lại Django server để nạp cấu hình.

Khi chưa cấu hình SMTP trong môi trường phát triển, email và OTP được in ra terminal đang chạy server. OTP hết hạn sau 5 phút, chỉ dùng một lần; yêu cầu gửi lại bị giới hạn theo thời gian. SMS Viettel chưa được bật.

## Luồng sử dụng

- Khách hàng có thể chọn loại khách lẻ hoặc khách sỉ khi đăng ký; lựa chọn được lưu vào hồ sơ và quyết định chính sách giá (giá sỉ chỉ áp dụng khi đạt số lượng tối thiểu của từng biến thể). Cả hai loại đều đăng nhập với vai trò khách hàng, không cấp quyền nhân viên/quản lý.
- Khách hàng có thể xem catalog, đăng ký/đăng nhập, quản lý địa chỉ, thêm biến thể vào giỏ, đặt hàng COD hoặc chuyển khoản giả lập, theo dõi đơn và gửi yêu cầu hậu mãi.
- Nhân viên xử lý đơn theo trạng thái, quản lý catalog, làm việc với yêu cầu hậu mãi và xem báo cáo; quản lý có các chức năng đó cùng phân quyền nhân viên và dashboard quản trị.
- Từ cửa hàng, khách chọn sản phẩm → giỏ hàng → thanh toán → theo dõi đơn. Nhân viên xử lý đơn trong `/don-hang/`; khách tìm đơn và hỗ trợ trong khu vực tài khoản.
- Nghiệp vụ và dữ liệu được lưu trong SQLite qua các model/migration Django hiện có; giao diện gọi API cùng dịch vụ nghiệp vụ thay vì tự tính giá hoặc tự đổi trạng thái.

`seed_demo_catalog` thêm 10 sản phẩm với nhiều quy cách và hương vị; `seed_demo_sales` tạo thêm 8 hồ sơ khách hàng, địa chỉ, 10 đơn hàng ở các trạng thái khác nhau và một yêu cầu hủy mẫu gắn với tài khoản khách hàng mẫu. Các lệnh chỉ chạy khi `DEBUG=True`, có thể chạy lặp lại và không ghi đè các bản ghi đã tồn tại. Người dùng mới có thể tự đăng ký trực tiếp trên website.
