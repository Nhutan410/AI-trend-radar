# TÀI LIỆU HƯỚNG DẪN VÀ THIẾT KẾ HỆ THỐNG: PNJ AI TREND RADAR V2

## 1. Tổng quan Hệ thống (System Overview)
**PNJ AI Trend Radar V2** là một ứng dụng phân tích phản hồi khách hàng thông minh, sử dụng mô hình ngôn ngữ lớn (LLM - cụ thể là Qwen2.5:7B qua Ollama) để tự động trích xuất cảm xúc theo từng khía cạnh (Aspect-Based Sentiment Analysis - ABSA), phân tích xu hướng (Trend Detection) và tạo ra các báo cáo khuyến nghị chiến lược (LLM Synthesis). 

Ứng dụng được xây dựng trên framework **Streamlit** với kiến trúc module hoá, hỗ trợ người dùng theo dõi dữ liệu sức khoẻ thương hiệu qua giao diện Dashboard trực quan.

---

## 2. Kiến trúc & Luồng dữ liệu (Architecture & Data Flow)

Dữ liệu di chuyển qua các bước sau:
1. **Dữ liệu thô (Raw Data):** Từ file `PNJ_Feedback.xlsx` chứa danh sách phản hồi của khách hàng.
2. **Ingestion (Nạp liệu):** So sánh `PNJ_Feedback.xlsx` và `PNJ_ABSA_Result.json` để tìm ra các phản hồi mới chưa được xử lý.
3. **ABSA Pipeline:** Gọi model LLM nội bộ (Ollama) để đọc từng phản hồi thô và trích xuất ra cấu trúc JSON (Category, Term, Opinion, Sentiment, Trending).
4. **Data Store:** Lưu kết quả trích xuất vào `PNJ_ABSA_Result.json`.
5. **Trend Engine:** Động cơ xử lý toán học và thống kê, biến dữ liệu ABSA flat thành các metrics (NPS, Weak Signals, Z-Score, Top Complaints).
6. **LLM Synthesis:** LLM đọc báo cáo số liệu từ Trend Engine và viết ra văn bản tổng hợp, khuyến nghị chiến lược bằng ngôn ngữ tự nhiên.
7. **UI / Dashboard:** Render dữ liệu qua Streamlit (Tổng quan, Biểu đồ Cảm xúc, Xu hướng, Khuyến nghị).

---

## 3. Các Module Cốt Lõi (Core Modules)

### 3.1. Nạp và Xử lý dữ liệu (`core/ingestion.py`)
- **Nhiệm vụ:** Đọc file Excel và file JSON cache.
- **Cơ chế:** Dùng `Feedback ID` làm khoá chính để lọc ra (detect) những feedback nào có trong file Excel nhưng chưa có trong JSON.
- **Flatten Data:** Có chức năng `get_json_as_dataframe` để "trải phẳng" (explode) dữ liệu JSON. Nếu 1 feedback có 3 khía cạnh (aspects) được nhắc tới, nó sẽ được tách thành 3 dòng trong DataFrame để Trend Engine dễ phân tích.

### 3.2. Đường ống trích xuất ABSA (`core/absa_pipeline.py`)
- **Nhiệm vụ:** Biến văn bản thô của khách hàng thành dữ liệu có cấu trúc.
- **Mô hình sử dụng:** `qwen2.5:7b` chạy local qua cổng `http://localhost:11434`.
- **Cấu trúc trích xuất (Schema):**
  - `category`: Thuộc 1 trong 5 nhóm: *"Sản phẩm", "Dịch vụ nhân viên", "Giá cả", "Cửa hàng", "Giao hàng/Online"*.
  - `term`: Thực thể cụ thể (VD: "nhân viên Mai", "nhẫn kim cương").
  - `opinion`: Trích dẫn hoặc nhận định cụ thể.
  - `sentiment`: `"positive"`, `"negative"`, `"neutral"`.
  - `trending`: Chuỗi text nếu feedback có đề cập đến xu hướng thị trường hoặc hành vi mới, nếu không thì để trống.

