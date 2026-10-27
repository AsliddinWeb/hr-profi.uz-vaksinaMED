# Build context = repo root (mijoz extension kodi ham kerak: clients/<CLIENT_NAME>)
FROM node:24-alpine AS dev
ARG CLIENT_NAME=example
ENV CLIENT_NAME=${CLIENT_NAME}
WORKDIR /app/core/frontend
COPY core/frontend/package.json core/frontend/package-lock.json ./
RUN npm ci
COPY core/frontend ./
COPY clients/${CLIENT_NAME} /app/clients/${CLIENT_NAME}
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM dev AS build
RUN npm run build

FROM nginx:1.27-alpine AS prod
COPY deploy/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/core/frontend/dist /usr/share/nginx/html
