# Frontend image (CLAUDE.md §6.18/§6.19).
# Dependencies install + build happen at BUILD time only. The runtime image is
# nginx serving static assets and proxying /api to the backend — zero egress.

# ── Build stage ─────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
# Use a lockfile-respecting install when present; fall back otherwise.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# ── Runtime stage ───────────────────────────────────
FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1
