(() => {
    const makeSvgElement = (name, attributes = {}) => {
        const element = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
        return element;
    };

    const calculate4IntervalScale = (maxVal) => {
        if (!maxVal || maxVal <= 0) {
            return { yMax: 4, yTicks: [4, 3, 2, 1, 0], step: 1 };
        }
        const rawStep = maxVal / 4;
        const exponent = Math.floor(Math.log10(rawStep));
        const power = Math.pow(10, exponent);
        const fraction = rawStep / power;

        let niceFraction;
        if (fraction <= 1.0) niceFraction = 1.0;
        else if (fraction <= 1.25) niceFraction = 1.25;
        else if (fraction <= 1.5) niceFraction = 1.5;
        else if (fraction <= 2.0) niceFraction = 2.0;
        else if (fraction <= 2.5) niceFraction = 2.5;
        else if (fraction <= 5.0) niceFraction = 5.0;
        else niceFraction = 10.0;

        const step = niceFraction * power;
        const yMax = step * 4;
        const yTicks = [yMax, step * 3, step * 2, step, 0];
        return { yMax, yTicks, step };
    };

    const formatTick = val => {
        if (Math.abs(val) < 1e-6) return "0";
        if (Number.isInteger(val)) return val.toLocaleString("vi-VN");
        return Number(val.toFixed(2)).toLocaleString("vi-VN");
    };

    const renderRevenueChart = () => {
        const dataElement = document.getElementById("report-timeline");
        const chart = document.getElementById("revenue-chart");
        if (!dataElement || !chart) return;

        const data = JSON.parse(dataElement.textContent || "{}");
        const labels = data.labels || [];
        const revenue = data.revenue_millions || [];
        const exactRevenues = data.revenue_exact || [];
        const orders = data.orders_count || [];

        // Không có dữ liệu: hiện dòng "Chưa có dữ liệu trong kỳ này." chỉ khi không có nhãn trục nào
        const hasRevenue = exactRevenues.some(v => (v || 0) > 0) || revenue.some(v => (v || 0) > 0);
        const hasOrders = orders.some(o => (o || 0) > 0);
        if (!labels.length) {
            chart.replaceChildren();
            const empty = document.createElement("div");
            empty.className = "report-chart-empty";
            empty.textContent = "Chưa có dữ liệu trong kỳ này.";
            chart.append(empty);
            return;
        }

        // Kiểm tra xem doanh thu cả kỳ có dưới 1 triệu không
        // Nếu max doanh thu < 1 triệu (hoặc demo vài chục/trăm nghìn): đổi sang "nghìn đồng"
        const maxExactVnd = Math.max(...exactRevenues, 0);
        const isThousandUnit = maxExactVnd < 1_000_000;

        // Cập nhật phụ đề biểu đồ theo đơn vị
        const subtitleEl = document.getElementById("revenue-chart-subtitle");
        if (subtitleEl) {
            subtitleEl.textContent = isThousandUnit ? "Doanh thu (nghìn đồng)" : "Doanh thu (triệu đồng)";
        }

        const width = 1000;
        const height = 320;
        const margin = { top: 28, right: 30, bottom: 46, left: 60 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;

        // Giá trị quy đổi cho trục Y
        // Nếu nghìn đồng: exactVnd / 1000
        // Nếu triệu đồng: exactVnd / 1000000
        const divisor = isThousandUnit ? 1_000 : 1_000_000;
        const scaledRevenues = labels.map((_, i) => {
            const exact = exactRevenues[i] !== undefined ? exactRevenues[i] : Math.round((revenue[i] || 0) * 1_000_000);
            return exact / divisor;
        });

        const maxScaledVal = Math.max(...scaledRevenues, 0);
        // Trục dọc tự co giãn theo giá trị lớn nhất, chia đúng 4 khoảng đều
        const { yMax, yTicks } = calculate4IntervalScale(maxScaledVal);

        const stepX = plotWidth / labels.length;
        const xAt = index => margin.left + stepX * (index + 0.5);

        const points = labels.map((label, index) => {
            const val = scaledRevenues[index] || 0;
            const ratio = yMax > 0 ? val / yMax : 0;
            const rawHeight = ratio * plotHeight;
            const barHeight = val > 0 ? Math.max(4, rawHeight) : 0;
            const exactVnd = exactRevenues[index] !== undefined ? exactRevenues[index] : Math.round((revenue[index] || 0) * 1_000_000);
            const ord = orders[index] || 0;
            return {
                x: xAt(index),
                revenueY: margin.top + plotHeight - barHeight,
                height: barHeight,
                scaledVal: val,
                exactVnd,
                orders: ord,
                label,
            };
        });

        const svg = makeSvgElement("svg", {
            class: "report-chart",
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": "Doanh thu theo thời gian dạng cột",
            preserveAspectRatio: "xMidYMid meet",
        });

        // 4 khoảng vạch chia ngang và số trục Y bên trái (chỉ để lại đường ngang, bỏ đường đứng)
        const gridGroup = makeSvgElement("g");

        yTicks.forEach(tickVal => {
            const ratio = (yMax - tickVal) / yMax;
            const y = margin.top + plotHeight * ratio;
            gridGroup.append(
                makeSvgElement("line", {
                    class: "report-chart-grid",
                    x1: margin.left,
                    x2: width - margin.right,
                    y1: y,
                    y2: y,
                    stroke: "#edf0eb",
                    "stroke-width": "1",
                }),
            );
            const revenueLabel = makeSvgElement("text", {
                x: margin.left - 10,
                y: y + 4,
                "text-anchor": "end",
                fill: "#173c32",
                "font-size": "11.5",
                "font-weight": "600",
            });
            revenueLabel.textContent = formatTick(tickVal);
            gridGroup.append(revenueLabel);
        });
        svg.append(gridGroup);

        // Trục dọc Y (trái)
        const leftAxisLine = makeSvgElement("line", {
            x1: margin.left,
            y1: margin.top,
            x2: margin.left,
            y2: height - margin.bottom,
            stroke: "#b5c2ba",
            "stroke-width": "1.2",
        });
        svg.append(leftAxisLine);

        // Trục ngang X (dưới)
        const xAxisLine = makeSvgElement("line", {
            x1: margin.left,
            y1: height - margin.bottom,
            x2: width - margin.right,
            y2: height - margin.bottom,
            stroke: "#b5c2ba",
            "stroke-width": "1.2",
        });
        svg.append(xAxisLine);

        const barWidth = Math.max(1.5, Math.min(36, stepX * 0.65));
        const bars = makeSvgElement("g", { class: "report-chart-bars" });
        const labelsGroup = makeSvgElement("g", { class: "report-chart-values" });
        const hitZoneGroup = makeSvgElement("g", { class: "report-chart-hitzones" });

        points.forEach(point => {
            let bar = null;
            if (point.height > 0) {
                bar = makeSvgElement("rect", {
                    x: point.x - barWidth / 2,
                    y: point.revenueY,
                    width: barWidth,
                    height: point.height,
                    rx: Math.min(3, Math.max(1, barWidth / 2)),
                    fill: "rgba(37, 97, 79, .82)",
                    style: "transition: fill 0.18s ease; cursor: pointer;",
                });
                bars.append(bar);

                // Hiển thị số tiền vắn tắt phía trên cột nếu đủ chỗ
                if (barWidth >= 12 || labels.length <= 15) {
                    let displayVal;
                    if (point.exactVnd >= 1_000_000) {
                        displayVal = (point.exactVnd / 1_000_000).toFixed(1).replace(".", ",") + " tr";
                    } else if (point.exactVnd >= 1_000) {
                        displayVal = Math.round(point.exactVnd / 1000) + "k";
                    } else {
                        displayVal = point.exactVnd + "đ";
                    }
                    const valText = makeSvgElement("text", {
                        x: point.x,
                        y: Math.max(margin.top - 6, point.revenueY - 6),
                        "text-anchor": "middle",
                        class: "report-bar-value",
                        fill: "#25614f",
                        "font-size": "10",
                        "font-weight": "600",
                    });
                    valText.textContent = displayVal;
                    labelsGroup.append(valText);
                }
            }

            // Hit zone toàn chiều cao cho mỗi cột để hover mượt mà và hiển thị tooltip
            const hitArea = makeSvgElement("rect", {
                x: point.x - stepX / 2,
                y: margin.top,
                width: stepX,
                height: plotHeight,
                fill: "transparent",
                style: "cursor: pointer;",
            });
            const exactVndStr = point.exactVnd.toLocaleString("vi-VN");
            const orderInfo = ` • ${point.orders} đơn`;
            const title = makeSvgElement("title");
            title.textContent = `${point.label}: ${exactVndStr} đ${orderInfo}`;
            hitArea.append(title);

            if (bar) {
                hitArea.addEventListener("mouseenter", () => {
                    bar.style.fill = "#144638";
                });
                hitArea.addEventListener("mouseleave", () => {
                    bar.style.fill = "";
                });
            }
            hitZoneGroup.append(hitArea);
        });

        svg.append(bars);
        svg.append(labelsGroup);
        svg.append(hitZoneGroup);

        // Trục ngang:
        // - Theo tháng (Năm nay): hiện đủ Tháng 1 đến Tháng 12
        // - Hôm nay: hiện đủ 24 h (0h, 1h, ... 23h)
        // - Kỳ ngắn (7 ngày): hiện hết 7 ngày
        // - Theo ngày (Quý, Tháng, Tùy chọn): khoảng cách thời gian xa xíu (5-10 ngày), đều nhau, không đè chữ
        const totalPoints = points.length;
        const isHourlyLabel = text => /^\d{1,2}h$/.test(text);
        const isHourlySeries = points.every(p => isHourlyLabel(String(p.label || "").trim()));
        const isDailyLabel = text => /^\d{1,2}\/\d{1,2}$/.test(text);
        const isDailySeries = points.every(p => isDailyLabel(String(p.label || "").trim()));

        let lastShownX = -999;
        const minGapPx = isHourlySeries ? 24 : 36;

        points.forEach(point => {
            const rawLabel = String(point.label || "").trim();
            let showLabel = true;
            let text = rawLabel;

            if (isDailySeries) {
                const [day, month] = rawLabel.split("/").map(n => parseInt(n, 10));
                text = `${day}/${month}`;
                if (totalPoints <= 7) {
                    // Kỳ ngắn (7 ngày): hiện hết 7 ngày
                    showLabel = true;
                } else if (totalPoints <= 35) {
                    // Theo ngày (Tháng): hiện nhãn ngày 1, 5, 10, 15, 20, 25, 30
                    showLabel = [1, 5, 10, 15, 20, 25, 30].includes(day);
                } else if (totalPoints <= 100) {
                    // Theo ngày (Quý, Tùy chọn ~3 tháng): khoảng cách thời gian xa xíu (ngày 1, 10, 20) để đều nhau, không chồng lấn
                    showLabel = (day === 1 || day === 10 || day === 20);
                } else {
                    // Tùy chọn dài (> 100 ngày): chỉ ngày 1 mỗi tháng để đều nhau
                    showLabel = (day === 1);
                }
            } else if (isHourlySeries) {
                // Hôm nay: hiện hết 24 h
                showLabel = true;
                text = rawLabel;
            } else {
                // Theo tháng (Năm nay): hiện đủ Tháng 1 đến Tháng 12
                const monthYear = rawLabel.match(/^(\d{1,2})\/\d{4}$/);
                if (monthYear) text = `Tháng ${parseInt(monthYear[1], 10)}`;
                showLabel = true;
            }

            // Chống đè chữ: đảm bảo khoảng cách tối thiểu giữa 2 nhãn liên tiếp
            if (!showLabel || (point.x - lastShownX < minGapPx)) return;
            lastShownX = point.x;

            const label = makeSvgElement("text", {
                x: point.x,
                y: height - 12,
                "text-anchor": "middle",
                fill: "#64716a",
                "font-size": isHourlySeries ? "10" : "11",
            });
            label.textContent = text;
            svg.append(label);
        });

        // Vẽ biểu đồ một lần duy nhất, thay thế nội dung cũ chống chớp đè
        chart.replaceChildren(svg);
    };

    const renderTopProductsChart = () => {
        const dataElement = document.getElementById("report-top-products");
        const chart = document.getElementById("top-products-chart");
        if (!dataElement || !chart) return;

        let topProducts = [];
        try {
            topProducts = JSON.parse(dataElement.textContent) || [];
        } catch (e) {
            topProducts = [];
        }

        // Chỉ lấy top 5
        topProducts = topProducts.slice(0, 5);

        if (!topProducts.length || !topProducts.some(p => (p.qty || 0) > 0)) {
            chart.innerHTML = '<div class="report-chart-empty" style="padding: 40px 10px; text-align: center; color: #888; font-size: 13px;">Chưa có sản phẩm bán trong kỳ này.</div>';
            return;
        }

        const count = topProducts.length;
        const width = 600;
        const marginLeft = 190;
        const marginRight = 45;
        const marginTop = 16;
        const marginBottom = 30;
        const plotWidth = width - marginLeft - marginRight;

        const barHeight = 22;
        const gap = 12;
        // Chiều cao tự thích ứng theo số lượng sản phẩm (1 đến 5 sp)
        // để khi chỉ có 1 hoặc 2 sp không bị khoảng trống khổng lồ lơ lửng
        const plotHeight = Math.max(count * (barHeight + gap) - gap, 36);
        const height = marginTop + plotHeight + marginBottom;

        const maxQty = Math.max(...topProducts.map(p => p.qty || 0), 1);

        // Tính thang đo trục X (ví dụ 0, 5, 10, 15, 20, 25, 30...)
        let step = 1;
        if (maxQty <= 5) step = 1;
        else if (maxQty <= 10) step = 2;
        else if (maxQty <= 25) step = 5;
        else if (maxQty <= 50) step = 10;
        else if (maxQty <= 100) step = 20;
        else if (maxQty <= 250) step = 50;
        else step = Math.ceil(maxQty / 5);

        const tickCount = Math.max(3, Math.ceil(maxQty / step));
        const xMax = tickCount * step;
        const xTicks = [];
        for (let i = 0; i <= tickCount; i++) {
            xTicks.push(i * step);
        }

        const svg = makeSvgElement("svg", {
            viewBox: `0 0 ${width} ${height}`,
            style: "width: 100%; height: auto; display: block; font-family: inherit;",
        });

        // X-ticks & nhãn số (chỉ giữ vạch chia và số trục X, không vẽ đường đứng)
        const gridGroup = makeSvgElement("g");
        xTicks.forEach(tick => {
            const xPos = marginLeft + (tick / xMax) * plotWidth;

            // Vạch chia nhỏ trên trục X
            const tickMark = makeSvgElement("line", {
                x1: xPos, y1: height - marginBottom,
                x2: xPos, y2: height - marginBottom + 4,
                stroke: "#b5c2ba", "stroke-width": "1",
            });
            gridGroup.append(tickMark);

            // Số trục X (full màu đen, không có viền stroke)
            const tickText = makeSvgElement("text", {
                x: xPos, y: height - marginBottom + 16,
                "text-anchor": "middle", "font-size": "11.5",
                fill: "#000",
                stroke: "none",
                "font-weight": "600",
                style: "fill: #000 !important; stroke: none !important;",
            });
            tickText.textContent = tick.toLocaleString("vi-VN");
            gridGroup.append(tickText);
        });
        svg.append(gridGroup);

        // Trục dọc Y
        const yAxisLine = makeSvgElement("line", {
            x1: marginLeft, y1: marginTop - 4,
            x2: marginLeft, y2: height - marginBottom,
            stroke: "#b5c2ba", "stroke-width": "1.2",
        });
        svg.append(yAxisLine);

        // Trục ngang X
        const xAxisLine = makeSvgElement("line", {
            x1: marginLeft, y1: height - marginBottom,
            x2: marginLeft + plotWidth, y2: height - marginBottom,
            stroke: "#b5c2ba", "stroke-width": "1.2",
        });
        svg.append(xAxisLine);

        // Vẽ các cột ngang và nhãn
        const startY = marginTop;

        topProducts.forEach((item, index) => {
            const barY = startY + index * (barHeight + gap);
            const qty = item.qty || 0;
            const barWidth = xMax > 0 ? (qty / xMax) * plotWidth : 0;
            const rawName = item.name || `Sản phẩm ${index + 1}`;
            const prodCode = item.product_code || item.code;
            const prodUrl = prodCode ? `/products/quan-ly/chi-tiet/${encodeURIComponent(prodCode)}/` : null;

            // Link wrapper bao quanh tên và thanh để bấm vào ra chi tiết sản phẩm
            const itemRow = makeSvgElement("g", { class: "report-product-row" });

            // Nhãn tên sản phẩm nằm bên trái trục Y, không bị che khuất hay đè lên cột
            const labelGroup = makeSvgElement("g", { style: prodUrl ? "cursor: pointer;" : "cursor: default;" });
            const labelText = makeSvgElement("text", {
                x: marginLeft - 12,
                y: barY + 15,
                "text-anchor": "end",
                "font-size": "11.5",
                "font-weight": index === 0 ? "700" : "500",
                fill: index === 0 ? "#11382b" : "#2d3748",
            });
            labelText.textContent = rawName;

            const title = makeSvgElement("title");
            title.textContent = `${rawName}${item.spec && item.spec !== '-' ? ' (' + item.spec + ')' : ''}\n• Số lượng bán: ${qty.toLocaleString('vi-VN')}\n• Doanh thu: ${item.revenue_formatted || ''}${prodUrl ? '\n(Bấm để xem chi tiết sản phẩm)' : ''}`;
            labelGroup.append(labelText);
            labelGroup.append(title);
            itemRow.append(labelGroup);

            // Dải màu xanh lá đồng bộ với tông màu toàn trang
            const greenPalette = [
                { bar: "#173c32", hover: "#0f2620" }, // Top 1: Xanh đậm thương hiệu
                { bar: "#25614f", hover: "#1a4639" }, // Top 2: Xanh vừa
                { bar: "#3d7e6a", hover: "#2f6353" }, // Top 3
                { bar: "#5b9e8a", hover: "#4a8372" }, // Top 4
                { bar: "#7dbda9", hover: "#69a391" }, // Top 5
            ];
            const colorObj = greenPalette[index] || greenPalette[greenPalette.length - 1];
            const barColor = colorObj.bar;
            const hoverColor = colorObj.hover;

            const bar = makeSvgElement("rect", {
                x: marginLeft,
                y: barY,
                width: Math.max(barWidth, qty > 0 ? 3 : 0),
                height: barHeight,
                rx: "2",
                ry: "2",
                fill: barColor,
                style: `${prodUrl ? 'cursor: pointer;' : 'cursor: default;'} transition: fill 0.18s ease;`,
            });
            const barTitle = makeSvgElement("title");
            barTitle.textContent = `${rawName}${item.spec && item.spec !== '-' ? ' (' + item.spec + ')' : ''}\n• Số lượng bán: ${qty.toLocaleString('vi-VN')}\n• Doanh thu: ${item.revenue_formatted || ''}${prodUrl ? '\n(Bấm để xem chi tiết sản phẩm)' : ''}`;
            bar.append(barTitle);

            // Hover và Click điều hướng tới trang chi tiết sản phẩm
            if (prodUrl) {
                const navToProduct = () => { window.location.href = prodUrl; };
                labelGroup.addEventListener("click", navToProduct);
                bar.addEventListener("click", navToProduct);

                labelGroup.addEventListener("mouseenter", () => {
                    labelText.setAttribute("fill", "#0066cc");
                    bar.setAttribute("fill", hoverColor);
                });
                labelGroup.addEventListener("mouseleave", () => {
                    labelText.setAttribute("fill", index === 0 ? "#11382b" : "#2d3748");
                    bar.setAttribute("fill", barColor);
                });

                bar.addEventListener("mouseenter", () => {
                    bar.setAttribute("fill", hoverColor);
                    labelText.setAttribute("fill", "#0066cc");
                });
                bar.addEventListener("mouseleave", () => {
                    bar.setAttribute("fill", barColor);
                    labelText.setAttribute("fill", index === 0 ? "#11382b" : "#2d3748");
                });
            } else {
                bar.addEventListener("mouseenter", () => { bar.setAttribute("fill", hoverColor); });
                bar.addEventListener("mouseleave", () => { bar.setAttribute("fill", barColor); });
            }
            itemRow.append(bar);

            // Số lượng ở cuối thanh cột (full màu đen, không có viền stroke)
            const valText = makeSvgElement("text", {
                x: marginLeft + barWidth + 8,
                y: barY + 14,
                "text-anchor": "start",
                "font-size": "12.5",
                "font-weight": "700",
                fill: "#000",
                stroke: "none",
                style: "fill: #000 !important; stroke: none !important;",
            });
            valText.textContent = qty.toLocaleString("vi-VN");
            itemRow.append(valText);

            svg.append(itemRow);
        });

        chart.replaceChildren(svg);
    };

    const setupTopProductsToggle = () => {
        const btnChart = document.getElementById("btn-show-chart");
        const btnTable = document.getElementById("btn-show-table");
        const chartContainer = document.getElementById("top-products-chart-container");
        const tableContainer = document.getElementById("top-products-table-container");

        if (!btnChart || !btnTable || !chartContainer || !tableContainer) return;

        btnChart.addEventListener("click", () => {
            btnChart.style.background = "#173c32";
            btnChart.style.color = "#fff";
            btnTable.style.background = "#fff";
            btnTable.style.color = "#173c32";
            chartContainer.style.display = "block";
            tableContainer.style.display = "none";
        });

        btnTable.addEventListener("click", () => {
            btnTable.style.background = "#173c32";
            btnTable.style.color = "#fff";
            btnChart.style.background = "#fff";
            btnChart.style.color = "#173c32";
            tableContainer.style.display = "block";
            chartContainer.style.display = "none";
        });
    };

    const toggleCustomRange = form => {
        const preset = form.querySelector("[data-report-preset]");
        const range = form.querySelector("[data-report-range]");
        if (!preset || !range) return;
        const isCustom = preset.value === "custom";
        range.hidden = !isCustom;
        range.querySelectorAll("input").forEach(input => {
            input.required = isCustom;
        });
    };

    function setupReportPage(page = document.querySelector(".report-page")) {
        if (!page) return;
        page.querySelectorAll("[data-report-form]").forEach(form => {
            toggleCustomRange(form);
            form.addEventListener("change", event => {
                if (event.target.matches("[data-report-preset]")) toggleCustomRange(form);
            });
        });
        page.querySelectorAll("[data-order-sort]").forEach(button => {
            button.addEventListener("click", () => {
                const form = page.querySelector("[data-report-form]");
                if (!form) return;
                const field = form.elements.namedItem("order_sort");
                const direction = form.elements.namedItem("order_sort_dir");
                if (!field || !direction) return;
                direction.value = field.value === button.dataset.orderSort && direction.value === "asc" ? "desc" : "asc";
                field.value = button.dataset.orderSort;
                form.requestSubmit();
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        setupReportPage();
        renderRevenueChart();
        renderTopProductsChart();
        setupTopProductsToggle();

        // Tự động vẽ lại biểu đồ khi thay đổi kích thước cửa sổ (responsive)
        let resizeTimer = null;
        window.addEventListener("resize", () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                renderRevenueChart();
                renderTopProductsChart();
            }, 150);
        });
    });
})();