import atexit
import mimetypes
import os
import pathlib
import random
from pathlib import Path
from typing import Dict, Any, Optional, Union
from urllib.parse import urlparse, unquote

import aiohttp
import filetype
from mcp.server.fastmcp.server import FastMCP
from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright, \
    TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth


class XiaohongshuBrowser:
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self.cdp_url = cdp_url
        self.auth_file = Path(__file__).resolve().parent / "xiaohongshu_auth.json"

    async def _setup_browser(self):
        if not os.path.exists(self.auth_file):
            with open(self.auth_file, "w") as f:
                f.write("{}")
        # 快速检查 CDP 是否可用
        if not await self.is_cdp_available(self.cdp_url):
            raise Exception("CDP URL 不可用")
        # 获取 WebSocket URL
        ws_url = await self.get_ws_url(self.cdp_url)
        stealth = Stealth(
            navigator_user_agent_override="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            , navigator_languages_override=("zh-CN", 'zh')
        )
        self.playwright = await stealth.use_async(async_playwright()).__aenter__()
        self.browser = await self.playwright.chromium.connect_over_cdp(ws_url, timeout=5000)

        self.context = await self.browser.new_context(
            storage_state=self.auth_file
            , ignore_https_errors=True
            , device_scale_factor=1.0  # 禁用HiDPI缩放
            , is_mobile=False
            , timezone_id="Asia/Shanghai"
            , bypass_csp=True
        )
        self.context.set_default_timeout(15000)
        self.page = await self.context.new_page()

        def close_callback():
            print("页面关闭回调")
            self.is_logged_in = False

        self.page.on('close', close_callback)

    async def is_cdp_available(self, cdp_url: str, timeout: int = 2) -> bool:
        """快速检查 CDP URL 是否可用"""
        try:
            if cdp_url.startswith("http"):
                # 检查 HTTP CDP 端点
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                            f"{cdp_url}/json/version",
                            timeout=timeout,
                            headers={"Accept": "application/json"}
                    ) as resp:
                        return resp.status == 200

            elif cdp_url.startswith(("ws://", "wss://")):
                # 直接检查 WebSocket 连接
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(cdp_url, timeout=timeout):
                        return True

            return False
        except:
            return False

    async def get_ws_url(self, cdp_url: str) -> str:
        """获取可用的 WebSocket URL"""
        if cdp_url.startswith(("ws://", "wss://")):
            return cdp_url

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{cdp_url}/json/version",
                        timeout=3,
                        headers={"Accept": "application/json"}
                ) as resp:
                    data = await resp.json()
                    return data["webSocketDebuggerUrl"]
        except:
            return cdp_url  # 失败时返回原 URL

    async def _ensure_browser(self):
        if not self.page or self.page.is_closed():
            await self._setup_browser()

    async def _save_session(self):
        try:
            await self.page.context.storage_state(path=self.auth_file)
            print("登录状态已保存")
        except Exception as e:
            print(f"保存会话失败: {str(e)}")

    async def _check_login_status(self):
        if self.is_logged_in:
            return True
        try:
            await self.page.goto("https://www.xiaohongshu.com/", wait_until="domcontentloaded")
            # 检查是否存在登录按钮
            login_btns = await self.page.query_selector_all(".login-btn, .sign-in")
            # 检查是否存在用户头像
            avatar = await self.page.query_selector(".reds-avatar")
            is_logged_in = avatar or len(login_btns) == 0
            self.is_logged_in = is_logged_in
            print("检测到已登录状态" if is_logged_in else "检测到未登录状态")
            return is_logged_in
        except Exception as e:
            print(f"检查登录状态失败: {str(e)}", e)
            return False

    async def _close_browser(self) -> Dict[str, Any]:
        resources = [
            ("page", lambda: self.page.close(), "页面"),
            ("context", lambda: self.context.close(), "浏览器上下文"),
            ("browser", lambda: self.browser.close(), "浏览器"),
            ("playwright", lambda: self.playwright.stop(), "Playwright")
        ]

        results = []
        for attr, closer, name in resources:
            obj = getattr(self, attr, None)
            if not obj:
                continue
            try:
                await closer()
                results.append(f"{name}已关闭")
                setattr(self, attr, None)  # 立即解除引用
            except Exception as e:
                results.append(f"关闭{name}时出错: {str(e)}")
                # 即使失败也继续尝试关闭其他资源
        success = all("出错" not in msg for msg in results)
        return {
            "success": success,
            "message": " | ".join(results),
            "details": results
        }

