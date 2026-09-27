FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install --with-deps chromium
COPY . .
ENV PORT=10000
CMD gunicorn --bind 0.0.0.0:$PORT app:app
