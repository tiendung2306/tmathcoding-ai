# Local development (used by docker-compose.yml): Vite dev server with hot reload.
FROM node:20-alpine AS dev
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

FROM dev AS build
RUN npm run build

# Production: static files behind nginx with SPA fallback and an /api proxy.
#   docker build --target prod -t tmath-frontend ./frontend
#   docker run -e BACKEND_URL=http://backend:8000 -p 8080:80 tmath-frontend
FROM nginx:1.27-alpine AS prod
ENV BACKEND_URL=http://backend:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
