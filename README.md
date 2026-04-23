# 💎 PNJ AI Trend Radar V2

Ứng dụng phân tích feedback khách hàng toàn diện cho PNJ, kết hợp **Aspect-Based Sentiment Analysis (ABSA)**, **Trend Detection Engine**, và **AI-powered Insights** hiển thị qua dashboard Streamlit hiện đại.

> **Dữ liệu mẫu đã có sẵn** – `PNJ_ABSA_Result.json` được commit cùng repo, bạn có thể xem dashboard ngay mà **không cần chạy ABSA**.  
> Chỉ cần Ollama nếu muốn xử lý feedback mới từ `PNJ_Feedback.xlsx`.

---

## 📋 Mục lục

- [Tính năng](#-tính-năng)
- [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
- [Cài đặt & Chạy – Windows](#-cài-đặt--chạy--windows)
- [Cài đặt & Chạy – macOS / Linux](#-cài-đặt--chạy--macos--linux)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
- [Troubleshooting](#-troubleshooting)
- [Schema dữ liệu](#-schema-dữ-liệu)

---

## ✨ Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| **🔄 Cập nhật dữ liệu** | Phát hiện feedback mới trong `PNJ_Feedback.xlsx`, chạy ABSA tự động |
| **🤖 ABSA via Qwen2.5:7b** | Trích xuất aspect, opinion, sentiment từ text tiếng Việt |
| **📡 Trend Detection Engine** | Time-series analysis, Z-score weak signal, cross-store analysis |
| **💡 AI Synthesis** | Qwen tổng hợp insights chiến lược & đề xuất hành động SMART |
| **📊 Dashboard 4 tabs** | Tổng quan · Sentiment · Xu hướng · Khuyến nghị |
| **🔍 Bộ lọc linh hoạt** | Lọc theo ngày, cửa hàng, kênh, nguồn |
| **📥 Export báo cáo** | Tải báo cáo AI dạng Markdown |

---

## 💻 Yêu cầu hệ thống

| Thành phần | Phiên bản |
|------------|-----------|
| Python | ≥ 3.9 |
| Ollama *(chỉ cần nếu xử lý feedback mới)* | Mới nhất |
| Qwen2.5:7b *(chỉ cần nếu xử lý feedback mới)* | via Ollama |

**Phần cứng khuyến nghị:**

| | Tối thiểu | Khuyến nghị |
|--|-----------|-------------|
| RAM | 8 GB | 16 GB |
| GPU VRAM | 0 GB (CPU mode) | 8 GB |
| Ổ cứng trống | 5 GB | 10 GB |

---

## 🪟 Cài đặt & Chạy – Windows

> Thực hiện tất cả lệnh trong **Command Prompt (cmd)** hoặc **PowerShell**.  
> **KHÔNG dùng Git Bash** (có thể gặp lỗi encoding tiếng Việt).

### Bước 1 – Cài Python

1. Tải Python tại: https://www.python.org/downloads/
2. Khi cài đặt, **tích vào "Add Python to PATH"** (quan trọng!)
3. Kiểm tra:

```cmd
python --version
```

Kết quả mong đợi: `Python 3.x.x`

---

### Bước 2 – Clone repository

```cmd
git clone https://github.com/<your-username>/AI_Trend_Radar_V2.git
cd AI_Trend_Radar_V2
```

> Nếu chưa có Git: https://git-scm.com/download/win

---

### Bước 3 – Tạo Virtual Environment

```cmd
python -m venv .venv
```

---

### Bước 4 – Kích hoạt Virtual Environment

**Command Prompt (cmd):**
```cmd
.venv\Scripts\activate.bat
```

**PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

> ⚠️ Nếu PowerShell báo lỗi "cannot be loaded because running scripts is disabled":
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

Sau khi kích hoạt, bạn sẽ thấy `(.venv)` ở đầu dòng lệnh.

---

### Bước 5 – Cài dependencies

```cmd
pip install -r requirements.txt
```

---

### Bước 6 – Chạy ứng dụng

```cmd
streamlit run app.py
```

Ứng dụng mở tại: **http://localhost:8501**

---

### 🚀 Script khởi động nhanh (Windows)

Tạo file `start.bat` trong thư mục project với nội dung:

```bat
@echo off
call .venv\Scripts\activate.bat
streamlit run app.py
pause
```

Sau đó chỉ cần **double-click** `start.bat` để khởi động.

---

### Bước 7 (tuỳ chọn) – Cài Ollama để xử lý feedback mới

> Bỏ qua bước này nếu bạn chỉ muốn xem dữ liệu đã có sẵn.

1. Tải Ollama cho Windows: https://ollama.com/download/windows
2. Cài đặt và khởi động Ollama
3. Mở **Command Prompt mới** (để Ollama chạy song song):

```cmd
ollama serve
```

4. Mở **Command Prompt khác** và pull model:

```cmd
ollama pull qwen2.5:7b
```

> Model ~4.7 GB, cần kết nối internet để download lần đầu.

---

## 🍎 Cài đặt & Chạy – macOS / Linux

```bash
# 1. Clone repo
git clone https://github.com/<your-username>/AI_Trend_Radar_V2.git
cd AI_Trend_Radar_V2

# 2. Tạo và kích hoạt venv
python3 -m venv .venv
source .venv/bin/activate

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Chạy app
streamlit run app.py
```

**Cài Ollama (macOS/Linux) – tuỳ chọn:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama serve   # chạy trong terminal riêng
```

---

## 📁 Cấu trúc thư mục

```
AI_Trend_Radar_V2/
│
├── app.py                      # 🚀 Entry point – Streamlit app chính
├── requirements.txt            # Python dependencies
├── README.md                   # Tài liệu này
├── .gitignore
│
├── PNJ_Feedback.xlsx           # 📊 Nguồn dữ liệu feedback (input)
├── PNJ_ABSA_Result.json        # 💾 Kết quả ABSA (dữ liệu mẫu, auto-updated)
│
├── core/                       # Backend logic
│   ├── __init__.py
│   ├── ingestion.py            # Load xlsx/json, detect new rows, atomic save
│   ├── absa_pipeline.py        # ABSA extraction via Qwen2.5:7b + Ollama
│   ├── trend_engine.py         # Trend Detection Engine (time-series, Z-score)
│   └── llm_synthesis.py        # LLM-powered synthesis & recommendations
│
└── ui/                         # Frontend Streamlit components
    ├── __init__.py
    ├── overview.py             # Tab 1: Tổng quan
    ├── sentiment_analysis.py   # Tab 2: Phân tích cảm xúc
    ├── trend_detection.py      # Tab 3: Xu hướng & tín hiệu
    └── recommendations.py      # Tab 4: Khuyến nghị
```

---

## 📖 Hướng dẫn sử dụng

### Xem dữ liệu hiện có (không cần Ollama)

Chỉ cần chạy app là dashboard hiển thị ngay với dữ liệu từ `PNJ_ABSA_Result.json`.

### Thêm feedback mới & cập nhật phân tích

```
1. Thêm feedback mới vào PNJ_Feedback.xlsx
        ↓
2. Mở app → Sidebar → Kiểm tra trạng thái Ollama
        ↓
3. Click "⚡ Xử lý N feedback mới"
        ↓
4. App tự động: phát hiện ID mới → gọi Qwen2.5:7b → cập nhật JSON
        ↓
5. Dashboard tự refresh → xem charts và insights
        ↓
6. Tab "💡 Khuyến nghị" → Click "🤖 Tạo Báo Cáo AI"
```

### Các tab dashboard

| Tab | Nội dung |
|-----|----------|
| 🏠 **Tổng quan** | KPI cards, sentiment donut, category bar, heatmap, top stores |
| 📊 **Phân tích Cảm xúc** | Time-series 7 ngày, so sánh kênh, phân bổ nguồn, drilldown |
| 📡 **Xu hướng & Tín hiệu** | Weak signal alerts (🔴🟡🟢), velocity chart, top complaints |
| 💡 **Khuyến nghị** | Priority matrix, AI report generation, export Markdown |

---

## 🐛 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| `python` không nhận ra | Cài lại Python, tích "Add to PATH" |
| `.venv\Scripts\Activate.ps1` bị chặn | Chạy: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `ModuleNotFoundError` | Đảm bảo venv đã active (thấy `(.venv)`), chạy lại `pip install -r requirements.txt` |
| `❌ Không kết nối Ollama` | Mở cmd mới, chạy `ollama serve` |
| `⚠️ Model chưa được pull` | Chạy `ollama pull qwen2.5:7b` |
| Charts không hiển thị | `pip install --upgrade plotly streamlit` |
| JSON bị corrupt | Xóa các file `.tmp_absa_*.json` trong thư mục project |
| ABSA chậm | Bình thường: ~5-15s/feedback (CPU), ~2-5s (GPU) |
| Lỗi encoding tiếng Việt (Windows) | Dùng cmd hoặc PowerShell, **không dùng Git Bash** |

---

## 📊 Schema dữ liệu

### `PNJ_Feedback.xlsx` (input)

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `Feedback ID` | string | Unique ID (VD: `PNJ-00001`) |
| `Ngày` | string | DD/MM/YYYY |
| `Giờ` | string | HH:MM |
| `Nguồn` | string | Shopee, Facebook, App PNJ, v.v. |
| `Kênh` | string | Online / Offline |
| `Cửa hàng` | string | Tên chi nhánh PNJ |
| `Nội dung feedback` | string | Text feedback gốc |

### `PNJ_ABSA_Result.json` (output)

```json
[
  {
    "Feedback ID": "PNJ-00001",
    "Ngày": "01/01/2026",
    "Giờ": "08:16",
    "Nguồn": "Khảo sát tại quầy",
    "Kênh": "Offline",
    "Cửa hàng": "PNJ Vũng Tàu",
    "Nội dung feedback": "Nhân viên rất tận tình...",
    "aspects": [
      {
        "category": "Dịch vụ nhân viên",
        "term": "nhân viên Quỳnh",
        "opinion": "nhiệt tình và am hiểu sản phẩm",
        "sentiment": "positive"
      }
    ],
    "trending": "Trend pearl drop đang hot mùa này"
  }
]
```

**Các giá trị hợp lệ:**

| Field | Giá trị |
|-------|---------|
| `category` | `Sản phẩm` \| `Dịch vụ nhân viên` \| `Giá cả` \| `Cửa hàng` \| `Giao hàng/Online` |
| `sentiment` | `positive` \| `negative` \| `neutral` |
| `trending` | String mô tả xu hướng, hoặc `""` nếu không có |

---

## 🔐 Bảo mật

- Mọi xử lý đều **local** – dữ liệu không gửi ra ngoài internet
- Qwen2.5:7b chạy 100% trên máy của bạn qua Ollama
- `PNJ_ABSA_Result.json` được ghi **atomically** để tránh mất dữ liệu

---

*Built with ❤️ for PNJ · Powered by Qwen2.5:7b & Streamlit*
