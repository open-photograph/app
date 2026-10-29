# syntax=docker/dockerfile:1
ARG NODE_VERSION=22
FROM node:${NODE_VERSION}-bookworm-slim AS build
ARG PNPM_VERSION=12.11.2
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@${PNPM_VERSION} --activate
COPY apps/app/package.json apps/app/pnpm-lock.yaml ./
RUN --mount=type=cache,id=open-photograph-pnpm,target=/pnpm/store pnpm install --frozen-lockfile --store-dir=/pnpm/store
COPY apps/app/ ./
RUN pnpm build

FROM nginx:stable-alpine AS runtime
COPY apps/app/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
