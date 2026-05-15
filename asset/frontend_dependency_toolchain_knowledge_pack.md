# Frontend Dependency Toolchain Knowledge Pack

## 背景与范围

本知识包覆盖 TenderWord 前端依赖、lockfile、Next / Jest / ESLint / Tailwind / Playwright 工具链与 WSL 前端验证入口。它不替代 `frontend/package.json`、`frontend/package-lock.json` 或测试配置；代码和 lockfile 仍是真源。

适用场景：

- 修改 `frontend/package.json` 或 `frontend/package-lock.json`
- 升级 Next、React、Jest、jsdom、ESLint、Tailwind、Playwright、TypeScript 或相关类型包
- 处理 `npm audit`、`npm ls`、`npm ci`、Jest 配置加载、WSL 前端命令失败
- 移动运行时依赖与开发依赖边界

## 业务规则

- `frontend/package.json` 与 `frontend/package-lock.json` 必须成对提交；依赖变更通过 `npm install`、`npm uninstall`、`npm install --package-lock-only` 等 npm 命令生成，不手工拼 lockfile。
- 浏览器运行时依赖只保留应用运行所需包，例如 Next / React / UI runtime / store；Prettier、Jest、Playwright、ESLint、Tailwind、TypeScript、测试库和类型包属于 `devDependencies`。
- 不再被源码、脚本或配置引用的包应删除。例如误写或遗留包不能靠 lockfile 固定继续存在。
- 版本族要一起收敛：
  - `next` 与 `eslint-config-next` 保持同一 Next 版本线。
  - `jest`、`jest-environment-jsdom`、`@types/jest` 保持同一 Jest 主版本线。
  - Jest 30 读取 TypeScript Jest 配置时，Next 16 的 Jest 入口应使用 `next/jest.js`，否则运行 `jest` 可能出现 `ERR_MODULE_NOT_FOUND`。
- `npm audit --json` 的 `critical`、`high`、`moderate`、`low` 都应优先清零；若接受风险，必须有本地不可利用证据和回归记录。

## 输入输出样例

依赖收敛输入：

```json
{
  "next": "^16.2.6",
  "eslint-config-next": "16.1.6",
  "jest": "^29.7.0",
  "jest-environment-jsdom": "^30.3.0",
  "und": "^2.13.0",
  "prettier": "^3.8.1"
}
```

期望输出方向：

```json
{
  "dependencies": {
    "next": "^16.2.6"
  },
  "devDependencies": {
    "eslint-config-next": "^16.2.6",
    "jest": "^30.4.1",
    "jest-environment-jsdom": "^30.4.1",
    "@types/jest": "^30.0.0",
    "prettier": "^3.8.1"
  }
}
```

Jest 配置入口：

```ts
import nextJest from 'next/jest.js';
```

## 边界条件

- WSL 中必须优先使用 Linux `node` / `npm`，并用 Linux 临时目录运行测试：`TMPDIR=/tmp TMP=/tmp TEMP=/tmp`。
- Node 版本必须满足 `frontend/package.json` 的 `engines.node`，当前最低为 `>=20.9.0`；实际依赖还可能提出更高 patch 要求，安装失败时先看 npm engine 输出。
- `npm ls --depth=0` 若出现 `extraneous`，不得直接忽略。先确认：
  - `frontend/package.json` 没有声明该包；
  - `rg` 找不到源码、配置或脚本引用；
  - `npm prune --dry-run --json` 没有计划删除；
  - `npm audit --json` 为 0；
  - 该包来自 platform optional / bundled 依赖链。
- Playwright 依赖升级或浏览器基建变更必须跑 `npm run test:e2e`；只改纯 manifest 但不影响用户流程时，也应优先保留一次 e2e smoke 证据。

## 已知坑点

- `jest` 29 与 `jest-environment-jsdom` 30 混用会造成类型/运行时漂移；把 jsdom 降回 29 可能重新引入 jsdom 旧传递依赖漏洞。
- 只升级 `jest` 而保留 `@types/jest` 29，会让顶层 `@jest/types` 落在 29，而 Jest 30 依赖链落在 30，`frontend/jest.config.ts` 的 `next/jest` 类型桥接会在 `tsc --noEmit` 中失败。
- Next 16 包内存在 `jest.js` 与 `jest.d.ts`，但 Jest 30 通过 ESM 读取 TypeScript 配置时不会自动补全 `next/jest` 扩展名，应显式写 `next/jest.js`。
- `npm ci` 的 deprecated warning 不等于漏洞；是否阻塞以 `npm audit --json`、本地测试和可替代升级风险综合判断。

## 关联代码路径

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/jest.config.ts`
- `frontend/playwright.config.ts`
- `frontend/tsconfig.json`
- `AGENTS.md`

## 关联测试与验证入口

```bash
cd frontend
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm ci
npm ls --depth=0
TMPDIR=/tmp TMP=/tmp TEMP=/tmp npm audit --json
npm run lint
npm run type-check
TMPDIR=/tmp TMP=/tmp TEMP=/tmp CI=1 npm test -- --runInBand
npm run build
npm run test:e2e
```

## 回归风险

- 依赖版本族未同步会造成安装成功但类型检查或 Jest 配置加载失败。
- lockfile 未从干净安装验证会把本机 `node_modules` 残留误判为可复现状态。
- 将构建/测试工具放入 `dependencies` 会扩大生产依赖面和安全审计噪音。
- 忽略 Playwright smoke 会漏掉 Next / React / Tailwind / 浏览器运行时组合升级后的首屏或路由回归。
