# Frontend: build estatico con Vite y servido por nginx (que ademas hace proxy de /api)
FROM node:22-alpine AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ .
RUN npm run build

FROM nginx:1.27-alpine
# plantilla: la imagen oficial sustituye ${SATO_PROXY_CONFIABLE} al iniciar (las variables propias de nginx no se tocan)
COPY docker/nginx.conf /etc/nginx/templates/default.conf.template
ENV SATO_PROXY_CONFIABLE=127.0.0.1
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
