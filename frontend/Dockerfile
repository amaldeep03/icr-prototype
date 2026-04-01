### Multi-stage build: build with Node, serve with nginx
FROM node:18-alpine AS builder

WORKDIR /app

# Allow passing VITE_API_BASE at build-time (will be embedded into the static bundle)
ARG VITE_API_BASE
ENV VITE_API_BASE=${VITE_API_BASE}

COPY package.json package-lock.json* ./
RUN npm ci --silent || npm install --silent

COPY . .

RUN npm run build

### Production image
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]