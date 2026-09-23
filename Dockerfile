# Digi Gharz: one container serving the site, the app and the API.
#
# Build args:
#   SITE_URL      public address, baked into canonical links and the sitemap
#   NODE_IMAGE    base image; point it at a registry mirror if Docker Hub is
#                 unreachable from the build server
#   NPM_REGISTRY  npm registry; point it at a mirror if npmjs is unreachable
ARG NODE_IMAGE=node:22-alpine

FROM ${NODE_IMAGE} AS build
ARG NPM_REGISTRY=https://registry.npmjs.org/
ARG SITE_URL=https://example.com
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm config set registry "$NPM_REGISTRY" && npm ci
COPY . .
RUN SITE_URL="$SITE_URL" npm run build && npm prune --omit=dev \
    && date -u +%Y-%m-%dT%H:%M:%SZ > BUILT_AT

FROM ${NODE_IMAGE}
# node:sqlite is stable enough for us; hide its "experimental" start-up warning.
ENV NODE_ENV=production \
    NODE_OPTIONS=--disable-warning=ExperimentalWarning \
    PORT=3000 \
    DB_PATH=/app/data/digi-gharz.db
WORKDIR /app
COPY --from=build /app/package.json /app/BUILT_AT ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/server ./server
# The server shares these modules with the browser (dates, draws, plans).
COPY --from=build /app/src/lib ./src/lib
# Runs as root: PaaS disks are usually mounted root-owned, and SQLite must
# be able to write to them.
RUN mkdir -p /app/data
EXPOSE 3000
# SQLite lives in /app/data: mount the platform's persistent disk there.
# (No VOLUME line: it would create an anonymous volume some platforms keep
# in place of, or alongside, the disk they mount.)
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1
CMD ["node", "server/index.js"]
