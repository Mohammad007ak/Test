FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# در زمان build هیچ متغیر محیطی‌ای از .env در دسترس نیست، پس DEBUG را همینجا
# صراحتاً False می‌کنیم تا collectstatic هم مثل زمان اجرای واقعی از
# ManifestStaticFilesStorage استفاده کند و فایل manifest درست تولید شود؛
# در زمان اجرا مقدار واقعی DEBUG از .env این مقدار را override می‌کند.
ENV DEBUG=False
RUN python manage.py collectstatic --noinput

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "security_projects.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
