# 小红书 MCP 服务器

基于模型上下文协议（MCP）的小红书自动化服务器，使用Playwright实现无头浏览器自动操作。本项目通过CDP（Chrome DevTools Protocol）实现浏览器自动化，提供内容搜索、笔记浏览、评论互动等核心功能，支持笔记创作、评论分析等场景。

## 主要更新
- ✅ 使用 Playwright + CDP 实现自动化控制
- 📂 支持多浏览器实例热切换
- 🔐 自动加载/保存会话状态
- 🚀 提供完整的MCP工具接口

## 功能特性

### 已实现功能
- **会话管理**：保存登录状态 (xiaohongshu_auth.json)
- **搜索功能**：关键词搜索笔记 (search_articles)
- **内容查看**：获取笔记详情 (get_article_content)
- **评论系统**：读取/发布评论 (view_article_comments, post_comment)
- **笔记发布**：支持图文/纯文本笔记发布 (post_note)
- **页面滚动**：自动加载更多内容 (scroll)

### 开发中功能
- ▢ 点赞/收藏操作
- ▢ 粉丝互动功能
- ▢ 多账号管理

## 环境要求
- Python 3.10+
- Chrome/Chromium 120+ (启用调试模式)
- Playwright 1.36+ 
- fastmcp 0.4.1+

## 安装步骤

1. 克隆项目：
```bash
git clone https://github.com/yourname/xiaohongshu-mcp.git
cd xiaohongshu-mcp
```

2. 安装依赖：
```bash
uv pip install -r requirements.txt
```

3. 安装浏览器：
```bash
playwright install chromium
```

## 使用方法

### 启动浏览器调试服务
1. 新开终端执行：
```bash
chrome --remote-debugging-port=9222
```

2. 登录浏览器手动完成小红书账号登录

### 开发者快速启动
```bash
# 执行测试函数
uv run test_tools.py

# 启动MCP服务
uv run mcp_server_playwright.py

# 启动调试
fastmcp dev mcp_server_playwright.py
```

## 工具接口文档

| 工具名称          | 参数说明                          | 返回值类型            |
|-------------------|---------------------------------|-----------------------|
| login()           | 无参数                           | 登录状态检测          |
| search(keyword)   | keyword: 搜索关键词               | 笔记列表数据          |
| get_article(url)  | url: 笔记链接                     | 内容文本提取          |
| view_comments(url)| url: 笔记链接                     | 评论层级解析          |
| post_comment()    | url: 笔记链接, text: 评论内容       | 发表状态反馈          |
| post_note()       | 标题/内容/标签/配图参数            | 发布操作结果          |
| scroll()          | 无参数                           | 页面滚动状态         |

## 注意事项
1. 首次运行必须手动登录保存会话
2. 多浏览器支持：修改配置文件中的CSP端口
3. 评论操作需注意平台的频率限制（建议>30s/次）
4. 会话文件默认存储路径：xiaohongshu_auth.json

## 授权声明
本项目仅用于技术研究，使用时请遵守小红书使用协议及《网络信息安全法》相关规定。

## 贡献指南
1. 提交issue描述功能需求
2. Fork后提交PR
3. 添加测试用例和文档更新

## 常见问题

Q: 报错"Connect Over CDP failed"?
A: 请检查浏览器是否已启动并启用调试端口

Q: 如何实现多账号管理？
A: 复制浏览器实例到单独目录，修改配置文件中的auth_file参数