### 3.3. Động cơ Phân tích Xu hướng (`core/trend_engine.py`)
Đây là bộ não toán học của hệ thống. Nhận DataFrame đã được trải phẳng và trả về `TrendEngineOutput` chứa toàn bộ insight.

**Các chức năng chính:**
- Thống kê tổng quan (Summary Statistics).
- Phân tích chuỗi thời gian của cảm xúc (Time-series sentiment).
- Dò tìm Tín hiệu yếu (Weak Signal Detection) - Phát hiện các mầm mống rủi ro hoặc xu hướng trước khi bùng phát.
- Phân loại khiếu nại hàng đầu (Top Complaints).
- So sánh hiệu suất cửa hàng, kênh và nguồn dữ liệu (Cross-store / Channel Analysis).

### 3.4. Tổng hợp báo cáo LLM (`core/llm_synthesis.py`)
- **Nhiệm vụ:** Đọc Output của `Trend Engine` và bắt LLM đóng vai "Chuyên gia phân tích CX" (CX Analyst) để viết báo cáo.
- **Nội dung tạo ra:** 
  1. Phân tích vấn đề cốt lõi.
  2. Xu hướng cần theo dõi.
  3. Khuyến nghị hành động (SMART).
  4. Rủi ro nếu không hành động.
- **Quick Summary:** Ngoài ra còn cung cấp hàm tóm tắt siêu ngắn (3 câu) để hiển thị trên top màn hình Dashboard.

---

## 4. Giao diện Người Dùng (UI / Dashboard)

Ứng dụng chia làm 4 Tab chính trong `app.py`:
1. **🏠 Tổng quan (Overview):** Chứa các thẻ chỉ số (Metrics), tóm tắt nhanh từ LLM, và biểu đồ Radar (hiệu suất tổng thể).
2. **📊 Phân tích Cảm xúc (Sentiment Analysis):** Trình bày chi tiết tỷ lệ tiêu cực/tích cực theo từng hạng mục, biểu đồ nhiệt theo thời gian (Weekly Heatmap) và chi tiết các bình luận.
3. **📡 Xu hướng & Tín hiệu (Trend Detection):** Tập trung vào kết quả của **Weak Signals** (Tín hiệu yếu cảnh báo rủi ro) và các mảng Text về trending thị trường.
4. **💡 Khuyến nghị (Recommendations):** Nơi hiển thị báo cáo chi tiết 4 phần do LLM CX Analyst biên soạn dựa trên số liệu thực tế.

---

## 5. Thuật ngữ (Terminologies)

| Thuật ngữ | Giải thích |
| :--- | :--- |
| **ABSA (Aspect-Based Sentiment Analysis)** | Phân tích cảm xúc dựa trên khía cạnh. Thay vì đánh giá chung 1 câu là tốt/xấu, ABSA bóc tách xem khách khen "giá cả" nhưng chê "dịch vụ". |
| **Weak Signal (Tín hiệu yếu)** | Những dấu hiệu, phản hồi tiêu cực hoặc xu hướng mới xuất hiện ở quy mô nhỏ, chưa thành khủng hoảng nhưng có tốc độ gia tăng bất thường hoặc xuất hiện đồng thời ở nhiều nơi. |
| **NPS Proxy** | Chỉ số NPS (Net Promoter Score) mô phỏng. NPS thực tế yêu cầu khách hàng đánh giá điểm 0-10. Ở đây dùng công thức quy đổi từ số lượng bình luận tích cực/tiêu cực để làm tham chiếu. |
| **Sentiment Velocity** | Vận tốc cảm xúc. Sự biến thiên (tăng/giảm) của điểm số cảm xúc qua từng ngày (đạo hàm bậc 1 của chuỗi thời gian cảm xúc). |
| **Z-Score (Điểm tiêu chuẩn)** | Thống kê đo lường mức độ sai lệch của một dữ liệu so với mức trung bình của tập dữ liệu đó. Dùng để xác định sự "tăng đột biến" một cách có cơ sở toán học. |

