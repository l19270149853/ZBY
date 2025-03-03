import requests
import time
import concurrent.futures
import logging
from urllib.parse import urlparse

# 调试模式配置
DEBUG_MODE = True

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

class EnhancedTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        
    def _normalize_url(self, raw_url):
        """增强URL处理"""
        try:
            # 自动补全缺失部分
            if "://" not in raw_url:
                raw_url = f"http://{raw_url}"
                
            parsed = urlparse(raw_url)
            if not parsed.path or "index.m3u8" not in parsed.path:
                return f"{parsed.scheme}://{parsed.netloc}/hls/1/index.m3u8"
            return raw_url
        except Exception as e:
            logging.error(f"URL处理失败: {raw_url} - {str(e)}")
            return None

    def _test_url(self, url):
        """增强测试方法"""
        try:
            # 第一阶段：快速连通性测试
            start = time.monotonic()
            resp = self.session.head(url, timeout=5, allow_redirects=True)
            if resp.status_code != 200:
                logging.debug(f"初步检查失败 [{resp.status_code}]: {url}")
                return None, 0

            # 第二阶段：速度测试
            downloaded = 0
            speed = 0
            with self.session.get(url, stream=True, timeout=10) as response:
                response.raise_for_status()
                
                for chunk in response.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    if time.monotonic() - start > 8:  # 最长8秒
                        break
                        
                elapsed = max(time.monotonic() - start, 0.1)
                speed = (downloaded / 1024) / elapsed
                return url, round(speed, 2)
                
        except Exception as e:
            error_type = type(e).__name__
            logging.debug(f"测试失败 [{error_type}]: {url}")
            return None, 0

    def run(self, urls):
        """执行测试"""
        valid = []
        
        # 预处理URL
        processed_urls = [self._normalize_url(u) for u in urls]
        processed_urls = [u for u in processed_urls if u is not None]
        
        if not processed_urls:
            logging.error("无有效URL可测试")
            return []
            
        logging.info(f"开始测试 {len(processed_urls)} 个URL...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = {executor.submit(self._test_url, url): url for url in processed_urls}
            
            for future in concurrent.futures.as_completed(futures, timeout=30):
                url = futures[future]
                try:
                    result_url, speed = future.result()
                    if result_url:
                        valid.append((result_url, speed))
                        logging.info(f"✅ 有效地址: {result_url} ({speed}KB/s)")
                except Exception as e:
                    logging.error(f"任务异常: {url} - {str(e)}")

        # 按速度排序
        return sorted(valid, key=lambda x: x[1], reverse