# MCP服务实例
mcp = FastMCP("Xiaohongshu", port=10001, host='0.0.0.0')

browsers = {
    "theone": XiaohongshuBrowser("http://192.168.3.7:9222"),
    "rongyao30": XiaohongshuBrowser("http://192.168.3.72:9222"),
    "mi6": XiaohongshuBrowser("http://192.168.3.18:9222"),
}


async def select_active_browser() -> XiaohongshuBrowser:
    for browser_id, browser in browsers.items():
        try:
            await browser._ensure_browser()
            print(f"优先使用 {browser_id} 浏览器")
            return browser
        except Exception as e:
            print(e)

    print(f"没有可用浏览器")
    raise RuntimeError("没有可用浏览器")


async def preferred_browser() -> XiaohongshuBrowser:
    browser = await select_active_browser()
    ok = await browser._check_login_status()
    if ok:
        return browser
    print(f"未登录小红书账号")
    raise RuntimeError("未登录小红书账号")


async def clean_browsers():
    for b in browsers.values():
        try:
            await b._close_browser()
        except:
            continue
    return {"success": True, "message": "浏览器资源已完全清理"}

import asyncio
def handle_shutdown(signum, frame):
    """处理关机信号"""
    print(f"接收到关机信号 {signum}, 正在清理资源...")    
    asyncio.create_task(clean_browsers())
    print("资源清理完成，程序退出")

import signal
signal.signal(signal.SIGINT, handle_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, handle_shutdown)  # kill命令

@atexit.register
def cleanup():
    """程序退出时的清理"""
    print("程序退出，cleanup正在清理资源...")
    asyncio.run(clean_browsers())
    print("资源清理完成")


# @mcp.tool()
async def scroll():
    page = (await preferred_browser()).page
    await page.evaluate("""
        const scroller = document.querySelector('.note-scroller');
        if (scroller) scroller.scrollTop = scroller.scrollHeight;
    """)
    await page.wait_for_timeout(2000)
    return {"success": True, "message": "滚动完成"}


@mcp.tool()
async def login() -> Dict[str, Any]:
    """小红书登录"""
    bowser = await select_active_browser()
    await bowser._check_login_status()
    try:
        if bowser.is_logged_in:
            return {"success": True, "message": "已是登录状态"}

        await bowser.page.goto("https://www.xiaohongshu.com/", wait_until="domcontentloaded")
        # 这里建议人工扫码或手动登录
        print("请手动完成登录...")
        await bowser.page.wait_for_selector(".reds-avatar", timeout=120000)
        bowser.is_logged_in = True
        await bowser._save_session()
        return {"success": True, "message": "登录成功"}
    except PlaywrightTimeoutError:
        return {"success": False, "message": "登录超时，请检查是否完成登录"}
    except Exception as e:
        return {"success": False, "message": f"登录失败: {str(e)}"}


# @mcp.tool()
async def get_current_page_articles() -> Dict[str, Any]:
    return await parse_current_page_articles()

async def parse_current_page_articles() -> Dict[str, Any]:
    """获取当前页面笔记列表"""
    try:
        page = (await preferred_browser()).page
        articles = []
        article_elements = await page.query_selector_all(".note-item")
        for element in article_elements:
            try:
                title_elem = await element.query_selector(".footer .title")
                title = await title_elem.inner_text() if title_elem else ""
                link_elem = await element.query_selector(".cover, .mask, .ld")
                link = await link_elem.evaluate("el => el.href") if link_elem else ""
                author_elem = await element.query_selector(".author .name")
                author = await author_elem.inner_text() if author_elem else ""
                like_elem = await element.query_selector(".footer .like-wrapper .count")
                like = await like_elem.inner_text() if like_elem else ""
                articles.append({
                    "title": title.strip(),
                    "author": author.strip(),
                    "link": link,
                    "like": like.strip(),
                })
            except Exception as e:
                continue
        return {
            "success": True,
            "articles": articles,
            "count": len(articles)
        }
    except Exception as e:
        return {"success": False, "message": f"搜索失败: {str(e)}"}


