# Quý Thu Online Sales Management

Hệ thống bán hàng trực tuyến và quản lý vận hành cửa hàng Quý Thu, xây dựng bằng Django. Dự án gồm giao diện cửa hàng cho khách hàng và các màn hình nghiệp vụ cho Nhân viên, Quản lý.

## 1. Yêu cầu môi trường

Hướng dẫn chạy nhanh bên dưới dành cho Windows:

- Windows 10/11.
- Python 3.12 và Windows Python Launcher (`py`). Kiểm tra trong PowerShell:

  ```powershell
  py -3.12 --version
  ```

- Git để clone/cập nhật mã nguồn.
- Kết nối Internet khi cài dependencies lần đầu.

Ứng dụng dùng SQLite trong môi trường phát triển, không cần cài riêng máy chủ cơ sở dữ liệu. `run.bat` sẽ tạo môi trường ảo `.venv` trong thư mục dự án, không cài thư viện vào Python toàn hệ thống.

## 2. Clone và chạy website

Mở PowerShell tại thư mục muốn lưu dự án, sau đó chạy:

```powershell
git clone --branch feature/customer-storefront-workflows --single-branch https://github.com/minhductruongvan/quythu-online-sales-management.git
Set-Location quythu-online-sales-management
```

Nếu đã clone repository nhưng chưa có nhánh hướng dẫn ở máy, chạy một lần:

```powershell
git fetch origin
git switch --track origin/feature/customer-storefront-workflows
```

Nếu nhánh đã tồn tại ở máy, chuyển sang nhánh đó bằng `git switch feature/customer-storefront-workflows`. Những lần cập nhật sau, chạy `git pull` trong thư mục dự án trước khi khởi động lại website.

Tại thư mục gốc dự án, chạy một trong hai cách:

```powershell
.\run.bat
```

Hoặc nhấp đúp `run.bat` trong File Explorer. Khi chạy, tập lệnh sẽ:

1. Tạo `.venv` bằng Python 3.12 nếu môi trường ảo chưa tồn tại.
2. Cài hoặc kiểm tra thư viện trong `requirements.txt`.
3. Tạo/cập nhật schema SQLite bằng các migration.
4. Tạo tài khoản mẫu, catalog sản phẩm và dữ liệu bán hàng mẫu.
5. Khởi động Django development server tại `http://127.0.0.1:8000/` và mở website trên trình duyệt.

Giữ cửa sổ đang chạy server mở trong khi sử dụng website. Nhấn `Ctrl+C` trong cửa sổ đó để dừng server. Nếu trình duyệt không tự mở, truy cập thủ công `http://127.0.0.1:8000/`.

Có thể chạy lại `run.bat` để khởi động lại dự án. Migration và các lệnh seed dùng `get_or_create` cho dữ liệu mẫu nên không tạo thêm bản sao khi chạy lại. Riêng lệnh seed tài khoản mẫu sẽ đặt lại mật khẩu của các tài khoản demo mỗi lần chạy.

### Cài đặt và chạy thủ công

Nếu không muốn dùng `run.bat`, chạy các lệnh sau từ thư mục gốc:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate --noinput
..\.venv\Scripts\python.exe manage.py seed_m1_demo_accounts
..\.venv\Scripts\python.exe manage.py seed_demo_catalog
..\.venv\Scripts\python.exe manage.py seed_demo_sales
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Mở `http://127.0.0.1:8000/` trong trình duyệt. Các lệnh seed chỉ hoạt động khi `DJANGO_DEBUG=True`; đây là cấu hình mặc định cho phát triển cục bộ.

## 3. Tài khoản mẫu

Đăng nhập tại `http://127.0.0.1:8000/tai-khoan/dang-nhap/`:

| Vai trò | Email |
|---|---|
| Khách hàng | `khachhang@gmail.com` |
| Nhân viên | `nhanvien@gmail.com` |
| Quản lý | `quanly@gmail.com` |

Mật khẩu mặc định của cả ba tài khoản là `Quythu123!`. Có thể đặt `M1_DEMO_PASSWORD` trong tệp `.env` ở thư mục gốc để dùng mật khẩu khác. Tài khoản demo chỉ dành cho phát triển và thử nghiệm; không dùng trên hệ thống triển khai thực tế.

Các lệnh seed tạo 10 sản phẩm mẫu, 8 hồ sơ khách hàng thử nghiệm và các đơn hàng minh họa ở nhiều trạng thái. Các bản ghi mẫu được lưu trong `backend/db.sqlite3` và tồn tại qua những lần khởi động tiếp theo.

## 4. Các luồng chức năng

