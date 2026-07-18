# Two-stage web image: build the React SPA, then serve it with Caddy (which also
# reverse-proxies the API, so the whole app is same-origin — no CORS in prod).

# --- Stage 1: build the SPA ------------------------------------------------
FROM node:20-alpine AS build
WORKDIR /app

# The API base URL is baked in at BUILD time. In production it must be the
# public site URL (same origin as this web server), e.g. https://yourdomain.com
# — Caddy proxies /v1 and /static from there to the API container.
ARG VITE_API_URL=https://yourdomain.com
ENV VITE_API_URL=${VITE_API_URL}

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build            # → /app/dist

# --- Stage 2: serve with Caddy (auto-HTTPS) --------------------------------
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
EXPOSE 80 443
