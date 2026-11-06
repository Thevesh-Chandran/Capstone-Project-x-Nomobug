# Daily refresh job: query BigQuery, build the Evidence site, upload it to the dashboard bucket.
# Credentials: the Cloud Run job's service account (cp2-dashboard-refresh), no key files.
FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY evidence.config.yaml ./
COPY pages ./pages
COPY sources ./sources
COPY static ./static
COPY refresh ./refresh
ENV NODE_OPTIONS=--max-old-space-size=3072
CMD ["sh", "-c", "npx evidence sources && npx evidence build && node refresh/upload.mjs"]
