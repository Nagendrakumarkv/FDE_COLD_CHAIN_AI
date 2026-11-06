FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first for better build caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501"]