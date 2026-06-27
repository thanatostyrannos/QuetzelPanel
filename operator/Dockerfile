# Operator (kopf) image. Build from the repo root:
#   nerdctl --namespace k8s.io build -t quetzel/operator:dev -f operator/Dockerfile .
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY operator/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY operator/quetzel_operator ./quetzel_operator
# Bundle a catalog fallback; the chart also mounts it as a ConfigMap (authoritative).
COPY deploy/catalog.json /etc/quetzel/catalog.json
ENV CATALOG_PATH=/etc/quetzel/catalog.json
# kopf's console-script entrypoint does not add the working dir to sys.path.
ENV PYTHONPATH=/app

# Namespace is supplied by the chart's command (kopf run --namespace ...).
CMD ["kopf", "run", "--standalone", "--all-namespaces", "-m", "quetzel_operator.handlers"]