# @mcp.tool()
async def search_articles(keyword: str, ) -> Dict[str, Any]:
    """
    搜索笔记
    args:
        keyword: 搜索关键字
    """
    try:
        page = (await preferred_browser()).page
        await page.goto(f"https://www.xiaohongshu.com/search_result?keyword={keyword}",
                        wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        return await parse_current_page_articles()
    except Exception as e:
        return {"success": False, "message": f"搜索失败: {str(e)}"}


# @mcp.tool()
async def get_article_content(article_url: str) -> Dict[str, Any]:
    """
    获取笔记内容
    args:
        article_url: 笔记的url
    """
    try:
        page = (await preferred_browser()).page
        await page.goto(article_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        content_elements = await page.query_selector_all(".desc .note-text")
        for element in content_elements:
            content = await element.inner_text()
            return {"success": True, "content": content.strip()}
        return {"success": False, "message": "未找到内容"}
    except Exception as e:
        return {"success": False, "message": f"搜索失败: {str(e)}"}


# @mcp.tool()
async def view_article_comments(article_url: str, limit: int = 20) -> Dict[str, Any]:
    """
    查看小红书笔记的评论
    args:
        article_url: 笔记的url
        limit: 评论数量
    """
    try:
        page = (await preferred_browser()).page
        await page.goto(article_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await page.evaluate("""
            const scroller = document.querySelector('.note-scroller');
            if (scroller) scroller.scrollTop = scroller.scrollHeight;
        """)
        await page.wait_for_timeout(2000)
        comments = []
        comment_elements = await page.query_selector_all(
            ".comments-container .list-container .parent-comment")
        for element in comment_elements[:limit]:
            try:
                username_elem = await element.query_selector(".author")
                username = await username_elem.inner_text() if username_elem else ""
                content_elem = await element.query_selector(".content, .note-text")
                content = await content_elem.inner_text() if content_elem else ""
                date_elem = await element.query_selector(".info .date > span:not(.location)")
                date = await date_elem.inner_text() if date_elem else ""
                location_elem = await element.query_selector(".info .date > .location")
                location = await location_elem.inner_text() if location_elem else ""
                # 子评论递归获取
                replies = []
                reply_container = await element.query_selector(".reply-container")
                if reply_container:
                    replies = await get_sub_comments(reply_container, max_expand=5)

                comments.append({
                    "username": username.strip(),
                    "content": content.strip(),
                    "date": date.strip(),
                    "location": location.strip(),
                    "replies": replies,
                })
            except Exception as e:
                continue
        return {
            "success": True,
            "article_url": article_url,
            "comments": comments,
            "count": len(comments)
        }
    except Exception as e:
        return {"success": False, "message": f"获取评论失败: {str(e)}"}


async def get_sub_comments(reply_container, max_expand=5):
    """递归获取子评论，边获取边展开"""
    replies = []
    expand_count = 0
    page = (await preferred_browser()).page
    while True:
        # 1. 获取当前已加载的子评论
        sub_comments = await reply_container.query_selector_all(".comment-item-sub")
        for sub in sub_comments[len(replies):]:  # 只处理新出现的
            sub_username_elem = await sub.query_selector(".author .name")
            sub_username = await sub_username_elem.inner_text() if sub_username_elem else ""
            sub_content_elem = await sub.query_selector(".content, .note-text")
            sub_content = await sub_content_elem.inner_text() if sub_content_elem else ""
            sub_date_elem = await sub.query_selector(".info .date > span:not(.location)")
            sub_date = await sub_date_elem.inner_text() if sub_date_elem else ""
            sub_location_elem = await sub.query_selector(".info .date > .location")
            sub_location = await sub_location_elem.inner_text() if sub_location_elem else ""
            replies.append({
                "username": sub_username.strip(),
                "content": sub_content.strip(),
                "date": sub_date.strip(),
                "location": sub_location.strip(),
            })
        # 2. 判断是否还有“展开更多回复”
        show_more_btn = await reply_container.query_selector(".show-more")
        if show_more_btn and expand_count < max_expand:
            try:
                await show_more_btn.click()
                await reply_container.wait_for_selector(".comment-item-sub", timeout=5000)
                await page.wait_for_timeout(random.randint(1000, 2000))
                expand_count += 1
                continue  # 继续处理新加载的
            except Exception as e:
                break
        break
    return replies


@mcp.tool()
async def post_comment(article_url: str, comment_text: str) -> Dict[str, Any]:
    """
    发布笔记评论，对笔记进行评论
    args:
        article_url: 要评论的笔记的url
        comment_text: 评论内容文本
    """
    try:
        page = (await preferred_browser()).page
        await page.goto(article_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        input_box = await page.query_selector(".input-box .content-edit")
        if input_box:
            await input_box.click()
            await page.wait_for_timeout(1000)
            comment_input = await page.query_selector(".input-box .content-edit .content-input")
            if comment_input:
                await comment_input.fill(comment_text)
                submit_btn = await page.query_selector("button:has-text('发表'), button:has-text('发送')")
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(3000)
                    return {
                        "success": True,
                        "message": "评论发表成功",
                        "comment": comment_text
                    }
        return {"success": False, "message": "未找到评论输入框或按钮"}
    except Exception as e:
        return {"success": False, "message": f"评论发表失败: {str(e)}"}


@mcp.tool()
async def post_note(title: str, content: str, abstract: Optional[str]=None, tags: Optional[list[str]] = None,
                    image: Optional[list[Union[pathlib.Path, str]]] = None) -> Dict[str, Any]:
    """
    发布笔记
    args:
        title: 笔记标题，必填，最长20个字
        abstract: 笔记摘要，归纳笔记要点，列表形式每行一条，非必填但图片和摘要二选一
        content: 笔记正文（正文最后不包含笔记标签）
        tags: 笔记话题标签
        image: 笔记配图，非必填但图片和摘要二选一
    """
    try:
        page = (await preferred_browser()).page
        await page.goto("https://creator.xiaohongshu.com/publish/publish?source=official")
        await page.wait_for_selector('.upload-container')

        if image:
            await post_image_text_note(title, content, tags, image)
        else:
            await post_text_note(title, abstract, content, tags)

        await page.goto("https://www.xiaohongshu.com", wait_until="commit")

        return {"success": True, "message": "笔记发布成功", "title": title}
    except Exception as e:
        print(e)
        return {"success": False, "message": f"发布笔记失败: {str(e)}"}


async def human_wait(page, min_ms: int = 500, max_ms: int = 1000):
    base = 200
    delay = random.randint(min_ms, max_ms) + base
    await page.wait_for_timeout(delay)


async def post_text_note(title: str, abstract: str, content: str, tags: Optional[list[str]] = None):
    page = (await preferred_browser()).page
    # 选择纯文本
    await page.locator('.upload-container .creator-tab:has-text("写长文"):not([style])').click()
    await page.wait_for_selector('.new-btn', timeout=20000)
    # 进入编辑
    await page.locator('.new-btn').click()
    await human_wait(page)
    # 填写标题
    await page.get_by_placeholder("输入标题").fill(title)
    await human_wait(page)
    # 填写摘要
    await page.fill('.rich-editor-content .ProseMirror', abstract)
    await human_wait(page)
    # 下一步
    await page.locator(".next-btn", has_text="一键排版").click()
    # 等待生成图片页面加载完成
    await page.wait_for_selector(".loading-card")
    await page.locator(".loading-card").first.wait_for(state="detached", timeout=30000)
    await human_wait(page)
    # 下一步进入图文
    await page.locator(".footer .submit").click()
    # 等待图片页面加载完成
    await page.wait_for_selector(".post-page")
    # 填写正文
    await page.fill('.edit-container .ProseMirror', content)
    await human_wait(page)
    # 填写话题标签
    await page.keyboard.press("Control+End")
    await human_wait(page)
    await page.keyboard.press("Enter")
    await page.keyboard.press("Enter")
    await human_wait(page)
    if tags:
        for tag in tags:
            if not tag:
                continue
            await page.locator('#topicBtn').click()
            await human_wait(page)
            await page.keyboard.type(tag)
            await human_wait(page)
            await page.keyboard.press("Enter")
            await human_wait(page)
    # 发布
    await human_wait(page)
    await page.get_by_text("发布", exact=True).click()
    await page.get_by_text("发布成功").wait_for(state="visible")


async def post_image_text_note(title: str, content: str, tags: Optional[list[str]] = None,
                               image: Optional[list[Union[pathlib.Path, str]]] = None):
    page = (await preferred_browser()).page
    # 选择图文
    await page.locator('.upload-container .creator-tab:has-text("上传图文"):not([style])').click()
    await page.wait_for_selector(".upload-input", timeout=20000)
    # 上传图片
    await human_wait(page)
    await upload_image_first(image[0])
    if len(image) > 1:
        await upload_image(image[1:])
    # 填写标题
    await page.fill('input[placeholder="填写标题会有更多赞哦～"]', title)
    await human_wait(page)
    # 填写正文
    await page.fill('.edit-container .ProseMirror', content)
    await human_wait(page)
    # 填写话题标签
    await page.keyboard.press("Control+End")
    await human_wait(page)
    await page.keyboard.press("Enter")
    await page.keyboard.press("Enter")
    await human_wait(page)
    if tags:
        for tag in tags:
            if not tag or not tag.strip():
                continue
            await page.locator('#topicBtn').click()
            await human_wait(page)
            await page.keyboard.type(tag)
            await human_wait(page)
            await page.keyboard.press("Enter")
            await human_wait(page)
    # 发布
    await human_wait(page)
    await page.get_by_text("发布", exact=True).click()
    await page.get_by_text("发布成功").wait_for(state="visible")


async def upload_image_first(image: Union[pathlib.Path, str]):
    page = (await preferred_browser()).page
    file_payload = await get_file(image)
    if not file_payload:
        raise Exception(f"上传第一张图片失败：{image}")
    # 监听文件选择器弹出
    async with page.expect_file_chooser() as fc_info:
        await page.locator('.upload-input').click()
    file_chooser = await fc_info.value
    await file_chooser.set_files(file_payload)

    # 等待上传完成
    await human_wait(page,min_ms=1000, max_ms=2000)

    # 等待跳转
    await page.wait_for_selector(".post-page")
    await human_wait(page)


async def get_file(file: Union[str, pathlib.Path]):
    try:
        if isinstance(file, pathlib.Path):
            file_name = file.name
            with open(file, "rb") as f:
                file_byte = f.read()
        elif isinstance(file, str) and not file.startswith("http"):
            with open(file, "rb") as f:
                file_byte = f.read()
            file_name = os.path.basename(file)
        elif isinstance(file, str) and file.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(file, timeout=10) as resp:
                    if resp.status == 200:
                        file_byte = await resp.read()
            file_name = os.path.basename(unquote(urlparse(file).path))
        else:
            return None

        if kind := filetype.guess(file_byte):
            mime_type = kind.mime
        elif mime_types := mimetypes.guess_type(file_name):
            mime_type, _ = mime_types
        else:
            mime_type = "application/octet-stream"
        file = {
            "name": file_name,
            "mimeType": mime_type,
            "buffer": file_byte
        }
        return file
    except Exception as e:
        print(e)
        return None


async def upload_image(images: list[Union[pathlib.Path, str]]) -> Optional[str]:
    try:
        page = (await preferred_browser()).page
        for image in images:
            await human_wait(page)
            file_payload = await get_file(image)
            if not file_payload:
                continue

            # 监听文件选择器弹出
            async with page.expect_file_chooser() as fc_info:
                await page.locator('.img-upload-area .entry').click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(file_payload)

            # 等待上传完成
            await human_wait(page,min_ms=1000, max_ms=2000)

    except Exception as e:
        print(f"图片上传失败: {str(e)}")


@mcp.tool()
async def close_browser() -> Dict[str, Any]:
    return await clean_browsers()


# """
if __name__ == "__main__":
    mcp.run(transport='streamable-http')
    # mcp.run(transport='stdio')
# """

"""
from fastmcp import Client
import asyncio
import time

client = Client(mcp)


async def call_tool(arg: str):
    async with client:
        start = time.perf_counter()
        # result = await client.call_tool("login")
        # result = await client.call_tool("search_articles", {"keyword": arg})
        # result = await client.call_tool("get_current_page_articles")
        result = await client.call_tool("get_article_content", {"article_url":"https://bot.sannysoft.com"})
        # result = await client.call_tool("view_article_comments", {"article_url": "https://www.xiaohongshu.com/explore/67acaee3000000002903b9d3?xsec_token=ABgLq7EQbQbcqWZ3ZJEOv98WyaGPw3wkBIQ1WosKHNoCE=&xsec_source=pc_search&source=unknown", "limit": 10})
        # result = await client.call_tool("post_note",{"title": "✨今日运势指南｜你的专属幸运日✨","content": "🌟今日整体运势：\n今天会是充满机遇的一天！宇宙能量特别眷顾你，适合尝试新事物或做出重要决定。\n\n💖爱情运势：\n单身的朋友可能会遇到心动瞬间，有伴侣的记得给TA一个小惊喜～\n\n💰财运：\n有意外之财的可能，但也要理性消费哦！\n\n⚡幸运物：\n银色饰品能为你带来好运\n\n#今日运势 #星座运势 #好运来","tags": ["今日运势","星座运势","好运来"],"image": []})
        print(result)
        end = time.perf_counter()
        elapsed = end - start  # 转换为秒
        print(f"耗时: {elapsed:.6f}  秒")


asyncio.run(call_tool("潮汕美食"))
# """
