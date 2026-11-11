(() => {
    const csrf = () => document.querySelector('[name="csrfmiddlewaretoken"]')?.value || "";
    const money = value => `${new Intl.NumberFormat("vi-VN", { useGrouping: true, maximumFractionDigits: 0 }).format(Number(value || 0))} ₫`;
    const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
    const date = value => value ? new Date(value).toLocaleString("vi-VN") : "—";
    const message = (node, text, error = false) => {
        node.className = `module-alert${error ? " error" : " success"}`;
        node.textContent = text;
    };

    async function request(url, method = "GET", data = null) {
        const headers = { Accept: "application/json" };
        const options = { method, credentials: "same-origin", headers };
        if (data !== null) {
            headers["Content-Type"] = "application/json";
            headers["X-CSRFToken"] = csrf();
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

    const renderRecordGroup = (title, records, fields) => {
        const rows = Array.isArray(records) ? records : records ? [records] : [];
        if (!rows.length) return "";
        return `<section class="module-panel order-record-group"><h3>${esc(title)}</h3>
            ${rows.map(record => `<dl class="order-record">
                ${fields.map(([label, key, formatter]) => {
                    const value = record[key];
                    return value === null || value === undefined || value === ""
                        ? ""
                        : `<div><dt>${esc(label)}</dt><dd>${esc(formatter ? formatter(value) : value)}</dd></div>`;
                }).join("")}
            </dl>`).join("")}</section>`;
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
                    <td><strong>${esc(line.ten_sp)}</strong><br><span>${esc(line.huong_vi)} · ${esc(line.quy_cach)}</span>${line.con_ban ? "" : '<br><span class="module-pill danger">Ngừng kinh doanh</span>'}</td>
                    <td>${money(line.don_gia)}<br><small>${esc(line.ten_loai_gia)}</small></td>
                    <td><form class="module-inline-form" data-update="${esc(line.ma_ctgh)}"><button class="module-button secondary" type="button" data-step="-1" aria-label="Giảm số lượng">−</button><input type="number" min="1" name="so_luong" value="${line.so_luong}" aria-label="Số lượng"><button class="module-button secondary" type="button" data-step="1" aria-label="Tăng số lượng">+</button><button class="module-button secondary" type="submit">Cập nhật</button></form></td>
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
                `<option value="${esc(item.ma_dia_chi)}" ${String(item.ma_dia_chi) === String(preferred) ? "selected" : ""}>${esc(item.ten_nguoi_nhan)} · ${esc(addressText(item))}</option>`
            ).join("");
            addressSelect.disabled = !addressList.length;
            root.querySelector("#checkout-no-address").hidden = addressList.length > 0;

            let orderData;
            if (addressList.length) {
                const query = queryFor(selected, { ma_dia_chi: addressSelect.value });
                orderData = (await request(`${root.dataset.api}?${query}`)).data;
                const chosenAddress = addressList.find(item => String(item.ma_dia_chi) === String(addressSelect.value)) || orderData.dia_chi;
                root.querySelector("#checkout-address-summary").textContent =
                    `${chosenAddress.ten_nguoi_nhan} · ${chosenAddress.so_dien_thoai} · ${addressText(chosenAddress)}`;
            } else {
                orderData = (await request(`${root.dataset.cartApi}?${queryFor(selected)}`)).data;
                root.querySelector("#checkout-address-summary").textContent = "";
            }

            const lines = orderData.cac_dong || [];
            root.querySelector("#checkout-items").innerHTML = lines.map(line =>
                `<div class="module-summary" style="padding:10px 0;border-bottom:1px solid var(--line)"><span>${esc(line.ten_sp)} · ${esc(line.huong_vi)} · ${esc(line.quy_cach)} × ${line.so_luong}</span><strong>${money(line.thanh_tien)}</strong></div>`
            ).join("");
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
                location.assign(`/don-cua-toi/${encodeURIComponent(result.data.ma_dh)}/`);
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
                    <tr><td><strong>${esc(order.ma_dh)}</strong></td><td>${date(order.ngay_dat)}</td>
                    <td>${order.chi_tiet.map(line => `${esc(line.ten_sp)} × ${line.so_luong}`).join("<br>")}</td>
                    <td>${money(order.tong_thanh_toan)}<br><small>${esc(order.ten_trang_thai_thanh_toan)}</small></td>
                    <td><span class="module-pill">${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</span></td>
                    <td>${esc(order.ten_trang_thai_hau_mai || "—")}</td><td><a href="/don-cua-toi/${encodeURIComponent(order.ma_dh)}/">Chi tiết →</a></td></tr>`
                ).join("") : '<tr><td colspan="7" class="module-empty">Chưa có đơn hàng phù hợp.</td></tr>';
            } catch (error) { message(status, error.message, true); }
        };
        filter.addEventListener("change", load);
        await load();
    }

    function renderLines(lines, showSupply = false) {
        return `<div class="module-table-wrap"><table class="module-table"><thead><tr><th>Sản phẩm</th><th>Đơn giá</th><th>Số lượng</th><th>Thành tiền</th>${showSupply ? "<th>Tình trạng cung ứng</th>" : ""}</tr></thead><tbody>${lines.map(line =>
            `<tr><td><strong>${esc(line.ten_sp)}</strong><br>${esc(line.huong_vi)} · ${esc(line.quy_cach)}</td><td>${money(line.don_gia)}<br><small>${esc(line.ten_loai_gia)}</small></td><td>${line.so_luong}</td><td>${money(line.thanh_tien)}</td>${showSupply ? `<td><span class="module-pill">${esc(line.ten_ket_qua_kiem_tra || "Chưa kiểm tra")}</span>${line.so_luong_thieu ? `<br><small>Thiếu ${line.so_luong_thieu}</small>` : ""}</td>` : ""}</tr>`
        ).join("")}</tbody></table></div>`;
    }

    function renderOrderProgress(status) {
        const steps = [
            { statuses: ["CHO_XAC_NHAN"], label: "Đặt hàng" },
            { statuses: ["DA_XAC_NHAN", "CHO_THANH_TOAN"], label: "Xác nhận đơn" },
            { statuses: ["DANG_CHUAN_BI", "CHO_BO_SUNG"], label: "Chuẩn bị hàng" },
            { statuses: ["SAN_SANG_GIAO", "DANG_GIAO"], label: "Đang giao" },
            { statuses: ["GIAO_THANH_CONG"], label: "Đã giao" },
            { statuses: ["HOAN_THANH"], label: "Hoàn thành" },
        ];
        if (status === "DA_HUY") return '<p class="module-alert error">Đơn hàng đã bị hủy.</p>';
        const current = steps.findIndex(step => step.statuses.includes(status));
        return { steps, current };
    }

    function renderStatusHistory(items) {
        const groups = [];
        (items || []).forEach(item => {
            const previous = groups[groups.length - 1];
            if (previous && previous.trang_thai === item.trang_thai
                && item.trang_thai_cu === item.trang_thai) {
                previous.events.push(item);
            } else {
                groups.push({ trang_thai: item.trang_thai, ten_trang_thai: item.ten_trang_thai, events: [item] });
            }
        });
        return groups.map(group => `<li><strong>${esc(group.ten_trang_thai)}</strong>
            ${group.events.map(item => `<div>· ${date(item.thoi_diem)} · ${esc(item.ten_nhan_vien || item.ten_tac_nhan)}${item.ghi_chu ? ` · ${esc(item.ghi_chu)}` : ""}</div>`).join("")}</li>`).join("")
            || "<li>Chưa có lịch sử.</li>";
    }

    async function setupCustomerOrderDetail(root) {
        const messageNode = root.querySelector("#order-detail-message");
        const content = root.querySelector("#order-detail-content");
        const orderApi = root.dataset.api;
        const load = async () => {
            const result = await request(orderApi);
            const order = result.data;
            const qr = order.thong_tin_chuyen_khoan;
            const withinReturnWindow = Boolean(order.han_cua_so_doi_tra)
                && new Date(order.han_cua_so_doi_tra) >= new Date();
            const canConfirm = withinReturnWindow && !order.thoi_diem_xac_nhan_nhan_hang;
            const canRequestReturn = withinReturnWindow
                && !order.thoi_diem_xac_nhan_nhan_hang
                && ["GIAO_THANH_CONG", "HOAN_THANH"].includes(order.trang_thai);
            const progress = renderOrderProgress(order.trang_thai);
            const timeline = progress.steps
                ? `<ol class="order-progress" aria-label="Tiến độ đơn hàng">${progress.steps.map((step, index) => {
                    const event = (order.lich_su_trang_thai || [])
                        .filter(item => step.statuses.includes(item.trang_thai))
                        .at(-1);
                    const completed = index <= progress.current;
                    return `<li class="${completed ? "is-complete" : ""}${index === progress.current ? " is-current" : ""}"${index === progress.current ? ' aria-current="step"' : ""}>
                        <span class="order-progress-icon" aria-hidden="true">${completed ? "✓" : index + 1}</span>
                        <strong>${esc(step.label)}</strong>
                        <small>${event ? date(event.thoi_diem) : "Chờ cập nhật"}</small>
                    </li>`;
                }).join("")}</ol>`
                : progress;
            content.innerHTML = `
                <section class="module-panel"><span class="module-eyebrow">${esc(order.ma_dh)} · ${date(order.ngay_dat)}</span><h2>${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</h2>
                ${order.ten_trang_thai_hau_mai ? `<p><span class="module-pill warning">Hậu mãi: ${esc(order.ten_trang_thai_hau_mai)}</span></p>` : ""}
                <h3>Sản phẩm</h3>${renderLines(order.chi_tiet)}
                <hr><p><strong>Người nhận:</strong> ${esc(order.ho_ten_nguoi_nhan)} · ${esc(order.sdt_nguoi_nhan)}</p><p><strong>Địa chỉ:</strong> ${esc(order.dia_chi_giao_hang)}, ${esc(order.ten_tinh)}</p>
                <p><strong>Thanh toán:</strong> ${esc(order.ten_pttt)} · ${esc(order.ten_trang_thai_thanh_toan)}</p>
                <div class="module-summary"><span>Tiền hàng</span><strong>${money(order.tong_tien_hang)}</strong><span>Phí giao hàng</span><strong>${money(order.phi_van_chuyen)}</strong><span class="module-total">Tổng thanh toán</span><strong class="module-total">${money(order.tong_thanh_toan)}</strong></div>
                ${qr ? `<div class="module-alert"><strong>Chuyển khoản · ${money(qr.so_tien)}</strong><p>Ngân hàng / tài khoản: ${esc(qr.tai_khoan)}</p><p>Nội dung chuyển khoản: <code>${esc(qr.noi_dung)}</code></p><p>Hạn thanh toán: ${date(qr.han_thanh_toan)}</p><fieldset><legend>Mô phỏng thanh toán (bản thử nghiệm)</legend><label><input type="radio" name="payment-result" value="THANH_CONG" checked> Giao dịch thành công</label><label><input type="radio" name="payment-result" value="THAT_BAI"> Giao dịch thất bại</label><button class="module-button" data-payment>Gửi kết quả mô phỏng</button></fieldset></div>` : ""}
                ${canConfirm ? '<button class="module-button" data-received>Đã nhận hàng</button>' : ""}
                ${canRequestReturn ? `<p><a href="/tai-khoan/hau-mai/?ma_dh=${encodeURIComponent(order.ma_dh)}">Yêu cầu đổi/trả →</a></p>` : ""}
                <p><a href="/tai-khoan/hau-mai/?ma_dh=${encodeURIComponent(order.ma_dh)}">${["CHO_XAC_NHAN", "DA_XAC_NHAN", "CHO_THANH_TOAN", "DANG_CHUAN_BI", "CHO_BO_SUNG"].includes(order.trang_thai) ? "Yêu cầu hủy / theo dõi hậu mãi" : "Theo dõi hậu mãi"} →</a></p></section>
                <section class="module-panel"><h2>Tiến độ đơn hàng</h2>${timeline}<h2>Lịch sử trạng thái</h2><ol>${renderStatusHistory(order.lich_su_trang_thai)}</ol>${order.trang_thai === "CHO_BO_SUNG" ? `<p><strong>Hẹn bổ sung hàng:</strong> ${date(order.thoi_diem_hen_cung_cap)}</p>` : ""}</section>`;
        };
        root.addEventListener("click", async event => {
            try {
                if (event.target.closest("[data-received]")) {
                    await request(`${orderApi}da-nhan-hang/`, "POST", {});
                    message(messageNode, "Đã xác nhận nhận hàng.");
                    await load();
                }
                if (event.target.closest("[data-payment]")) {
                    const value = root.querySelector('[name="payment-result"]:checked')?.value;
                    await request(`${orderApi}payment/`, "POST", { ket_qua: value });
                    message(messageNode, "Đã ghi nhận kết quả mô phỏng thanh toán.");
                    await load();
                }
            } catch (error) { message(messageNode, error.message, true); }
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
                <tr><td><strong>${esc(order.ma_dh)}</strong><br><small>${date(order.ngay_dat)}</small></td><td>${esc(order.ten_khach_hang)}<br><small>${esc(order.ma_kh)}</small></td>
                <td>${esc(order.ten_loai_khach)}</td><td>${money(order.tong_thanh_toan)}</td><td><span class="module-pill">${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</span></td><td>${esc(order.ten_trang_thai_thanh_toan)}</td><td>${esc(order.ten_trang_thai_hau_mai || "—")}</td>
                <td><a href="/don-hang/${encodeURIComponent(order.ma_dh)}/">Mở đơn →</a></td></tr>`).join("") : '<tr><td colspan="8" class="module-empty">Không có đơn phù hợp bộ lọc.</td></tr>';
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

    const actionForms = order => {
        if (order.trang_thai_hau_mai === "CHO_HUY") {
            return '<section class="module-panel module-alert warning"><strong>Đơn đang chờ xử lý yêu cầu hủy.</strong><p>Các thao tác vận hành bị tạm khóa cho đến khi yêu cầu hậu mãi được giải quyết.</p></section>';
        }
        const input = (name, label, type = "text", required = false, value = "") =>
            `<div><label>${label}</label><input name="${name}" type="${type}" value="${esc(value)}" ${required ? "required" : ""}></div>`;
        const textarea = `<div><label>Ghi chú</label><textarea name="ghi_chu"></textarea></div>`;
        const form = (action, title, fields) => `<form data-action="${action}" class="module-panel"><h3>${title}</h3><div class="module-form-grid">${fields}</div><button class="module-button" type="submit">Ghi nhận</button></form>`;
        const shortages = (order.chi_tiet || []).map(line =>
            `<div><label>${esc(line.ten_sp)} · ${esc(line.huong_vi)} · ${esc(line.quy_cach)} (đặt ${line.so_luong}; ${esc(line.ten_ket_qua_kiem_tra || "Chưa kiểm tra")})</label><input type="number" min="0" max="${line.so_luong}" name="thieu-${esc(line.ma_ctdh)}" value="${line.so_luong_thieu || 0}" aria-label="Số lượng thiếu ${esc(line.ten_sp)}"></div>`
        ).join("");
        const isChecked = (order.chi_tiet || []).every(line => line.ket_qua_kiem_tra === "DU");
        const hasShortage = (order.chi_tiet || []).some(line => line.ket_qua_kiem_tra === "THIEU");
        const payment = order.giao_dich || {};
        const paymentAmount = payment.so_tien_thuc_nhan || payment.so_tien_phai_thu || order.tong_thanh_toan;
        const paymentForm = form("ghi-nhan-thanh-toan", "Ghi nhận thanh toán chuyển khoản",
            input("so_tien_thuc_nhan", "Số tiền thực nhận (đ)", "number", true, payment.so_tien_phai_thu || paymentAmount)
            + input("ma_giao_dich_ngan_hang", "Mã giao dịch ngân hàng", "text", true)
            + input("ly_do_dieu_chinh", "Lý do (bắt buộc khi đính chính)")
            + textarea);
        const correctionForm = !["HOAN_THANH", "DA_HUY"].includes(order.trang_thai)
            && order.ma_pttt === "PT001" && order.trang_thai_thanh_toan === "DA_THANH_TOAN"
            ? form("ghi-nhan-thanh-toan", "Đính chính ghi nhận thanh toán",
                input("so_tien_thuc_nhan", "Số tiền thực nhận (đ)", "number", true, payment.so_tien_thuc_nhan || "")
                + input("ma_giao_dich_ngan_hang", "Mã giao dịch ngân hàng", "text", true, payment.ma_giao_dich_ngan_hang || "")
                + input("ly_do_dieu_chinh", "Lý do đính chính", "text", true)
                + textarea)
            : "";
        switch (order.trang_thai) {
            case "CHO_XAC_NHAN": {
                return `<form data-action="kiem-tra-hang" class="module-panel"><h3>Kiểm tra cung ứng</h3><div class="module-form-grid">${shortages}${textarea}</div><button class="module-button" type="submit">Lưu kết quả kiểm tra</button></form>`
                    + (isChecked ? form("xac-nhan", "Xác nhận đơn", textarea) : hasShortage
                        ? form("cho-bo-sung", "Chuyển đơn sang chờ bổ sung hàng", input("thoi_diem_hen", "Thời điểm hẹn cung cấp", "datetime-local", true) + textarea)
                        : '<section class="module-panel"><p>Vui lòng lưu kết quả kiểm tra đủ hàng trước khi xác nhận đơn.</p></section>');
            }
            case "CHO_BO_SUNG":
                return form("gia-han", "Gia hạn thời điểm bổ sung", input("thoi_diem_hen", "Thời điểm hẹn mới", "datetime-local", true) + textarea)
                    + form("da-du-hang", "Đã đủ hàng", textarea);
            case "DA_XAC_NHAN":
                return form("bat-dau-chuan-bi", "Bắt đầu chuẩn bị", textarea) + correctionForm;
            case "CHO_THANH_TOAN":
                return order.trang_thai_thanh_toan === "DA_THANH_TOAN"
                    ? form("bat-dau-chuan-bi", "Bắt đầu chuẩn bị", textarea) + correctionForm
                    : paymentForm;
            case "DANG_CHUAN_BI":
                return `<form data-action="kiem-tra-hang" class="module-panel"><h3>Kiểm tra lại cung ứng</h3><div class="module-form-grid">${shortages}${textarea}</div><button class="module-button secondary" type="submit">Cập nhật kiểm tra</button></form>`
                    + (hasShortage
                        ? form("cho-bo-sung", "Chuyển đơn sang chờ bổ sung hàng", input("thoi_diem_hen", "Thời điểm hẹn cung cấp", "datetime-local", true) + textarea)
                        : isChecked
                            ? form("san-sang-giao", "Sẵn sàng giao", textarea)
                            : '<section class="module-panel"><p>Vui lòng kiểm tra và đánh dấu đủ hàng trước khi chuyển sang giao.</p></section>')
                    + correctionForm;
            case "SAN_SANG_GIAO":
                return form("ban-giao", "Bàn giao vận chuyển", `<div><label>Hình thức giao</label><select name="hinh_thuc_giao"><option value="XE_TAI" ${order.goi_y_hinh_thuc_giao.ma === "XE_TAI" ? "selected" : ""}>Xe tải nội bộ</option><option value="SHIPPER" ${order.goi_y_hinh_thuc_giao.ma === "SHIPPER" ? "selected" : ""}>Shipper giao nhanh</option><option value="DVVC" ${order.goi_y_hinh_thuc_giao.ma === "DVVC" ? "selected" : ""}>Đơn vị vận chuyển TMĐT</option></select></div>` + input("don_vi_van_chuyen", "Đơn vị vận chuyển") + input("sdt_shipper", "Số điện thoại shipper") + input("ma_van_don", "Mã vận đơn") + textarea);
            case "DANG_GIAO":
                return form("giao-thanh-cong", "Ghi nhận giao thành công", input("thoi_diem_giao", "Thời điểm giao", "datetime-local", true) + textarea) + correctionForm;
            case "GIAO_THANH_CONG":
                if (order.ma_pttt === "PT002" && order.trang_thai_thanh_toan !== "DA_THANH_TOAN") {
                    return form("thu-cod", "Ghi nhận thu COD", input("so_tien_thuc_nhan", "Số tiền thực nhận", "number", true) + textarea);
                }
                if (order.ma_pttt === "PT001" && order.trang_thai_thanh_toan !== "DA_THANH_TOAN") {
                    return paymentForm;
                }
                return '<section class="module-panel"><p>Đơn đã giao và thanh toán đầy đủ.</p></section>' + correctionForm;
            default:
                return correctionForm || '<section class="module-panel"><p>Không có thao tác vận hành được phép ở trạng thái hiện tại.</p></section>';
        }
    };

    async function setupStaffOrderDetail(root) {
        const status = root.querySelector("#staff-order-detail-message");
        const content = root.querySelector("#staff-order-detail-content");
        const load = async () => {
            const result = await request(root.dataset.api);
            const order = result.data;
            const paymentRecords = renderRecordGroup("Thanh toán", order.giao_dich, [
                ["Trạng thái", "ten_trang_thai"],
                ["Số tiền phải thu", "so_tien_phai_thu", money],
                ["Số tiền đã nhận", "so_tien_thuc_nhan", money],
                ["Thời điểm thanh toán", "thoi_diem_thanh_toan", date],
                ["Mã giao dịch", "ma_giao_dich"],
                ["Mã giao dịch ngân hàng", "ma_giao_dich_ngan_hang"],
                ["Nhân viên ghi nhận", "ten_nhan_vien_ghi_nhan"],
                ["Ghi chú", "ghi_chu"]
            ]);
            const deliveryRecords = renderRecordGroup("Lịch sử giao hàng", order.cac_lan_giao, [
                ["Lần giao", "lan_giao"],
                ["Trạng thái", "ten_ket_qua_giao"],
                ["Hình thức giao", "ten_hinh_thuc_giao"],
                ["Đơn vị vận chuyển", "don_vi_van_chuyen"],
                ["Mã vận đơn", "ma_van_don"],
                ["Thời điểm bàn giao", "thoi_diem_ban_giao", date],
                ["Thời điểm giao xong", "thoi_diem_giao_xong", date],
                ["Lý do giao thất bại", "ly_do_that_bai"]
            ]);
            content.innerHTML = `
                <section class="module-panel"><span class="module-eyebrow">${esc(order.ma_dh)} · ${date(order.ngay_dat)}</span><h2>${esc(order.ten_trang_thai_hien_thi || order.ten_trang_thai)}</h2>
                <p><strong>Khách:</strong> ${esc(order.ten_khach_hang)} (${esc(order.ma_kh)}) · ${esc(order.ten_loai_khach)}</p>
                <p><strong>Giao đến:</strong> ${esc(order.ho_ten_nguoi_nhan)} · ${esc(order.sdt_nguoi_nhan)} · ${esc(order.dia_chi_giao_hang)}</p>
                <p><strong>Thanh toán:</strong> ${esc(order.ten_pttt)} / ${esc(order.ten_trang_thai_thanh_toan)} · ${money(order.tong_thanh_toan)}</p>
                ${order.ten_trang_thai_hau_mai ? `<p class="module-alert warning"><strong>Đang có trạng thái hậu mãi:</strong> ${esc(order.ten_trang_thai_hau_mai)}</p>` : ""}
                <h3>Dòng hàng</h3>${renderLines(order.chi_tiet, true)}
                ${paymentRecords}
                ${deliveryRecords}
                <h3>Lịch sử xử lý</h3><ol>${renderStatusHistory(order.lich_su_trang_thai)}</ol>
                ${order.trang_thai === "CHO_BO_SUNG" && order.thoi_diem_hen_cung_cap ? `<p><strong>Hẹn bổ sung:</strong> ${date(order.thoi_diem_hen_cung_cap)}</p>` : ""}
                </section>${actionForms(order)}`;
        };
        root.addEventListener("submit", async event => {
            const form = event.target.closest("[data-action]");
            if (!form) return;
            event.preventDefault();
            const values = Object.fromEntries(new FormData(form).entries());
            if (form.dataset.action === "kiem-tra-hang") {
                values.ket_qua = {};
                Object.entries(values).forEach(([key, value]) => {
                    if (key.startsWith("thieu-")) {
                        values.ket_qua[key.slice(6)] = Number(value);
                        delete values[key];
                    }
                });
            }
            if (values.thoi_diem_hen || values.thoi_diem_giao) {
                const key = values.thoi_diem_hen ? "thoi_diem_hen" : "thoi_diem_giao";
                values[key] = new Date(values[key]).toISOString();
            }
            try {
                const result = await request(`${root.dataset.api}${form.dataset.action}/`, "POST", values);
                message(status, result.message);
                await load();
            } catch (error) { message(status, error.message, true); }
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