- **Khách hàng:** xem sản phẩm, đăng ký/đăng nhập, cập nhật hồ sơ và địa chỉ, mua hàng, theo dõi đơn và gửi yêu cầu hậu mãi.
- **Nhân viên:** quản lý hồ sơ khách hàng, sản phẩm, đơn hàng và yêu cầu hậu mãi.
- **Quản lý:** sử dụng các chức năng vận hành như Nhân viên, quản lý vai trò tài khoản nội bộ và xem/xuất báo cáo. Chức năng báo cáo chỉ dành cho Quản lý.

Một luồng mua hàng cơ bản: chọn sản phẩm → thêm vào giỏ → thanh toán → theo dõi đơn. Nhân viên xử lý đơn hàng tại `/don-hang/`; khách hàng xem lịch sử mua hàng và đơn của mình trong khu vực tài khoản.

## 5. Kiểm tra dự án

Từ thư mục gốc, chạy:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py test
```

`check` kiểm tra cấu hình Django; `makemigrations --check --dry-run` xác nhận model không có migration chưa tạo; `test` chạy toàn bộ bộ kiểm thử. Bộ test dùng cơ sở dữ liệu tạm và không xóa dữ liệu đang có trong `backend/db.sqlite3`.

## 6. Cấu hình môi trường và email

Django đọc biến môi trường và tệp `.env` ở thư mục gốc. Tệp `.env.example` là mẫu tham khảo; không bắt buộc phải tạo `.env` để chạy website cục bộ.

Các thiết lập chính:

- `DJANGO_DEBUG`: mặc định `True` khi không khai báo. Giữ `True` khi chạy `run.bat`, vì các lệnh tạo dữ liệu mẫu chỉ chạy trong chế độ phát triển.
- `DJANGO_ALLOWED_HOSTS`: danh sách host phân tách bằng dấu phẩy.
- `DJANGO_SECRET_KEY`: khi chạy với `DJANGO_DEBUG=False`, phải đặt khóa riêng, đủ an toàn.
- `M1_DEMO_PASSWORD`: mật khẩu tùy chọn cho ba tài khoản mẫu.

Để bật gửi email OTP đặt lại mật khẩu bằng Gmail:

1. Bật Xác minh 2 bước cho tài khoản Google và tạo Mật khẩu ứng dụng.
2. Tạo tệp cấu hình từ PowerShell tại thư mục gốc:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Điền `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` và `DEFAULT_FROM_EMAIL` trong `.env`; dùng Mật khẩu ứng dụng, không dùng mật khẩu đăng nhập Google thông thường.
4. Khởi động lại server để nạp cấu hình.

Khi chưa cấu hình SMTP trong môi trường phát triển, OTP được in trong terminal đang chạy server. OTP hết hạn sau 5 phút và chỉ dùng một lần. SMS Viettel hiện chưa được bật.

Không đưa `.env`, mật khẩu thật hoặc khóa bí mật lên Git. `.env` và cơ sở dữ liệu SQLite đã được loại khỏi Git bằng `.gitignore`. Cấu hình mặc định chỉ phục vụ phát triển cục bộ; không dùng `run.bat`, tài khoản demo hoặc Django development server để triển khai production.

## 7. Xử lý sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `py` không được nhận diện hoặc không tạo được môi trường ảo | Cài Python 3.12, bật tùy chọn cài Python Launcher, rồi mở lại PowerShell/Command Prompt. Kiểm tra bằng `py -3.12 --version`. |
| Cài dependencies thất bại | Kiểm tra Internet, sau đó chạy lại `run.bat`; lỗi cài đặt sẽ được hiển thị trong cửa sổ. |
| `ModuleNotFoundError` khi chạy thủ công | Chạy lại bước cài thư viện bằng `.venv\Scripts\python.exe -m pip install -r requirements.txt` từ thư mục gốc. |
| Báo lỗi migration hoặc chưa có bảng | Từ thư mục `backend`, chạy `..\.venv\Scripts\python.exe manage.py migrate --noinput`, sau đó chạy lại `run.bat`. |
| Cổng `8000` đã được sử dụng | Dừng server cũ bằng `Ctrl+C`. Nếu cần chạy cổng khác, dùng `..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8001` từ thư mục `backend`, rồi mở `http://127.0.0.1:8001/`. |
| Website không tự mở trình duyệt | Để server tiếp tục chạy và mở thủ công `http://127.0.0.1:8000/`. |
| Seed báo chỉ được chạy khi `DEBUG=True` | Kiểm tra `.env` và bảo đảm `DJANGO_DEBUG=True` khi chạy môi trường phát triển. |

Khi gặp lỗi khác, giữ lại phần thông báo trong terminal và xử lý lỗi đầu tiên xuất hiện; các lỗi phía sau có thể là hệ quả của lỗi khởi động ban đầu.
