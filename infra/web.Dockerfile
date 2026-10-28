FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY web/package*.json ./
RUN npm ci
COPY web/ .
RUN npm run build
FROM nginx:1.28-alpine
ARG VCS_REF=development
LABEL io.viacrm.project=viacrm org.opencontainers.image.revision=$VCS_REF
COPY infra/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf '{"commit":"%s"}\n' "$VCS_REF" > /usr/share/nginx/html/release.json
EXPOSE 80
