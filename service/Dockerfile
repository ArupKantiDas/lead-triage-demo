FROM node:22-alpine

WORKDIR /app

# No native modules — pure JS deps only. No build tools needed.
COPY package.json package-lock.json* ./
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

COPY tsconfig.json ./
COPY src/ ./src/

# Build TypeScript to dist/
RUN npm install --include=dev && npm run build && npm prune --production

# The data volume is mounted at /data at runtime
VOLUME ["/data"]

ENV PORT=3001
ENV DATA_DIR=/data
ENV NODE_ENV=production

EXPOSE 3001

CMD ["node", "--experimental-sqlite", "dist/index.js"]
