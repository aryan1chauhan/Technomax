# Build runs locally: npm run build → dist/
# Docker only serves the pre-built static assets via nginx.
# This bypasses Docker's npm network issues (slow in WSL2/Windows) entirely.
FROM nginx:alpine

COPY dist/ /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
