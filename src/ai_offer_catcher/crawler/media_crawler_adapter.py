from __future__ import annotations

import asyncio
import base64
import logging
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from playwright.async_api import BrowserContext, BrowserType, Page, Playwright, async_playwright
from tenacity import RetryError

from ai_offer_catcher.app_settings import AppSettings
from ai_offer_catcher.models.schemas import CrawlPostImage, CrawlPostRecord
from ai_offer_catcher.utils import compact_text, parse_xhs_timestamp, safe_int, sha256_bytes

logger = logging.getLogger(__name__)


class XhsCrawlerSession:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self.browser_context: BrowserContext | None = None
        self.context_page: Page | None = None
        self.cdp_manager = None
        self.client = None
        self._playwright_manager = None
        self._mc_utils = None

        root = str(self.settings.mediacrawler_root)
        if root not in sys.path:
            sys.path.insert(0, root)

    async def __aenter__(self) -> "XhsCrawlerSession":
        import config as mc_config
        from media_platform.xhs.client import XiaoHongShuClient
        from media_platform.xhs.login import XiaoHongShuLogin
        from tools import utils as mc_utils
        from tools.cdp_browser import CDPBrowserManager

        self._mc_config = mc_config
        self._mc_utils = mc_utils
        self._XiaoHongShuClient = XiaoHongShuClient
        self._XiaoHongShuLogin = XiaoHongShuLogin
        self._CDPBrowserManager = CDPBrowserManager
        self._install_qrcode_saver()

        mc_config.ENABLE_CDP_MODE = self.settings.enable_cdp
        mc_config.CDP_HEADLESS = self.settings.cdp_headless
        mc_config.CDP_CONNECT_EXISTING = self.settings.cdp_connect_existing
        mc_config.CDP_DEBUG_PORT = self.settings.cdp_port
        mc_config.HEADLESS = self.settings.headless
        mc_config.SAVE_LOGIN_STATE = self.settings.save_login_state
        mc_config.USER_DATA_DIR = self.settings.user_data_dir
        mc_config.CRAWLER_MAX_SLEEP_SEC = self.settings.request_sleep_seconds
        mc_config.MAX_CONCURRENCY_NUM = self.settings.max_concurrency
        mc_config.ENABLE_GET_COMMENTS = self.settings.enable_comments
        mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = self.settings.max_comments_per_post

        self._playwright_manager = await async_playwright().start()
        playwright = self._playwright_manager
        if self.settings.enable_cdp:
            self.browser_context = await self._launch_browser_with_cdp(playwright)
        else:
            self.browser_context = await self._launch_browser(playwright.chromium)
            stealth_path = str(self.settings.mediacrawler_root / "libs" / "stealth.min.js")
            await self.browser_context.add_init_script(path=stealth_path)
        self.context_page = await self.browser_context.new_page()
        await self.context_page.goto(self.settings.xhs_index_url)
        self.client = await self._create_client()
        if not await self.client.pong():
            login_obj = self._XiaoHongShuLogin(
                login_type="qrcode",
                login_phone="",
                browser_context=self.browser_context,
                context_page=self.context_page,
                cookie_str="",
            )
            await login_obj.begin()
            await self.client.update_cookies(browser_context=self.browser_context)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.cdp_manager:
            await self.cdp_manager.cleanup(force=True)
        elif self.browser_context:
            await self.browser_context.close()
        if self._playwright_manager:
            await self._playwright_manager.stop()

    async def _launch_browser(self, chromium: BrowserType) -> BrowserContext:
        if self.settings.save_login_state:
            user_data_dir = self.settings.mediacrawler_root / "browser_data" / self.settings.user_data_dir
            return await chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                accept_downloads=True,
                headless=self.settings.headless,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            )
        browser = await chromium.launch(headless=self.settings.headless)
        return await browser.new_context(viewport={"width": 1920, "height": 1080})

    async def _launch_browser_with_cdp(self, playwright: Playwright) -> BrowserContext:
        self.cdp_manager = self._CDPBrowserManager()
        return await self.cdp_manager.launch_and_connect(
            playwright=playwright,
            playwright_proxy=None,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            headless=self.settings.cdp_headless,
        )

    async def _create_client(self):
        assert self.browser_context is not None
        assert self.context_page is not None
        cookie_str, cookie_dict = self._mc_utils.convert_cookies(await self.browser_context.cookies(self.settings.xhs_index_url))
        return self._XiaoHongShuClient(
            headers={
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json;charset=UTF-8",
                "origin": self.settings.xhs_index_url,
                "pragma": "no-cache",
                "referer": f"{self.settings.xhs_index_url}/",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )

    async def search_page(
        self,
        keyword: str,
        page_no: int,
        search_id: str,
        sort_type: str = "latest",
    ) -> dict[str, Any]:
        from media_platform.xhs.field import SearchSortType

        sort_map = {
            "latest": SearchSortType.LATEST,
            "general": SearchSortType.GENERAL,
            "popular": SearchSortType.MOST_POPULAR,
        }
        return await self.client.get_note_by_keyword(
            keyword=keyword,
            page=page_no,
            search_id=search_id,
            sort=sort_map.get(sort_type, SearchSortType.LATEST),
        )

    async def fetch_note_detail(self, note_id: str, xsec_source: str, xsec_token: str) -> dict[str, Any] | None:
        try:
            note_detail = await self.client.get_note_by_id(note_id, xsec_source or "pc_search", xsec_token)
        except RetryError:
            note_detail = None
        if not note_detail:
            note_detail = await self.client.get_note_by_id_from_html(note_id, xsec_source or "pc_search", xsec_token, enable_cookie=True)
        if note_detail:
            note_detail.update({"xsec_token": xsec_token, "xsec_source": xsec_source or "pc_search"})
        await asyncio.sleep(self.settings.request_sleep_seconds)
        return note_detail

    async def download_media(self, url: str) -> bytes | None:
        return await self.client.get_note_media(url)

    def _install_qrcode_saver(self) -> None:
        from PIL import Image
        from tools import crawler_util
        from tools import utils as mc_utils

        qr_dir = self.settings.artifact_root / "login"
        qr_dir.mkdir(parents=True, exist_ok=True)
        qr_path = qr_dir / "xhs_login_qrcode.png"

        def _save_qrcode(qr_code: str) -> None:
            payload = qr_code.split(",", 1)[1] if "," in qr_code else qr_code
            image = Image.open(BytesIO(base64.b64decode(payload)))
            image.save(qr_path)
            logger.info("Saved Xiaohongshu login QR code to %s", qr_path)
            print(f"XHS login QR saved to: {qr_path}")

        crawler_util.show_qrcode = _save_qrcode
        mc_utils.show_qrcode = _save_qrcode

    @staticmethod
    def note_to_record(note_detail: dict[str, Any]) -> CrawlPostRecord:
        user_info = note_detail.get("user", {})
        interact_info = note_detail.get("interact_info", {})
        image_list = note_detail.get("image_list", [])
        normalized_images: list[CrawlPostImage] = []
        for index, image in enumerate(image_list):
            image_url = image.get("url_default") or image.get("url")
            if not image_url:
                continue
            normalized_images.append(CrawlPostImage(image_index=index, image_url=image_url))

        source_note_id = note_detail.get("note_id") or note_detail.get("id")
        note_url = f"https://www.xiaohongshu.com/explore/{source_note_id}?xsec_token={note_detail.get('xsec_token')}&xsec_source={note_detail.get('xsec_source', 'pc_search')}"
        merged_text = compact_text([note_detail.get("title"), note_detail.get("desc")])
        return CrawlPostRecord(
            source_note_id=source_note_id,
            note_url=note_url,
            xsec_token=note_detail.get("xsec_token"),
            xsec_source=note_detail.get("xsec_source"),
            note_type=note_detail.get("type"),
            title=note_detail.get("title") or (note_detail.get("desc") or "")[:255],
            content=note_detail.get("desc"),
            author_id=user_info.get("user_id"),
            author_nickname=user_info.get("nickname"),
            author_avatar=user_info.get("avatar"),
            ip_location=note_detail.get("ip_location"),
            like_count=safe_int(interact_info.get("liked_count")),
            collect_count=safe_int(interact_info.get("collected_count")),
            comment_count=safe_int(interact_info.get("comment_count")),
            share_count=safe_int(interact_info.get("share_count")),
            published_at=parse_xhs_timestamp(note_detail.get("time")),
            raw_note_json=note_detail,
            merged_text=merged_text,
            images=normalized_images,
        )

    @staticmethod
    def attach_downloaded_image(image: CrawlPostImage, content: bytes, local_path: str) -> CrawlPostImage:
        return CrawlPostImage(
            image_index=image.image_index,
            image_url=image.image_url,
            local_path=local_path,
            sha256=sha256_bytes(content),
        )
