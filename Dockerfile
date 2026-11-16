FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN useradd --system --uid 10001 --home /app appli
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN DJANGO_SECRET_KEY=construction python manage.py collectstatic --noinput -v0 \
 && chmod +x docker/entrypoint.sh && chown -R appli /app

USER appli
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/sante/',timeout=4)"
ENTRYPOINT ["/app/docker/entrypoint.sh"]