---

## 6. Các Công thức Toán học và Logic Tính toán (Formulas)

Toàn bộ công thức nằm trong `core/trend_engine.py`:

### 6.1. NPS Proxy Score
Được tính dựa trên tổng số cảm xúc (bỏ qua feedback bị rỗng khía cạnh).
$$NPS\_Proxy = \frac{\text{Positive Count} - \text{Negative Count}}{\text{Total Sentiments}} \times 100$$

### 6.2. Sentiment Timeseries & Velocity (Chuỗi thời gian & Vận tốc)
- **Tỷ lệ tích cực/tiêu cực hàng ngày:**
  $$Pos\_Ratio_t = \frac{Pos_t}{Total_t}$$
  $$Neg\_Ratio_t = \frac{Neg_t}{Total_t}$$
- **Điểm Net Score (Điểm ròng hàng ngày):** 
  $$Net\_Score_t = Pos\_Ratio_t - Neg\_Ratio_t$$
- **Rolling Sentiment (Trung bình động 7 ngày):** Làm mượt chuỗi dữ liệu để triệt tiêu nhiễu theo ngày.
  $$Rolling\_Score_t = \frac{1}{7} \sum_{i=t-6}^{t} Net\_Score_i$$
- **Sentiment Velocity (Vận tốc cảm xúc):** Là sự chênh lệch (đạo hàm) của đường Rolling Sentiment để xem xu hướng đang cắm đầu xuống hay ngóc đầu lên.
  $$Velocity_t = Rolling\_Score_t - Rolling\_Score_{t-1}$$

### 6.3. Weak Signal Detection (Công thức Phát hiện Tín hiệu Yếu)
Động cơ so sánh **Cửa sổ hiện tại (14 ngày gần nhất)** so với **Đường cơ sở / Baseline (60 ngày trước đó)**.

- **Kỳ phân tích:**
  - `recent_window`: $t_{max} - 14$ ngày đến $t_{max}$
  - `baseline_window`: $t_{max} - 74$ ngày đến $t_{max} - 15$ ngày

- **Tỷ lệ tiêu cực trung bình:**
  - $p_0$ (`baseline_neg_rate`): Tỷ lệ tiêu cực trong giai đoạn baseline.
  - $p$ (`recent_neg_rate`): Tỷ lệ tiêu cực trong 14 ngày gần nhất.
  - $n$: Số lượng mẫu trong 14 ngày gần nhất.

- **Standard Error (Sai số chuẩn):**
  $$SE = \sqrt{\frac{p_0 \times (1 - p_0)}{\max(n, 1)}}$$

- **Hệ số Z-Score:**
  $$Z = \frac{p - p_0}{\max(SE, 10^{-6})}$$

- **Logic cảnh báo:**
  Nếu $Z > 1.5$ hoặc ($p > 0.5$ và $n \ge 5$) thì ghi nhận đây là **Tín hiệu yếu / Đột biến tiêu cực**.
  - **High Severity (🔴):** Nếu $Z > 2.5$
  - **Medium Severity (🟡):** Nếu $1.5 < Z \le 2.5$
  - **Low Severity (🟢):** Nếu chỉ thoả mãn $p > 0.5$ và mẫu $\ge 5$.
  - **Điểm rủi ro (Score 0-1):** $\min(1.0, \max(0.0, Z / 4.0))$

### 6.4. Cross-store Recurring Issues (Vấn đề hệ thống chuỗi)
Ngoài phân tích theo thời gian, hệ thống dò tìm các lời chê (opinion) giống hệt nhau (hoặc cùng chung phân loại) xuất hiện ở **bao nhiêu cửa hàng khác nhau** trong 14 ngày.
- Nếu $Store\_Count \ge 3$, xem như lỗi hệ thống (Systemic Issue).
- **High Severity:** Nếu $Store\_Count \ge 5$.
- **Điểm rủi ro:** $\min(1.0, Store\_Count / 10)$.
