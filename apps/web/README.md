# QuantOS Web Frontend

AI Quant Research OS 前端应用，基于 React + TypeScript + Vite 构建。

## 技术栈

- **框架**: React 18
- **语言**: TypeScript
- **构建工具**: Vite
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **路由**: React Router
- **HTTP 客户端**: Axios
- **图表**: Recharts
- **图标**: Lucide React

## 快速开始

### 安装依赖

```bash
cd apps/web
pnpm install
```

### 启动开发服务器

```bash
pnpm dev
```

前端将在 http://localhost:3000 启动。

### 构建生产版本

```bash
pnpm build
```

### 代码检查

```bash
pnpm lint
```

## 项目结构

```
src/
├── api/                    # API 服务层
│   ├── client.ts          # Axios 客户端配置
│   ├── services.ts        # API 服务函数
│   └── types.ts           # TypeScript 类型定义
├── components/            # 可复用组件
│   ├── ui/               # 基础 UI 组件
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   └── Input.tsx
│   ├── Layout.tsx        # 主布局
│   ├── Header.tsx        # 顶部导航
│   └── Sidebar.tsx       # 侧边栏
├── pages/                # 页面组件
│   ├── Dashboard.tsx     # 仪表盘
│   ├── MarketData.tsx    # 行情数据
│   ├── FactorEngine.tsx  # 因子引擎
│   ├── Backtest.tsx      # 回测系统
│   └── Agent.tsx         # AI Agent
├── store/                # 状态管理
│   ├── index.ts
│   ├── marketStore.ts
│   ├── factorStore.ts
│   ├── backtestStore.ts
│   └── agentStore.ts
├── App.tsx               # 主应用组件
├── main.tsx              # 应用入口
└── index.css             # 全局样式
```

## 功能模块

### 1. 仪表盘
- 系统概览统计
- 市场指数展示
- 最近活动记录
- 快速操作入口

### 2. 行情数据
- 股票搜索与筛选
- 股票详情查看
- 价格数据展示
- K线图表（待实现）

### 3. 因子引擎
- 因子分类浏览
- 因子计算执行
- 因子分析结果
- IC/IR 分析

### 4. 回测系统
- 回测参数配置
- 回测执行与监控
- 回测结果展示
- 回测历史记录

### 5. AI Agent
- Agent 选择与切换
- 对话式交互
- 消息历史记录
- Agent 状态监控

## 开发说明

### 环境变量

创建 `.env` 文件配置环境变量：

```env
VITE_API_BASE_URL=/api
```

### API 代理

开发模式下，API 请求会自动代理到 http://localhost:8000。

### 代码规范

- 使用 ESLint 进行代码检查
- 遵循 TypeScript 严格模式
- 使用 Tailwind CSS 进行样式开发
- 组件采用函数式组件 + Hooks

## 部署

### 构建

```bash
pnpm build
```

构建产物将输出到 `dist/` 目录。

### 部署到服务器

将 `dist/` 目录部署到 Web 服务器，配置 Nginx 或其他服务器处理 SPA 路由。

## 后续优化

1. **图表完善**: 添加 K线图、收益曲线等图表
2. **实时数据**: WebSocket 实时数据推送
3. **主题切换**: 完善深色/浅色主题切换
4. **国际化**: 支持中英文切换
5. **性能优化**: 代码分割、懒加载
6. **测试覆盖**: 添加单元测试和 E2E 测试