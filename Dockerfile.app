FROM python:3.12-alpine

WORKDIR /app

# Instala dependências
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copia a aplicação completa (Flask + Frontend)
COPY . ./

# Diretório para o volume do banco SQLite
RUN mkdir -p /data

ENV PORT=5002 \
    DB_PATH=/data/lances.db \
    ADMIN_PASSWORD=admin123 \
    INITIAL_BID=300

EXPOSE 5002

# Executa com Gunicorn em produção para performance e estabilidade
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "app:app"]
