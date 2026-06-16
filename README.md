# PNJ AI Trend Radar V2

Ứng dụng Streamlit để phân tích feedback khách hàng PNJ, hiển thị sentiment, xu hướng, tín hiệu yếu và báo cáo khuyến nghị từ AI.

## Tính năng chính

- Dashboard 4 tab: Tổng quan, Phân tích cảm xúc, Xu hướng & Tín hiệu, Khuyến nghị.
- Đọc dữ liệu từ `PNJ_ABSA_Result.json` và `PNJ_Feedback.xlsx`.
- Phát hiện feedback mới và chạy ABSA bằng OpenAI khi có `OPENAI_API_KEY`.
- Đăng nhập đơn giản bằng username/password trong `.env`.
- Chạy được bằng Docker Compose, Docker CLI hoặc Python local.

## Yêu cầu

- Docker Desktop nếu chạy bằng Docker.
- Python 3.10+ nếu chạy local.
- `OPENAI_API_KEY` nếu muốn xử lý feedback mới hoặc tạo báo cáo AI.

## Cấu hình `.env`

Tạo file `.env` từ mẫu:

```bash
cp .env.example .env
```

Cập nhật các biến sau trong `.env`:

```env
AUTH_USERNAME=your_username
AUTH_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
```

Không commit `.env`. File này chứa thông tin đăng nhập và API key thật.

## Chạy bằng Docker Compose

```bash
docker compose up --build
```

Mở app tại:

```text
http://localhost:8501
```

Nếu port `8501` bị chiếm, sửa trong `docker-compose.yml`:

```yaml
ports:
  - "8502:8501"
```

Sau đó mở `http://localhost:8502`.

## Chạy bằng Docker CLI

Build image:

```bash
docker build -t ai-trend-radar:latest .
```

Chạy container:

```bash
docker run --rm --env-file .env --name ai-trend-radar -p 8501:8501 ai-trend-radar:latest
```

Nếu port `8501` bị chiếm:

```bash
docker run --rm --env-file .env --name ai-trend-radar -p 8502:8501 ai-trend-radar:latest
```

## Chạy local bằng Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Trên Windows:

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
streamlit run app.py
```

## Lỗi thường gặp

| Lỗi | Cách xử lý |
| --- | --- |
| Không đăng nhập được | Kiểm tra `AUTH_USERNAME` và `AUTH_PASSWORD` trong `.env`, rồi restart app. |
| App báo thiếu OpenAI | Thêm `OPENAI_API_KEY` vào `.env`. Dashboard vẫn xem được dữ liệu có sẵn, nhưng AI/ABSA sẽ bị tắt. |
| Port `8501` bị chiếm | Dùng mapping `8502:8501` khi chạy Docker hoặc sửa `docker-compose.yml`. |
| `ModuleNotFoundError` khi chạy local | Kích hoạt venv và chạy lại `pip install -r requirements.txt`. |
| Docker không đọc được biến môi trường | Đảm bảo file `.env` nằm cùng thư mục với `docker-compose.yml` hoặc truyền `--env-file .env`. |
