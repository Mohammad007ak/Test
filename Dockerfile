# اجرای برنامه روی سرور (مثلاً کوبرنتیز هم‌روش)؛ دیتابیس در /app/data که باید دیسک ماندگار باشد
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FINASSIST_DATABASE_URL=sqlite:////app/data/finassist.db \
    FINASSIST_SECURE_COOKIES=true

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations migrations
COPY app app

RUN useradd --uid 1000 --create-home finassist && mkdir -p /app/data \
    && chown finassist /app/data
USER finassist
VOLUME /app/data
EXPOSE 8000

# فقط یک نسخه (replica) اجرا شود: SQLite و زمان‌بند قیمت داخل همین پردازه‌اند
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
