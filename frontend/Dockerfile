# Build the static web app, then serve it with nginx (which also proxies /api).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_TILE_URL
ARG VITE_TILE_MAX_ZOOM
ARG VITE_TILE_ATTRIBUTION
ENV VITE_TILE_URL=$VITE_TILE_URL VITE_TILE_MAX_ZOOM=$VITE_TILE_MAX_ZOOM VITE_TILE_ATTRIBUTION=$VITE_TILE_ATTRIBUTION
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
