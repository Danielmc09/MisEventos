FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npx vite build

FROM nginxinc/nginx-unprivileged:stable-alpine AS runtime
ARG VITE_API_URL=http://localhost:8000
# Lo usa la plantilla de nginx para la CSP (connect-src).
ENV VITE_API_URL=$VITE_API_URL
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
