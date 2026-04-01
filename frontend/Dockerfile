FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Production server ──
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# React Router support — all routes serve index.html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
