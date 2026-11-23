FROM python:3.14-slim

WORKDIR /app

# Instalar uv (gestor de dependencias)
RUN pip install --no-cache-dir uv

# Cachear dependencias antes de copiar el código
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Código de la aplicación (datos/ llega como volumen)
COPY app.py bitacora.py ./
COPY static/   static/
COPY templates/ templates/
COPY publico/  publico/

EXPOSE 8000
CMD ["uv", "run", "waitress-serve", "--host", "0.0.0.0", "--port", "8000", "app:app"]