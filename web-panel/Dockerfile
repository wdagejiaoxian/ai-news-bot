# ========================================
# AI News Bot Web Panel Dockerfile
# ========================================
# 构建: docker build -f web-panel/Dockerfile -t ai-news-bot-web:latest web-panel/

# 第一阶段：构建前端
FROM node:20-alpine AS builder

WORKDIR /app

# 复制 package 文件
COPY package.json package-lock.json* ./

# 安装依赖（含 devDependencies，vue-tsc 在 devDependencies 中）
RUN npm ci --legacy-peer-deps

# 复制源代码
COPY . .

# 构建生产版本
ENV NODE_ENV=production
RUN npm run build

# 第二阶段：运行 Nginx
FROM nginx:alpine

# 删除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 从构建阶段复制静态文件
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 3000

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]