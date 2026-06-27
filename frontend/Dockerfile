# Frontend image (multi-stage). Build from the repo root:
#   nerdctl --namespace k8s.io build -t quetzel/frontend:dev -f frontend/Dockerfile .
FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
