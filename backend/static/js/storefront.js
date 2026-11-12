(() => {
    const csrf = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
    const money = value => `${new Intl.NumberFormat("vi-VN", { useGrouping: true, maximumFractionDigits: 0 }).format(Number(value || 0))} ₫`;
    const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
    // "15:59 08/11/2026" – một hàm định dạng ngày cho mọi trang M3
    const shortDate = value => value
        ? new Date(value).toLocaleString("vi-VN", { hour: "2-digit", minute: "2-digit", day: "2-digit", month: "2-digit", year: "numeric" })
        : "—";
    // Tên sản phẩm đã chứa hương vị (vd "Bánh dừa nướng vị sầu riêng") thì chỉ ghi quy cách, tránh lặp chữ
    const variantLabel = line => String(line.ten_sp).toLowerCase().includes(String(line.huong_vi).toLowerCase())
        ? line.quy_cach : `${line.huong_vi} · ${line.quy_cach}`;
    // Ô sản phẩm có ảnh, dùng chung cho giỏ hàng và trang thanh toán
    const productCell = line => `<div class="cart-product"><img src="${esc(line.anh)}" alt="" width="56" height="56" loading="lazy"><div><strong>${esc(line.ten_sp)}</strong><br><span>${esc(variantLabel(line))}</span></div></div>`;
    // Pill trạng thái: chờ khách/chờ hàng = vàng, đã hủy = đỏ
    const statusPill = order => {
        const waiting = ["CHO_THANH_TOAN", "CHO_BO_SUNG"].includes(order.trang_thai) && order.trang_thai_thanh_toan !== "DA_THANH_TOAN";
        const tone = order.trang_thai === "DA_HUY" ? "danger" : waiting ? "warning" : "";
        return `<span class="module-pill ${tone}">${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</span>`;
    };
    const afterSalesPill = order => order.ten_trang_thai_hau_mai
        ? `<span class="module-pill ${order.trang_thai_hau_mai === "CHO_HUY" ? "danger" : "warning"}">${esc(order.ten_trang_thai_hau_mai)}</span>`
        : "—";
    const message = (node, text, error = false) => {
        node.className = `module-alert${error ? " error" : " success"}`;
        node.textContent = text;
    };

    async function request(url, method = "GET", data = null) {
        const headers = { Accept: "application/json" };
        const options = { method, credentials: "same-origin", headers };
        // Django chặn mọi request ghi dữ liệu (POST/PATCH/DELETE) thiếu CSRF token, kể cả khi không gửi body
        if (method !== "GET") headers["X-CSRFToken"] = csrf();
        if (data !== null) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(data);
        }
        const response = await fetch(url, options);
        let body;
        try {
            body = await response.json();
        } catch {
            throw new Error("Máy chủ trả về phản hồi không hợp lệ.");
        }
        if (!response.ok) {
            const detail = body.errors
                ? Object.values(body.errors).flat().join(" ")
                : body.message || body.detail;
            throw new Error(detail || "Không thể hoàn tất thao tác.");
        }
        return body;
    }

    const queryFor = (ids, extra = {}) => {
        const query = new URLSearchParams();
        ids.forEach(id => query.append("chon", id));
        Object.entries(extra).forEach(([key, value]) => {
            if (value) query.set(key, value);
        });
        return query.toString();
    };

    async function setupCart(root) {
        const rows = root.querySelector("#cart-rows");
        const status = root.querySelector("#cart-message");
        const total = root.querySelector("#cart-total");
        const checkout = root.querySelector("#checkout-button");
        const selectAll = root.querySelector("#cart-select-all");
        const selectedCount = root.querySelector("#cart-selected-count");
        const selected = new Set();
        let cart = { cac_dong: [], tam_tinh: 0 };

        const load = async () => {
            const suffix = queryFor([...selected]);
            const result = await request(`${root.dataset.api}${suffix ? `?${suffix}` : ""}`);
            cart = result.data;
            if (!selected.size) {
                cart.cac_dong.filter(line => line.da_chon).forEach(line => selected.add(line.ma_ctgh));
            }
            const selectable = cart.cac_dong.filter(line => line.con_ban);
            rows.innerHTML = cart.cac_dong.length ? cart.cac_dong.map(line => `
                <tr>
                    <td><input type="checkbox" data-select="${esc(line.ma_ctgh)}" ${line.da_chon || selected.has(line.ma_ctgh) ? "checked" : ""} ${line.con_ban ? "" : "disabled"} aria-label="Chọn ${esc(line.ten_sp)}"></td>
                    <td>${productCell(line)}${line.con_ban ? "" : '<span class="module-pill danger">Ngừng kinh doanh</span>'}</td>
                    <td>${money(line.don_gia)}<br><small>${esc(line.ten_loai_gia)}</small></td>
                    <td class="cart-qty"><form class="module-inline-form" data-update="${esc(line.ma_ctgh)}"><button class="module-button secondary" type="button" data-step="-1" aria-label="Giảm số lượng">−</button><input type="number" min="1" name="so_luong" value="${line.so_luong}" data-current="${line.so_luong}" aria-label="Số lượng"><button class="module-button secondary" type="button" data-step="1" aria-label="Tăng số lượng">+</button></form></td>
                    <td><strong>${money(line.thanh_tien)}</strong></td>
                    <td><button class="module-button danger" type="button" data-delete="${esc(line.ma_ctgh)}">Xóa</button></td>
                </tr>`).join("") : '<tr><td colspan="6" class="module-empty">Giỏ hàng đang trống. Khám phá các sản phẩm Quý Thu để bắt đầu.</td></tr>';
            total.textContent = money(cart.tam_tinh);
            selectedCount.textContent = String(selected.size);
            selectAll.disabled = !selectable.length;
            selectAll.checked = selectable.length > 0 && selectable.every(line => selected.has(line.ma_ctgh));
            selectAll.indeterminate = selectable.some(line => selected.has(line.ma_ctgh)) && !selectAll.checked;
            checkout.disabled = !selected.size;
        };

        root.addEventListener("change", async event => {
            // Gõ số lượng rồi Enter hoặc bấm ra ngoài ô → gửi cập nhật luôn (không cần nút [Cập nhật])
            if (event.target.name === "so_luong") {
                event.target.form.requestSubmit();
                return;
            }
            if (event.target === selectAll) {
                selected.clear();
                if (selectAll.checked) {
                    cart.cac_dong.filter(line => line.con_ban).forEach(line => selected.add(line.ma_ctgh));
                }
                try { await load(); } catch (error) { message(status, error.message, true); }
                return;
            }
            const checkbox = event.target.closest("[data-select]");
            if (!checkbox) return;
            checkbox.checked ? selected.add(checkbox.dataset.select) : selected.delete(checkbox.dataset.select);
            try { await load(); } catch (error) { message(status, error.message, true); }
        });
        root.addEventListener("submit", async event => {
            const form = event.target.closest("[data-update]");
            if (!form) return;
            event.preventDefault();
            const input = form.querySelector('[name="so_luong"]');
            if (input.value === input.dataset.current) return;  // không đổi → không gửi (Enter + rời ô chỉ gửi 1 lần)
            input.dataset.current = input.value;
            try {
                const url = `${root.dataset.api}${encodeURIComponent(form.dataset.update)}/?${queryFor([...selected])}`;
                const result = await request(url, "PATCH", { so_luong: Number(new FormData(form).get("so_luong")) });
                message(status, result.message);
                await load();
            } catch (error) { message(status, error.message, true); }
        });
        root.addEventListener("click", async event => {
            const stepButton = event.target.closest("[data-step]");
            if (stepButton) {
                const quantity = stepButton.closest("form").querySelector('[name="so_luong"]');
                quantity.value = String(Math.max(1, Number(quantity.value) + Number(stepButton.dataset.step)));
                stepButton.closest("form").requestSubmit();
            }
            const button = event.target.closest("[data-delete]");
            if (button) {
                try {
                    await request(`${root.dataset.api}${encodeURIComponent(button.dataset.delete)}/?${queryFor([...selected])}`, "DELETE");
                    selected.delete(button.dataset.delete);
                    message(status, "Đã xóa sản phẩm khỏi giỏ.");
                    await load();
                } catch (error) { message(status, error.message, true); }
            }
            if (event.target.closest("#checkout-button")) {
                if (selected.size) location.assign(`/thanh-toan/?${queryFor([...selected])}`);
            }
        });
        try { await load(); } catch (error) { message(status, error.message, true); }
    }

    function setupAddToCart() {
        document.querySelectorAll(".js-add-to-cart").forEach(form => form.addEventListener("submit", async event => {
            event.preventDefault();
            const status = form.parentElement.querySelector(".js-form-message");
            const data = Object.fromEntries(new FormData(form).entries());
            try {
                const result = await request(form.dataset.api, "POST", {
                    ma_bien_the: data.ma_bien_the,
                    so_luong: Number(data.so_luong)
                });
                status.innerHTML = `<div class="module-alert success">${esc(result.message)} <a href="/gio-hang/">Mở giỏ hàng →</a></div>`;
            } catch (error) {
                status.innerHTML = `<div class="module-alert error">${esc(error.message)}</div>`;
            }
        }));
    }

    function setupProductVariantPicker() {
        document.querySelectorAll("[data-product-detail]").forEach(root => {
            const picker = root.querySelector("[data-product-variant-picker]");
            if (!picker) return;

            const update = () => {
                const option = picker.selectedOptions[0];
                if (!option) return;

                const retailPrice = root.querySelector("#product-retail-price");
                const wholesaleLine = root.querySelector("#product-wholesale-line");
                const wholesalePrice = root.querySelector("#product-wholesale-price");
                const wholesaleMinimum = root.querySelector("#product-wholesale-min");
                const selectedVariant = root.querySelector("[data-selected-variant]");

                if (retailPrice) retailPrice.textContent = money(option.dataset.retailPrice);
                if (selectedVariant) selectedVariant.value = option.value;
                root.querySelectorAll("[data-product-variant-select]").forEach(card => {
                    card.setAttribute(
                        "aria-pressed",
                        String(card.dataset.productVariantSelect === option.value),
                    );
                    const cardRetailPrice = card.querySelector("[data-product-variant-price]");
                    const cardWholesalePrice = card.querySelector("[data-product-variant-wholesale-price]");
                    if (cardRetailPrice) {
                        cardRetailPrice.textContent = money(card.dataset.productRetailPrice);
                    }
                    if (cardWholesalePrice) {
                        cardWholesalePrice.textContent = money(card.dataset.productWholesalePrice);
                    }
                });
                if (wholesaleLine) {
                    const hasWholesalePrice = Boolean(option.dataset.wholesalePrice);
                    wholesaleLine.hidden = !hasWholesalePrice;
                    if (wholesalePrice) {
                        wholesalePrice.textContent = hasWholesalePrice
                            ? money(option.dataset.wholesalePrice)
                            : "";
                    }
                    if (wholesaleMinimum) {
                        wholesaleMinimum.textContent = option.dataset.wholesaleMin || "";
                    }
                }
            };

            picker.addEventListener("change", update);
            root.querySelectorAll("[data-product-variant-select]").forEach(card => {
                card.addEventListener("click", () => {
                    picker.value = card.dataset.productVariantSelect;
                    picker.dispatchEvent(new Event("change", { bubbles: true }));
                });
            });
            update();
        });
    }

    function setupProductGallery() {
        document.querySelectorAll("[data-product-gallery]").forEach(gallery => {
            const mainImage = gallery.querySelector("[data-product-main-image]");
            if (!mainImage) return;
            gallery.addEventListener("click", event => {
                const thumbnail = event.target.closest("[data-product-image]");
                if (!thumbnail) return;
                mainImage.src = thumbnail.dataset.productImage;
                mainImage.alt = thumbnail.dataset.imageAlt || mainImage.alt;
                gallery.querySelectorAll("[data-product-image]").forEach(image => {
                    image.setAttribute("aria-pressed", String(image === thumbnail));
                });
            });
        });
    }

    async function setupCheckout(root) {
        const status = root.querySelector("#checkout-message");
        const addressSelect = root.querySelector("#checkout-address");
        const addressDialog = root.querySelector("#checkout-address-dialog");
        const addressForm = root.querySelector("#checkout-address-form");
        const addressFormMessage = root.querySelector("#checkout-address-form-message");
        const selected = [...new URLSearchParams(location.search).getAll("chon")];
        let addressList = [];
        let payment = "";

        const addressText = item => [
            item.dia_chi_chi_tiet, item.phuong_xa, item.quan_huyen, item.tinh_thanh
        ].filter(Boolean).join(", ");
        const load = async preferredAddress => {
            if (!selected.length) throw new Error("Bạn chưa chọn sản phẩm cần thanh toán.");
            const addressResult = await request(root.dataset.addressApi);
            addressList = Array.isArray(addressResult.data) ? addressResult.data : addressResult.data?.ket_qua || [];
            const preferred = preferredAddress || addressSelect.value || addressList.find(item => item.mac_dinh)?.ma_dia_chi || addressList[0]?.ma_dia_chi;
            addressSelect.innerHTML = addressList.map(item =>
                `<option value="${esc(item.ma_dia_chi)}" ${String(item.ma_dia_chi) === String(preferred) ? "selected" : ""}>${esc(item.ten_nguoi_nhan)} · ${esc(item.so_dien_thoai)} · ${esc(addressText(item))}</option>`
            ).join("");
            addressSelect.disabled = !addressList.length;
            root.querySelector("#checkout-no-address").hidden = addressList.length > 0;

            let orderData;
            if (addressList.length) {
                const query = queryFor(selected, { ma_dia_chi: addressSelect.value });
                orderData = (await request(`${root.dataset.api}?${query}`)).data;
            } else {
                orderData = (await request(`${root.dataset.cartApi}?${queryFor(selected)}`)).data;
            }

            const lines = orderData.cac_dong || [];
            root.querySelector("#checkout-items").innerHTML = `<div class="module-table-wrap"><table class="module-table checkout-lines"><thead><tr><th>Sản phẩm</th><th>Đơn giá</th><th class="num">SL</th><th class="num">Thành tiền</th></tr></thead><tbody>
                ${lines.map(line => `<tr><td>${productCell(line)}</td><td>${money(line.don_gia)}<br><small>${esc(line.ten_loai_gia)}</small></td><td class="num">${line.so_luong}</td><td class="num"><strong>${money(line.thanh_tien)}</strong></td></tr>`).join("")}
                </tbody></table></div>`;
            root.querySelector("#checkout-subtotal").textContent = money(orderData.tong_tien_hang ?? orderData.tam_tinh);
            root.querySelector("#checkout-shipping").textContent = addressList.length ? money(orderData.phi_van_chuyen) : "Thêm địa chỉ để tính";
            root.querySelector("#checkout-total").textContent = addressList.length ? money(orderData.tong_thanh_toan) : "—";
            const paymentContainer = root.querySelector("#checkout-payments");
            if (addressList.length) {
                const defaultPayment = orderData.cac_phuong_thuc.find(item => item.ma_pttt === "PT002")
                    || orderData.cac_phuong_thuc[0];
                paymentContainer.innerHTML = orderData.cac_phuong_thuc.map(item =>
                    `<label class="module-panel"><input type="radio" name="payment" value="${esc(item.ma_pttt)}" ${String(item.ma_pttt) === String(payment) || (!payment && item.ma_pttt === defaultPayment?.ma_pttt) ? "checked" : ""}> ${esc(item.ten_pttt)}${item.ghi_chu_huong_dan ? `<br><small>${esc(item.ghi_chu_huong_dan)}</small>` : ""}</label>`
                ).join("");
                payment = root.querySelector('[name="payment"]:checked')?.value || "";
            } else {
                paymentContainer.innerHTML = '<p class="module-muted">Chọn địa chỉ giao hàng để xem phương thức thanh toán.</p>';
                payment = "";
            }
            root.querySelector("#place-order-button").disabled = !addressList.length || !payment;
        };

        addressSelect.addEventListener("change", async () => {
            try { await load(addressSelect.value); } catch (error) { message(status, error.message, true); }
        });
        root.addEventListener("change", event => {
            if (event.target.name === "payment") payment = event.target.value;
        });
        root.querySelector("#place-order-button").addEventListener("click", async event => {
            const button = event.currentTarget;
            button.disabled = true;
            try {
                const result = await request(root.dataset.orderApi, "POST", {
                    chon: selected,
                    ma_dia_chi: addressSelect.value,
                    ma_pttt: payment
                });
                // Màn hình đặt hàng thành công thay cho bố cục thanh toán (không chuyển thẳng sang chi tiết đơn)
                const code = result.data.ma_dh;
                const next = payment === "PT001"
                    ? "Cửa hàng sẽ kiểm tra hàng và xác nhận đơn. Sau khi xác nhận, bạn có 24 giờ để chuyển khoản theo mã QR ở trang chi tiết đơn."
                    : "Cửa hàng sẽ kiểm tra hàng và xác nhận đơn. Bạn thanh toán khi nhận hàng.";
                status.className = "";
                status.textContent = "";
                root.querySelector("#checkout-layout").outerHTML = `<section class="module-panel order-success">
                    <span class="order-success-icon" aria-hidden="true">✓</span>
                    <h2>Đặt hàng thành công</h2>
                    <p>Mã đơn của bạn: <strong>${esc(code)}</strong></p>
                    <p class="module-muted">${next}</p>
                    <div class="order-success-actions"><a class="module-link-button" href="/don-cua-toi/${encodeURIComponent(code)}/">Xem chi tiết đơn</a><a class="module-link-button secondary" href="/">Về trang chủ</a></div>
                </section>`;
                window.scrollTo({ top: 0, behavior: "smooth" });
            } catch (error) {
                message(status, error.message, true);
                button.disabled = false;
            }
        });

        const closeAddressDialog = () => addressDialog.close();
        root.querySelector("#checkout-add-address").addEventListener("click", () => {
            addressForm.reset();
            addressFormMessage.textContent = "";
            addressForm.querySelector('[name="mac_dinh"]').checked = addressList.length === 0;
            addressDialog.showModal();
            addressForm.querySelector('[name="ten_nguoi_nhan"]').focus();
        });
        root.querySelector("#checkout-address-close").addEventListener("click", closeAddressDialog);
        root.querySelector("#checkout-address-cancel").addEventListener("click", closeAddressDialog);
        addressDialog.addEventListener("click", event => {
            if (event.target === addressDialog) closeAddressDialog();
        });
        addressForm.addEventListener("submit", async event => {
            event.preventDefault();
            const saveButton = root.querySelector("#checkout-address-save");
            if (!addressForm.reportValidity()) return;
            const data = Object.fromEntries(new FormData(addressForm).entries());
            data.mac_dinh = addressForm.querySelector('[name="mac_dinh"]').checked || addressList.length === 0;
            saveButton.disabled = true;
            try {
                const result = await request(root.dataset.addressApi, "POST", data);
                message(status, "Đã lưu địa chỉ. Đang cập nhật phí giao hàng và đơn hàng.");
                closeAddressDialog();
                await load(result.data.ma_dia_chi);
            } catch (error) {
                message(addressFormMessage, error.message, true);
            } finally {
                saveButton.disabled = false;
            }
        });
        try { await load(new URLSearchParams(location.search).get("ma_dia_chi")); }
        catch (error) { message(status, error.message, true); }
    }

    async function setupCustomerOrders(root) {
        const rows = root.querySelector("#customer-order-rows");
        const status = root.querySelector("#customer-orders-message");
        const filter = root.querySelector("#order-status");
        const load = async () => {
            rows.innerHTML = '<tr><td colspan="7" class="module-empty">Đang tải…</td></tr>';
            try {
                const query = filter.value ? `?trang_thai=${encodeURIComponent(filter.value)}` : "";
                const result = await request(`${root.dataset.api}${query}`);
                rows.innerHTML = result.data.length ? result.data.map(order => `
                    <tr><td class="nowrap"><strong>${esc(order.ma_dh)}</strong></td><td class="nowrap">${shortDate(order.ngay_dat)}</td>
                    <td>${order.chi_tiet.map(line => `${esc(line.ten_sp)} × ${line.so_luong}`).join("<br>")}</td>
                    <td class="nowrap">${money(order.tong_thanh_toan)}<br><small>${order.ma_pttt === "PT002" ? "COD" : "Chuyển khoản"} · ${esc(order.ten_trang_thai_thanh_toan)}</small></td>
                    <td>${statusPill(order)}${order.han_thanh_toan ? `<br><small>Hạn ${shortDate(order.han_thanh_toan)}</small>` : ""}</td>
                    <td>${afterSalesPill(order)}</td><td class="nowrap"><a href="/don-cua-toi/${encodeURIComponent(order.ma_dh)}/">${order.han_thanh_toan ? "Thanh toán" : "Chi tiết"} →</a></td></tr>`
                ).join("") : '<tr><td colspan="7" class="module-empty">Chưa có đơn hàng phù hợp.</td></tr>';
            } catch (error) { message(status, error.message, true); }
        };
        filter.addEventListener("change", load);
        await load();
    }

    // ==========================================================
    // WF06 – CHI TIẾT ĐƠN CỦA KHÁCH (M3-UC05, UC06; cổng giả lập UC11)
    // Trái: đầu đơn + tiến độ (kèm việc khách cần làm: nhận hàng / chờ bổ sung),
    //       thanh toán chuyển khoản (QR), sản phẩm, giao hàng.
    // Phải: lịch sử trạng thái, hỗ trợ (hủy đơn / hậu mãi).
    // Dùng chung các hàm progressBar, infoList, historyCard, shortDate với WF08 (khai báo bên dưới).
    // ==========================================================
    const CUSTOMER_CANCELLABLE = ["CHO_XAC_NHAN", "DA_XAC_NHAN", "CHO_THANH_TOAN", "DANG_CHUAN_BI", "CHO_BO_SUNG"];
    const BANK_NAMES = { VCB: "Vietcombank (VCB)" };

    // Đơn COD không có bước "Thanh toán" trước chuẩn bị (COD thu tiền khi giao)
    function customerSteps(order) {
        const transfer = order.ma_pttt === "PT001";
        return [
            { label: "Đặt hàng", statuses: ["CHO_XAC_NHAN"] },
            { label: "Xác nhận", statuses: transfer ? ["DA_XAC_NHAN"] : ["DA_XAC_NHAN", "CHO_THANH_TOAN"] },
            ...(transfer ? [{ label: "Thanh toán", statuses: ["CHO_THANH_TOAN"] }] : []),
            { label: "Chuẩn bị hàng", statuses: ["DANG_CHUAN_BI", "CHO_BO_SUNG", "SAN_SANG_GIAO"] },
            { label: "Đang giao", statuses: ["DANG_GIAO"] },
            { label: "Đã nhận hàng", statuses: ["GIAO_THANH_CONG", "HOAN_THANH"] },
        ];
    }

    function customerHead(order) {
        const method = order.ma_pttt === "PT002" ? "COD" : "Chuyển khoản";
        const waitingTransfer = Boolean(order.thong_tin_chuyen_khoan);
        const when = order.thoi_diem_giao_thanh_cong
            ? `Giao lúc ${shortDate(order.thoi_diem_giao_thanh_cong)}` : `Đặt lúc ${shortDate(order.ngay_dat)}`;

        // Khối nhận hàng (UC06, BR21): chỉ khi đơn đã giao và còn trong thời hạn
        const withinWindow = Boolean(order.han_cua_so_doi_tra) && new Date(order.han_cua_so_doi_tra) >= new Date();
        const canConfirm = withinWindow && !order.thoi_diem_xac_nhan_nhan_hang;
        const canReturn = canConfirm && ["GIAO_THANH_CONG", "HOAN_THANH"].includes(order.trang_thai);
        const returnUrl = `${afterSalesCustomerUrl}?ma_dh=${encodeURIComponent(order.ma_dh)}`;
        let receipt = "";
        if (canConfirm) {
            receipt = `<div class="so-box"><p><strong>Bạn đã nhận đủ hàng?</strong> Nhấn [Đã nhận hàng] để hoàn tất. Nếu không xác nhận, hệ thống tự xác nhận vào <strong>${shortDate(order.han_cua_so_doi_tra)}</strong>; đến thời điểm này bạn vẫn có thể gửi yêu cầu đổi/trả.</p>
                <div class="so-buttons"><button class="module-button" type="button" data-received>Đã nhận hàng</button>${canReturn ? `<a class="module-link-button secondary" href="${returnUrl}">Yêu cầu đổi/trả →</a>` : ""}</div></div>`;
        } else if (order.thoi_diem_xac_nhan_nhan_hang) {
            receipt = `<div class="so-box"><p>Bạn đã xác nhận nhận hàng lúc <strong>${shortDate(order.thoi_diem_xac_nhan_nhan_hang)}</strong>. Cảm ơn bạn đã mua hàng tại Quý Thu.</p></div>`;
        }

        return `<section class="module-panel so-card">
            <div class="so-head-top">
                <span class="module-eyebrow">${esc(order.ma_dh)} · ${when}</span>
                <div class="so-pills"><span class="module-pill ${waitingTransfer ? "warning" : ""}">${method} · ${esc(order.ten_trang_thai_thanh_toan)}</span>${order.ten_trang_thai_hau_mai ? `<span class="module-pill warning">Hậu mãi: ${esc(order.ten_trang_thai_hau_mai)}</span>` : ""}</div>
            </div>
            <h2 class="so-title">${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</h2>
            ${order.trang_thai === "CHO_BO_SUNG" ? `<div class="so-banner"><span aria-hidden="true">⏳</span><div><strong>Cửa hàng đang bổ sung hàng cho đơn của bạn</strong><p>Dự kiến có hàng: <strong>${shortDate(order.thoi_diem_hen_cung_cap)}</strong>. Đơn sẽ tiếp tục xử lý ngay khi đủ hàng. Không muốn chờ? <a href="${returnUrl}">Yêu cầu hủy đơn →</a></p></div></div>` : ""}
            ${progressBar(customerSteps(order), order)}
            ${receipt}
        </section>`;
    }

    // BR17: QR chứa số tiền + nội dung (mã đơn). Ảnh QR lấy từ VietQR theo thông tin tài khoản của cửa hàng.
    function customerPayment(order) {
        const qr = order.thong_tin_chuyen_khoan;
        if (!qr) return "";
        // thong_tin_tai_khoan dạng "VCB 0041000888999 - Banh Dua Quy Thu"
        const match = /^(\S+)\s+(\d+)\s*-\s*(.+)$/.exec(qr.tai_khoan || "");
        const [bank, account, holder] = match ? [match[1], match[2], match[3].trim()] : ["", "", ""];
        const qrUrl = match
            ? `https://img.vietqr.io/image/${encodeURIComponent(bank)}-${account}-qr_only.png?amount=${qr.so_tien}&addInfo=${encodeURIComponent(qr.noi_dung)}&accountName=${encodeURIComponent(holder)}`
            : "";
        const hoursLeft = (new Date(qr.han_thanh_toan) - Date.now()) / 36e5;
        const left = hoursLeft <= 0 ? "đã quá hạn" : hoursLeft >= 1 ? `còn ${Math.floor(hoursLeft)} giờ` : `còn ${Math.ceil(hoursLeft * 60)} phút`;
        const rows = match
            ? [["Ngân hàng", esc(BANK_NAMES[bank] || bank)], ["Số tài khoản", esc(account)], ["Chủ tài khoản", esc(holder)]]
            : [["Ngân hàng / tài khoản", esc(qr.tai_khoan)]];
        return `<section class="module-panel so-card"><h2>Thanh toán chuyển khoản</h2>
            ${order.trang_thai_thanh_toan === "THAT_BAI" ? '<p class="module-alert error">Giao dịch gần nhất không thành công. Bạn có thể chuyển khoản lại trước hạn thanh toán.</p>' : ""}
            <div class="so-qr-wrap">
                ${qrUrl ? `<div class="so-qr"><img src="${qrUrl}" alt="Mã QR chuyển khoản ${money(qr.so_tien)} cho đơn ${esc(order.ma_dh)}" width="150" height="150"><span>Không tải được mã QR (cần Internet). Hãy chuyển khoản theo thông tin bên cạnh.</span></div>` : ""}
                ${infoList([
                    ...rows,
                    ["Số tiền", `<span class="so-amount">${money(qr.so_tien)}</span>`],
                    ["Nội dung CK", `<code>${esc(qr.noi_dung)}</code>`],
                    ["Hạn thanh toán", `${shortDate(qr.han_thanh_toan)} <span class="module-pill warning">${left}</span>`],
                ])}
            </div>
            <p class="so-hint">Quét mã bằng ứng dụng ngân hàng; số tiền và nội dung đã điền sẵn. Quá hạn đơn sẽ tự hủy.</p>
            <div class="so-demo"><p><strong>Cổng thanh toán giả lập</strong> <small>(chỉ dùng khi demo, thay cho ngân hàng thật)</small></p>
                <div class="so-buttons"><button class="module-button" type="button" data-payment="THANH_CONG">Thanh toán thành công</button><button class="module-button secondary" type="button" data-payment="THAT_BAI">Giao dịch thất bại</button></div>
            </div>
        </section>`;
    }

    function customerProducts(order) {
        return `<section class="module-panel so-card"><h2>Sản phẩm</h2>
            <div class="module-table-wrap"><table class="module-table so-table"><thead><tr><th>Sản phẩm</th><th>Loại giá</th><th>Đơn giá</th><th class="num">SL</th><th class="num">Thành tiền</th></tr></thead><tbody>
            ${(order.chi_tiet || []).map(line => `<tr>
                <td><strong>${esc(line.ten_sp)}</strong><br><span class="so-sub">${esc(variantLabel(line))}</span></td>
                <td>${esc(line.ten_loai_gia)}</td>
                <td>${money(line.don_gia)}</td>
                <td class="num">${line.so_luong}</td>
                <td class="num"><strong>${money(line.thanh_tien)}</strong></td></tr>`).join("")}
            </tbody></table></div>
            <dl class="so-totals"><dt>Tiền hàng</dt><dd>${money(order.tong_tien_hang)}</dd><dt>Phí giao hàng (${esc(order.ten_tinh)})</dt><dd>${money(order.phi_van_chuyen)}</dd><dt class="grand">Tổng thanh toán</dt><dd class="grand">${money(order.tong_thanh_toan)}</dd></dl>
        </section>`;
    }

    function customerDelivery(order) {
        return `<section class="module-panel so-card"><h2>Giao hàng</h2>${infoList([
            ["Người nhận", `${esc(order.ho_ten_nguoi_nhan)} · ${esc(order.sdt_nguoi_nhan)}`],
            ["Địa chỉ", `${esc(order.dia_chi_giao_hang)}, ${esc(order.ten_tinh)}`],
            ["Thanh toán", `${esc(order.ten_pttt)} · ${esc(order.ten_trang_thai_thanh_toan)}`],
            order.thoi_diem_giao_thanh_cong && ["Giao thành công", shortDate(order.thoi_diem_giao_thanh_cong)],
        ])}</section>`;
    }

    // Khối hỗ trợ chỉ hiện khi có việc khác để làm: còn hủy được, hoặc đang có yêu cầu hậu mãi.
    // Đơn đã giao thì nút [Yêu cầu đổi/trả] đã nằm ở khối nhận hàng, không lặp lại ở đây.
    function customerSupport(order) {
        const url = `${afterSalesCustomerUrl}?ma_dh=${encodeURIComponent(order.ma_dh)}`;
        let text;
        let link;
        if (order.ten_trang_thai_hau_mai) {
            text = `Yêu cầu của bạn đang được xử lý: <strong>${esc(order.ten_trang_thai_hau_mai)}</strong>.`;
            link = "Theo dõi hậu mãi";
        } else if (CUSTOMER_CANCELLABLE.includes(order.trang_thai)) {
            text = "Đơn chưa bàn giao vận chuyển nên bạn có thể gửi yêu cầu hủy.";
            link = "Yêu cầu hủy đơn";
        } else {
            return "";
        }
        return `<section class="module-panel so-card"><h2>Cần hỗ trợ?</h2><p class="so-hint">${text}</p><a class="module-link-button secondary" href="${url}">${link} →</a></section>`;
    }

    let afterSalesCustomerUrl = "/tai-khoan/hau-mai/";

    async function setupCustomerOrderDetail(root) {
        const messageNode = root.querySelector("#order-detail-message");
        const main = root.querySelector("#order-detail-main");
        const side = root.querySelector("#order-detail-side");
        const orderApi = root.dataset.api;
        afterSalesCustomerUrl = root.dataset.afterSales || afterSalesCustomerUrl;

        const load = async () => {
            const order = (await request(orderApi)).data;
            main.innerHTML = customerHead(order) + customerPayment(order) + customerProducts(order) + customerDelivery(order);
            side.innerHTML = historyCard(order, "Lịch sử trạng thái") + customerSupport(order);
        };

        // Ảnh QR không tải được (máy không có Internet) → hiện câu thay thế.
        // Sự kiện "error" của ảnh không nổi bọt nên phải bắt ở pha capture (tham số true).
        root.addEventListener("error", event => {
            if (event.target.matches?.(".so-qr img")) event.target.closest(".so-qr").classList.add("is-offline");
        }, true);

        root.addEventListener("click", async event => {
            const received = event.target.closest("[data-received]");
            const payment = event.target.closest("[data-payment]");
            if (!received && !payment) return;
            const button = received || payment;
            button.disabled = true;
            try {
                if (received) {
                    await request(`${orderApi}da-nhan-hang/`, "POST", {});
                    message(messageNode, "Đã xác nhận nhận hàng.");
                } else {
                    await request(`${orderApi}payment/`, "POST", { ket_qua: payment.dataset.payment });
                    message(messageNode, payment.dataset.payment === "THANH_CONG"
                        ? "Thanh toán thành công. Cửa hàng sẽ bắt đầu chuẩn bị hàng."
                        : "Đã ghi nhận giao dịch thất bại (mô phỏng).");
                }
                await load();
            } catch (error) {
                message(messageNode, error.message, true);
                button.disabled = false;
            }
            messageNode.scrollIntoView({ behavior: "smooth", block: "center" });
        });

        try { await load(); } catch (error) { message(messageNode, error.message, true); }
    }

    async function setupStaffOrders(root) {
        const rows = root.querySelector("#staff-order-rows");
        const status = root.querySelector("#staff-orders-message");
        const filter = root.querySelector("#staff-order-filter");
        const pagination = root.querySelector("#staff-order-pagination");
        let currentPage = 1;
        const load = async page => {
            currentPage = page;
            const query = new URLSearchParams(new FormData(filter));
            query.set("trang", String(page));
            rows.innerHTML = '<tr><td colspan="8" class="module-empty">Đang tải…</td></tr>';
            const result = await request(`${root.dataset.api}?${query}`);
            rows.innerHTML = result.data.length ? result.data.map(order => `
                <tr><td class="nowrap"><strong>${esc(order.ma_dh)}</strong><br><small>${shortDate(order.ngay_dat)}</small></td><td>${esc(order.ten_khach_hang)}<br><small>${esc(order.ma_kh)}</small></td>
                <td>${esc(order.ten_loai_khach)}</td><td class="nowrap">${money(order.tong_thanh_toan)}</td><td>${statusPill(order)}</td><td>${esc(order.ten_trang_thai_thanh_toan)}</td><td>${afterSalesPill(order)}</td>
                <td class="nowrap"><a href="/don-hang/${encodeURIComponent(order.ma_dh)}/">Mở đơn →</a></td></tr>`).join("") : '<tr><td colspan="8" class="module-empty">Không có đơn phù hợp bộ lọc.</td></tr>';
            pagination.innerHTML = `<span>${result.tong_so_don} đơn hàng · Trang ${result.trang_hien_tai}/${result.so_trang}</span><div class="module-inline-form"><button class="module-button secondary" data-page="${Math.max(1, page - 1)}" ${page <= 1 ? "disabled" : ""}>← Trước</button><button class="module-button secondary" data-page="${Math.min(result.so_trang || 1, page + 1)}" ${page >= result.so_trang ? "disabled" : ""}>Tiếp →</button></div>`;
        };
        filter.addEventListener("submit", async event => {
            event.preventDefault();
            try { await load(1); } catch (error) { message(status, error.message, true); }
        });
        pagination.addEventListener("click", async event => {
            const button = event.target.closest("[data-page]");
            if (!button || button.disabled) return;
            try { await load(Number(button.dataset.page)); } catch (error) { message(status, error.message, true); }
        });
        try { await load(currentPage); } catch (error) { message(status, error.message, true); }
    }

    // ==========================================================
    // WF08 – CHI TIẾT VÀ XỬ LÝ ĐƠN (nhân viên, M3-UC07 → UC13)
    // Bố cục 2 cột: trái là phần ĐỌC (đầu đơn + tiến độ, khách, dòng hàng,
    // thanh toán, giao hàng, lịch sử); phải là phần LÀM (các khối thao tác,
    // đánh số theo thứ tự làm, dính khi cuộn). Đổi trạng thái thì chỉ cột phải đổi.
    // ==========================================================
    const STAFF_STEPS = [
        { label: "Chờ xác nhận", statuses: ["CHO_XAC_NHAN"] },
        { label: "Đã xác nhận", statuses: ["DA_XAC_NHAN", "CHO_THANH_TOAN"] },
        { label: "Chuẩn bị", statuses: ["DANG_CHUAN_BI", "CHO_BO_SUNG"] },
        { label: "Sẵn sàng giao", statuses: ["SAN_SANG_GIAO"] },
        { label: "Đang giao", statuses: ["DANG_GIAO"] },
        { label: "Giao xong", statuses: ["GIAO_THANH_CONG"] },
        { label: "Hoàn thành", statuses: ["HOAN_THANH"] },
    ];
    // Thao tác bị chặn khi khách đang yêu cầu hủy (M3-BR19).
    // Khớp các hàm có gọi kiem_tra_khong_cho_huy() trong orders/services.py.
    const LOCKED_WHEN_CANCEL = {
        "kiem-tra-hang": "Kiểm tra hàng",
        "xac-nhan": "Xác nhận đơn",
        "ghi-nhan-thanh-toan": "Ghi nhận chuyển khoản",
        "bat-dau-chuan-bi": "Bắt đầu chuẩn bị",
        "ban-giao": "Bàn giao",
    };
    // Trạng thái còn cho đính chính ghi nhận chuyển khoản (trước khi bàn giao, feedback mục 25)
    const CORRECTION_STATUSES = ["DA_XAC_NHAN", "CHO_THANH_TOAN", "DANG_CHUAN_BI", "CHO_BO_SUNG", "SAN_SANG_GIAO"];

    // Giá trị cho ô datetime-local theo giờ máy: "2026-11-12T11:22"
    const localInputValue = (d = new Date()) => {
        const p = n => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
    };

    // Danh sách nhãn – giá trị. rows: [[nhãn, html đã escape], ...]; phần tử false bị bỏ qua.
    const infoList = rows => `<dl class="so-info">${rows.filter(Boolean)
        .map(([label, value]) => `<dt>${esc(label)}</dt><dd>${value}</dd>`).join("")}</dl>`;

    // Thanh tiến độ dùng chung cho WF06 (khách) và WF08 (nhân viên). steps: [{label, statuses}]
    function progressBar(steps, order) {
        if (order.trang_thai === "DA_HUY") return '<p class="module-alert error">Đơn hàng đã hủy.</p>';
        const finished = order.trang_thai === "HOAN_THANH";  // xong hết: mọi bước tô đậm, không còn bước "hiện tại"
        let current = finished ? steps.length : steps.findIndex(step => step.statuses.includes(order.trang_thai));
        // Chờ bổ sung hàng có thể xảy ra trước khi xác nhận (UC09 → UC10): khi đó đơn vẫn ở bước đầu tiên
        const confirmedBefore = (order.lich_su_trang_thai || []).some(item => item.trang_thai === "DA_XAC_NHAN");
        if (order.trang_thai === "CHO_BO_SUNG" && !confirmedBefore) current = 0;
        const shownName = order.ten_trang_thai_hien_thi || order.ten_trang_thai;
        return `<ol class="so-progress" style="--steps:${steps.length}" aria-label="Tiến độ xử lý đơn">${steps.map((step, index) => {
            const state = index < current ? "is-done" : index === current ? "is-current" : "";
            // Bước gộp nhiều trạng thái (Chờ bổ sung, Sẵn sàng giao…) hoặc đã thanh toán chờ chuẩn bị: ghi rõ trạng thái thật
            const sub = index === current && (step.statuses[0] !== order.trang_thai || shownName !== order.ten_trang_thai)
                ? `<small>${esc(shownName)}</small>` : "";
            return `<li class="${state}"${index === current ? ' aria-current="step"' : ""}><span class="so-dot" aria-hidden="true"></span><span>${step.label}</span>${sub}</li>`;
        }).join("")}</ol>`;
    }

    function staffHead(order, afterSalesUrl) {
        const cancelPending = order.trang_thai_hau_mai === "CHO_HUY";
        const method = order.ma_pttt === "PT002" ? "COD" : "Chuyển khoản";
        const afterSalesClass = cancelPending ? "danger" : order.trang_thai_hau_mai ? "warning" : "";
        const locked = Object.values(LOCKED_WHEN_CANCEL).join(", ");
        return `<section class="module-panel so-card">
            <div class="so-head-top">
                <span class="module-eyebrow">${esc(order.ma_dh)} · Đặt lúc ${shortDate(order.ngay_dat)}</span>
                <div class="so-pills"><span class="module-pill">${method} · ${esc(order.ten_trang_thai_thanh_toan)}</span>${order.ten_trang_thai_hau_mai ? `<span class="module-pill ${afterSalesClass}">Hậu mãi: ${esc(order.ten_trang_thai_hau_mai)}</span>` : ""}</div>
            </div>
            <h2 class="so-title">${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}${cancelPending ? '<span class="so-badge">Chờ hủy</span>' : ""}</h2>
            ${cancelPending ? `<div class="so-banner" role="alert"><span aria-hidden="true">⚠️</span><div><strong>Khách đang yêu cầu hủy đơn (Module 4)</strong><p>Tạm khóa: ${locked}. Xử lý yêu cầu hủy tại <a href="${esc(afterSalesUrl)}">Hậu mãi → Yêu cầu hủy</a> trước.</p></div></div>` : ""}
            ${order.trang_thai_hau_mai && !cancelPending ? `<div class="so-banner"><span aria-hidden="true">ℹ️</span><div><strong>Đơn đang có xử lý hậu mãi: ${esc(order.ten_trang_thai_hau_mai)}</strong><p>Xem chi tiết tại <a href="${esc(afterSalesUrl)}">Hậu mãi</a>.</p></div></div>` : ""}
            ${order.trang_thai === "CHO_BO_SUNG" ? `<div class="so-banner"><span aria-hidden="true">⏳</span><div><strong>Chờ bổ sung hàng</strong><p>Hẹn cung cấp: ${shortDate(order.thoi_diem_hen_cung_cap)}.</p></div></div>` : ""}
            ${progressBar(STAFF_STEPS, order)}
        </section>`;
    }

    function staffCustomer(order) {
        return `<section class="module-panel so-card"><h2>Khách hàng và giao hàng</h2>${infoList([
            ["Khách", `${esc(order.ten_khach_hang)} (${esc(order.ma_kh)}) · ${esc(order.ten_loai_khach)}`],
            ["Người nhận", `${esc(order.ho_ten_nguoi_nhan)} · ${esc(order.sdt_nguoi_nhan)}`],
            ["Địa chỉ", `${esc(order.dia_chi_giao_hang)}, ${esc(order.ten_tinh)}`],
            ["Ghi chú của khách", esc(order.ghi_chu || "—")],
        ])}</section>`;
    }

    function staffLines(order) {
        const check = line => {
            if (line.ket_qua_kiem_tra === "DU") return '<span class="so-check ok">Đủ hàng</span>';
            if (line.ket_qua_kiem_tra === "THIEU") return `<span class="so-check bad">Thiếu ${line.so_luong_thieu}</span>`;
            return '<span class="so-check wait">Chưa kiểm tra</span>';
        };
        return `<section class="module-panel so-card"><h2>Dòng hàng</h2>
            <div class="module-table-wrap"><table class="module-table so-table"><thead><tr><th>Sản phẩm</th><th>Đơn giá</th><th class="num">SL</th><th class="num">Thành tiền</th><th>Kiểm tra hàng</th></tr></thead><tbody>
            ${(order.chi_tiet || []).map(line => `<tr>
                <td><strong>${esc(line.ten_sp)}</strong><br><span class="so-sub">${esc(variantLabel(line))}</span></td>
                <td>${money(line.don_gia)}<br><small class="so-sub">${esc(line.ten_loai_gia)}</small></td>
                <td class="num">${line.so_luong}</td>
                <td class="num"><strong>${money(line.thanh_tien)}</strong></td>
                <td>${check(line)}</td></tr>`).join("")}
            </tbody></table></div>
            <dl class="so-totals"><dt>Tiền hàng</dt><dd>${money(order.tong_tien_hang)}</dd><dt>Phí giao hàng</dt><dd>${money(order.phi_van_chuyen)}</dd><dt class="grand">Tổng thanh toán</dt><dd class="grand">${money(order.tong_thanh_toan)}</dd></dl>
        </section>`;
    }

    function staffPayment(order) {
        const p = order.giao_dich || {};
        const isTransfer = order.ma_pttt === "PT001";
        const qr = order.thong_tin_chuyen_khoan;
        return `<section class="module-panel so-card"><h2>Thanh toán</h2>${infoList([
            ["Phương thức", esc(order.ten_pttt)],
            ["Trạng thái", esc(order.ten_trang_thai_thanh_toan)],
            ["Số tiền phải thu", money(p.so_tien_phai_thu ?? order.tong_thanh_toan)],
            p.so_tien_thuc_nhan !== null && p.so_tien_thuc_nhan !== undefined && ["Số tiền đã nhận", money(p.so_tien_thuc_nhan)],
            p.thoi_diem_thanh_toan && ["Thời điểm thanh toán", shortDate(p.thoi_diem_thanh_toan)],
            qr && order.trang_thai_thanh_toan !== "DA_THANH_TOAN" && ["Hạn thanh toán", shortDate(qr.han_thanh_toan)],
            ["Mã bản ghi", esc(p.ma_giao_dich || "—")],
            isTransfer && ["Mã GD ngân hàng", esc(p.ma_giao_dich_ngan_hang || "—")],
            ["Người ghi nhận", esc(p.ten_nhan_vien_ghi_nhan || "—")],
            p.ghi_chu && ["Ghi chú", esc(p.ghi_chu)],
        ])}</section>`;
    }

    function staffDelivery(order) {
        const list = order.cac_lan_giao || [];
        if (!list.length) return "";
        return `<section class="module-panel so-card"><h2>Giao hàng</h2>${list.map(g => infoList([
            ["Lần giao", `Lần ${g.lan_giao} · ${esc(g.ten_ket_qua_giao)}`],
            ["Hình thức", esc(g.ten_hinh_thuc_giao)],
            g.don_vi_van_chuyen && ["Đơn vị vận chuyển", esc(g.don_vi_van_chuyen)],
            g.sdt_shipper && ["SĐT shipper", esc(g.sdt_shipper)],
            g.ma_van_don && ["Mã vận đơn", esc(g.ma_van_don)],
            ["Bàn giao lúc", shortDate(g.thoi_diem_ban_giao)],
            g.thoi_diem_giao_xong && ["Giao xong lúc", shortDate(g.thoi_diem_giao_xong)],
            g.ly_do_that_bai && ["Lý do thất bại", esc(g.ly_do_that_bai)],
        ])).join('<hr class="so-hr">')}</section>`;
    }

    // Lịch sử dạng dòng thời gian, dùng chung WF06 và WF08.
    // Dòng có trạng thái cũ = mới là ghi nhận thêm (kiểm tra hàng, gia hạn…), không phải đổi trạng thái:
    // hiện ghi chú làm tiêu đề thay vì lặp lại tên trạng thái (feedback mục 10).
    function historyCard(order, title) {
        const items = order.lich_su_trang_thai || [];
        const body = items.length ? `<ol class="so-timeline">${items.map(item => {
            const note = item.trang_thai_cu && item.trang_thai_cu === item.trang_thai;
            const who = item.ten_nhan_vien ? `Nhân viên ${item.ten_nhan_vien}` : item.ten_tac_nhan;
            const heading = note ? (item.ghi_chu || "Ghi nhận") : item.ten_trang_thai;
            const detail = note ? who : `${who}${item.ghi_chu ? ` · ${item.ghi_chu}` : ""}`;
            return `<li class="${note ? "is-note" : ""}"><div><strong>${esc(heading)}</strong> · ${shortDate(item.thoi_diem)}</div><small>${esc(detail)}</small></li>`;
        }).join("")}</ol>` : '<p class="module-muted">Chưa có lịch sử.</p>';
        return `<section class="module-panel so-card"><h2>${esc(title)}</h2>${body}</section>`;
    }

    // ---------- Cột phải: các khối thao tác ----------
    let fieldId = 0;
    const field = (name, label, { type = "text", required = false, value = "", note = "", attrs = "" } = {}) => {
        const id = `so-f${++fieldId}`;
        return `<div class="so-field"><label for="${id}">${label}</label><input id="${id}" name="${name}" type="${type}" value="${esc(value)}" ${required ? "required" : ""} ${attrs}>${note ? `<small>${note}</small>` : ""}</div>`;
    };
    const noteField = () => {
        const id = `so-f${++fieldId}`;
        return `<div class="so-field"><label for="${id}">Ghi chú</label><textarea id="${id}" name="ghi_chu" rows="3"></textarea></div>`;
    };

    // Một khối thao tác. locked = lý do khóa (chuỗi rỗng = mở). Khối khóa chỉ hiện lý do + nút mờ.
    const actionCard = ({ no, action, title, hint = "", fields = "", button, locked = "", secondary = false }) => `
        <form class="module-panel so-action${locked ? " is-locked" : ""}" data-action="${action}">
            <h3>${no}. ${esc(title)}</h3>
            ${locked ? `<p class="so-hint">${esc(locked)}</p>` : hint ? `<p class="so-hint">${hint}</p>` : ""}
            <fieldset ${locked ? "disabled" : ""}>${locked ? "" : fields}<button class="module-button so-submit${secondary ? " secondary" : ""}" type="submit">${esc(button)}</button></fieldset>
        </form>`;
    const infoCard = (title, text) => `<section class="module-panel so-action"><h3>${esc(title)}</h3><p class="so-hint">${text}</p></section>`;

    // UC09: mỗi dòng chọn Đủ hàng / Thiếu; ô "SL thiếu" chỉ mở khi chọn Thiếu (feedback mục 16)
    const supplyFields = order => (order.chi_tiet || []).map(line => {
        const short = line.ket_qua_kiem_tra === "THIEU";
        const key = esc(line.ma_ctdh);
        return `<div class="so-line" data-line="${key}">
            <strong>${esc(line.ten_sp)} · ${esc(variantLabel(line))} · đặt ${line.so_luong}</strong>
            <div class="so-radios">
                <label><input type="radio" name="kq-${key}" value="DU" ${short ? "" : "checked"}> Đủ hàng</label>
                <label><input type="radio" name="kq-${key}" value="THIEU" ${short ? "checked" : ""}> Thiếu</label>
            </div>
            <input type="number" name="thieu-${key}" min="1" max="${line.so_luong}" placeholder="SL thiếu" value="${short ? line.so_luong_thieu : ""}" ${short ? "required" : "disabled"} aria-label="Số lượng thiếu – ${esc(line.ten_sp)}">
        </div>`;
    }).join("");

    function staffActions(order) {
        fieldId = 0;
        const status = order.trang_thai;
        const cancelPending = order.trang_thai_hau_mai === "CHO_HUY";
        const lines = order.chi_tiet || [];
        const allOk = lines.length > 0 && lines.every(line => line.ket_qua_kiem_tra === "DU");
        const hasShortage = lines.some(line => line.ket_qua_kiem_tra === "THIEU");
        const isTransfer = order.ma_pttt === "PT001";
        const paid = order.trang_thai_thanh_toan === "DA_THANH_TOAN";
        const payment = order.giao_dich || {};
        const mustCollect = payment.so_tien_phai_thu || order.tong_thanh_toan;
        const now = localInputValue();

        const cards = [];
        const add = card => {
            const cancelLock = cancelPending && LOCKED_WHEN_CANCEL[card.action]
                ? "Tạm khóa: khách đang yêu cầu hủy đơn." : "";
            cards.push(actionCard({ ...card, no: cards.length + 1, locked: card.locked || cancelLock }));
        };

        const supplyCard = recheck => ({
            action: "kiem-tra-hang",
            title: recheck ? "Kiểm tra lại cung ứng" : "Kiểm tra cung ứng",
            hint: "Đối chiếu hàng thực tế cho từng dòng.",
            fields: supplyFields(order) + noteField(),
            button: "Lưu kết quả kiểm tra",
            secondary: recheck && allOk,
        });
        const backorderCard = {
            action: "cho-bo-sung", title: "Chuyển chờ bổ sung hàng",
            hint: "Có dòng thiếu hàng. Hẹn thời điểm có hàng để báo khách.",
            fields: field("thoi_diem_hen", "Thời điểm hẹn cung cấp", { type: "datetime-local", required: true, attrs: `min="${now}"` }) + noteField(),
            button: "Chuyển chờ bổ sung",
        };
        const prepareCard = locked => ({
            action: "bat-dau-chuan-bi", title: "Bắt đầu chuẩn bị",
            hint: "Chuyển đơn sang Đang chuẩn bị hàng.", fields: noteField(), button: "Bắt đầu chuẩn bị", locked,
        });
        const transferCard = {
            action: "ghi-nhan-thanh-toan", title: "Ghi nhận chuyển khoản",
            hint: "Đối soát với sao kê ngân hàng khi khách chuyển khoản ngoài mã QR.",
            fields: field("so_tien_thuc_nhan", "Số tiền thực nhận (₫)", { type: "number", required: true, value: mustCollect, attrs: 'min="1"' })
                + field("ma_giao_dich_ngan_hang", "Mã giao dịch ngân hàng", { required: true, attrs: 'maxlength="50"' })
                + noteField(),
            button: "Ghi nhận đã nhận tiền",
        };
        const codCard = locked => ({
            action: "thu-cod", title: "Thu tiền COD",
            fields: field("so_tien_thuc_nhan", "Số tiền thực nhận (₫)", { type: "number", required: true, value: mustCollect, attrs: 'min="0"', note: `Điền sẵn bằng số tiền phải thu ${money(mustCollect)}.` }) + noteField(),
            button: "Ghi nhận đã thu tiền", locked,
        });

        switch (status) {
            case "CHO_XAC_NHAN":
                add(supplyCard(false));
                if (hasShortage) add(backorderCard);
                else add({
                    action: "xac-nhan", title: "Xác nhận đơn",
                    hint: isTransfer ? "Đơn chuyển khoản sẽ chuyển sang Chờ thanh toán (khách có 24 giờ)." : "Đơn COD chuyển sang Đã xác nhận.",
                    fields: noteField(), button: "Xác nhận đơn",
                    locked: allOk ? "" : 'Mở sau khi mọi dòng "Đủ hàng". Nếu có dòng thiếu, ô này đổi thành [Chuyển chờ bổ sung] kèm thời điểm hẹn.',
                });
                break;
            case "CHO_BO_SUNG":
                add({
                    action: "gia-han", title: "Gia hạn thời điểm bổ sung",
                    hint: "Dùng khi hàng về trễ hơn thời điểm đã hẹn.",
                    fields: field("thoi_diem_hen", "Thời điểm hẹn mới", { type: "datetime-local", required: true, attrs: `min="${now}"` }) + noteField(),
                    button: "Gia hạn", secondary: true,
                });
                add({
                    action: "da-du-hang", title: "Đã đủ hàng",
                    hint: "Hàng đã về đủ: các dòng thiếu chuyển thành Đủ hàng, đơn quay lại bước trước khi chờ bổ sung.",
                    fields: noteField(), button: "Ghi nhận đã đủ hàng",
                });
                break;
            case "DA_XAC_NHAN":
                add(prepareCard(""));
                break;
            case "CHO_THANH_TOAN":
                if (paid) add(prepareCard(""));
                else {
                    add(transferCard);
                    add(prepareCard("Mở sau khi khách thanh toán (qua cổng hoặc nhân viên ghi nhận ở khối trên)."));
                }
                break;
            case "DANG_CHUAN_BI":
                add(supplyCard(true));
                if (hasShortage) add(backorderCard);
                else add({
                    action: "san-sang-giao", title: "Sẵn sàng giao",
                    hint: "Hàng đã đóng gói xong, chờ bàn giao vận chuyển.",
                    fields: noteField(), button: "Ghi nhận sẵn sàng giao",
                    locked: allOk ? "" : 'Mở sau khi mọi dòng "Đủ hàng".',
                });
                break;
            case "SAN_SANG_GIAO": {
                const suggest = order.goi_y_hinh_thuc_giao || {};
                const options = [["XE_TAI", "Xe tải nội bộ"], ["SHIPPER", "Shipper giao nhanh"], ["DVVC", "ĐVVC TMĐT"]]
                    .map(([value, label]) => `<option value="${value}" ${suggest.ma === value ? "selected" : ""}>${label}</option>`).join("");
                const needCarrier = suggest.ma && suggest.ma !== "XE_TAI";
                add({
                    action: "ban-giao", title: "Bàn giao vận chuyển",
                    hint: `Gợi ý theo loại khách: <strong>${esc(suggest.ten || "—")}</strong> (khách sỉ → xe tải nội bộ, khách lẻ → shipper).`,
                    fields: `<div class="so-field"><label for="so-ship">Hình thức giao</label><select id="so-ship" name="hinh_thuc_giao" required>${options}</select></div>`
                        + field("don_vi_van_chuyen", "Đơn vị vận chuyển", { required: needCarrier, note: "Bắt buộc với Shipper và ĐVVC; xe tải để trống." })
                        + noteField(),
                    button: "Bàn giao",
                });
                break;
            }
            case "DANG_GIAO":
                add({
                    action: "giao-thanh-cong", title: "Ghi nhận giao thành công",
                    hint: "Giao thất bại được ghi nhận ở Hậu mãi (Module 4).",
                    fields: field("thoi_diem_giao", "Thời điểm giao", { type: "datetime-local", attrs: `max="${now}"`, note: "Để trống = thời điểm hiện tại. Không được ở tương lai hoặc trước lúc bàn giao." }) + noteField(),
                    button: "Giao thành công",
                });
                if (!isTransfer && !paid) add(codCard("Mở sau khi ghi nhận giao thành công."));
                break;
            case "GIAO_THANH_CONG":
                if (!isTransfer && !paid) add(codCard(""));
                else if (isTransfer && !paid) add(transferCard);
                else cards.push(infoCard("Chờ hoàn thành", `Đơn đã giao và thanh toán đầy đủ. Đơn tự chuyển Hoàn thành khi khách xác nhận đã nhận hàng hoặc hết hạn ${shortDate(order.han_cua_so_doi_tra)}.`));
                break;
            case "HOAN_THANH":
                cards.push(infoCard("Đơn đã hoàn thành", "Không còn thao tác vận hành. Đổi/trả (nếu có) xử lý ở Hậu mãi."));
                break;
            case "DA_HUY":
                cards.push(infoCard("Đơn đã hủy", "Không còn thao tác vận hành."));
                break;
            default:
                cards.push(infoCard("Không có thao tác", "Không có thao tác vận hành ở trạng thái hiện tại."));
        }

        // Đính chính: chỉ đơn chuyển khoản đã ghi nhận tiền, trước khi bàn giao, không có yêu cầu hủy (feedback mục 25)
        if (isTransfer && paid && !cancelPending && CORRECTION_STATUSES.includes(status)) {
            cards.push(`<details class="module-panel so-action so-correction"><summary>Đính chính ghi nhận thanh toán</summary>
                <form data-action="ghi-nhan-thanh-toan"><fieldset>
                    ${field("so_tien_thuc_nhan", "Số tiền thực nhận (₫)", { type: "number", required: true, value: payment.so_tien_thuc_nhan ?? "", attrs: 'min="1"' })}
                    ${field("ma_giao_dich_ngan_hang", "Mã giao dịch ngân hàng", { required: true, value: payment.ma_giao_dich_ngan_hang || "", attrs: 'maxlength="50"' })}
                    ${field("ly_do_dieu_chinh", "Lý do đính chính", { required: true, attrs: 'maxlength="120"' })}
                    ${noteField()}
                    <button class="module-button secondary so-submit" type="submit">Lưu đính chính</button>
                </fieldset></form></details>`);
        }
        return cards.join("");
    }

    async function setupStaffOrderDetail(root) {
        const status = root.querySelector("#staff-order-detail-message");
        const main = root.querySelector("#staff-order-main");
        const aside = root.querySelector("#staff-order-actions");
        const afterSalesUrl = root.dataset.afterSales || "/nhan-vien/hau-mai/";

        const render = order => {
            main.innerHTML = staffHead(order, afterSalesUrl) + staffCustomer(order) + staffLines(order)
                + staffPayment(order) + staffDelivery(order) + historyCard(order, "Lịch sử xử lý");
            aside.innerHTML = staffActions(order);
        };
        const load = async () => render((await request(root.dataset.api)).data);

        // Kiểm tra hàng: bật/tắt ô "SL thiếu" theo radio. Bàn giao: đơn vị vận chuyển bắt buộc khi không phải xe tải.
        root.addEventListener("change", event => {
            const radio = event.target.closest('.so-line input[type="radio"]');
            if (radio) {
                const input = radio.closest(".so-line").querySelector('input[type="number"]');
                const short = radio.value === "THIEU";
                input.disabled = !short;
                input.required = short;
                if (short) input.focus(); else input.value = "";
            }
            if (event.target.name === "hinh_thuc_giao") {
                const carrier = event.target.form.querySelector('[name="don_vi_van_chuyen"]');
                if (carrier) carrier.required = event.target.value !== "XE_TAI";
            }
        });

        root.addEventListener("submit", async event => {
            const form = event.target.closest("form[data-action]");
            if (!form) return;
            event.preventDefault();
            const action = form.dataset.action;
            const data = Object.fromEntries(new FormData(form).entries());
            if (action === "kiem-tra-hang") {
                // Gửi đúng định dạng API cũ: {"ket_qua": {ma_ctdh: so_luong_thieu}}, 0 = đủ hàng
                data.ket_qua = {};
                form.querySelectorAll(".so-line").forEach(row => {
                    const short = row.querySelector('input[value="THIEU"]').checked;
                    data.ket_qua[row.dataset.line] = short ? Number(row.querySelector('input[type="number"]').value) : 0;
                });
                Object.keys(data).forEach(key => {
                    if (key.startsWith("kq-") || key.startsWith("thieu-")) delete data[key];
                });
            }
            ["thoi_diem_hen", "thoi_diem_giao"].forEach(key => {
                if (!(key in data)) return;
                if (data[key]) data[key] = new Date(data[key]).toISOString();
                else delete data[key]; // để trống → API dùng thời điểm hiện tại
            });
            if (data.so_tien_thuc_nhan !== undefined) data.so_tien_thuc_nhan = Number(data.so_tien_thuc_nhan);

            const button = form.querySelector('[type="submit"]');
            button.disabled = true;
            try {
                const result = await request(`${root.dataset.api}${action}/`, "POST", data);
                message(status, result.message);
                if (result.data) render(result.data); else await load();
            } catch (error) {
                message(status, error.message, true);
                button.disabled = false;
            }
            status.scrollIntoView({ behavior: "smooth", block: "center" });
        });

        try { await load(); } catch (error) { message(status, error.message, true); }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const cart = document.querySelector("#cart-page");
        const checkout = document.querySelector("#checkout-page");
        const orders = document.querySelector("#customer-orders-page");
        const customerDetail = document.querySelector("#customer-order-detail");
        const staffList = document.querySelector("#staff-orders-page");
        const staffDetail = document.querySelector("#staff-order-detail");
        if (cart) setupCart(cart);
        if (checkout) setupCheckout(checkout);
        if (orders) setupCustomerOrders(orders);
        if (customerDetail) setupCustomerOrderDetail(customerDetail);
        if (staffList) setupStaffOrders(staffList);
        if (staffDetail) setupStaffOrderDetail(staffDetail);
        setupProductVariantPicker();
        setupProductGallery();
        setupAddToCart();
    });
})();
