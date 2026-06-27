# Backend API image. Build from the repo root:
#   nerdctl --namespace k8s.io build -t quetzel/backend:dev -f backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

# In-cluster the real provider is selected; mock remains available for demos.
ENV QUETZEL_PROVIDER=k8s

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
