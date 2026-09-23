FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Sem compilador nem libpq: psycopg2-binary e as demais deps têm wheel.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic no build: valores fake só para o settings carregar (sem banco).
RUN SECRET_KEY=build-only ALLOWED_HOSTS=localhost DEBUG=False \
    python manage.py collectstatic --noinput

# uid 1000 = dono dos arquivos na máquina de dev. protected_media existe na
# imagem só para o volume nomeado nascer com dono app (senão nasce root).
RUN useradd --uid 1000 --create-home app \
    && mkdir -p /app/protected_media && chown app /app/protected_media
USER app

EXPOSE 8000

# Padrão = serviço web: migrate e gunicorn. worker/beat sobrescrevem o command
# no compose, então a migration roda só aqui.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-2} --timeout 120"]
