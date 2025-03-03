import requests
import time
import concurrent.futures
from urllib.parse import urlparse
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

class StableSpeedTester:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"
        }

    def _normalize_url(self, raw_url):
        """标准化URL格式"""
        parsed = urlparse(raw_url)
        if not parsed.scheme:
            return f"http://{raw_url.strip('/')}/hls/1/index.m3u8"
        return f"{parsed.scheme}://{parsed.netloc}/hls/1/index.m3u8"

    def _test_single_url(self, url, timeout=8, duration=6, min_speed=5):
        """带超时保护的单URL测试"""
        best_speed = 0
        end_time = time.monotonic() + duration + 2  # 总超时保护

        try:
            # 第一阶段：快速连接测试
            with self.session.get(url, headers=self.headers, 
                                timeout=(3, 3), stream=True, verify=False) as resp:
                if resp.status_code != 200:
                    return None, 0

            # 第二阶段：速度测试
            start = time.monotonic()
            downloaded = 0
            with self.session.get(url, headers=self.headers, 
                                timeout=(timeout, timeout), stream=True, verify=False) as resp:
                resp.raise_for_status()
                
                for chunk in resp.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    if time.monotonic() - start >= duration:
                        break
                    if time.monotonic() > end_time:  # 全局超时保护
                        raise TimeoutError("Global timeout reached")

            elapsed = max(time.monotonic() - start, 0.1)
            best_speed = (downloaded / 1024) / elapsed
            if best_speed >= min_speed:
                return url, round(best_speed, 2)

        except requests.exceptions.RequestException as e:
            logging.debug(f"请求失败 {url}: {type(e).__name__}")
        except Exception as e:
            logging.error(f"未知错误 {url}: {str(e)}")
        
        return None, round(best_speed, 2)

    def safe_test_url(self, url, max_retries=1):
        """带重试的安全测试"""
        for _ in range(max_retries + 1):
            result, speed = self._test_single_url(url)
            if result:
                return result, speed
            time.sleep(0.5)
        return None, speed

    def batch_test(self, url_list, max_workers=8, timeout=30):
        """防卡死的批量测试"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="Tester"
        ) as executor:
            
            futures = {
                executor.submit(self.safe_test_url, url): url
                for url in (self._normalize_url(u) for u in url_list)
            }

            try:
                for future in concurrent.futures.as_completed(
                    futures, 
                    timeout=timeout  # 总体超时控制
                ):
                    url = futures[future]
                    try:
                        result, speed = future.result(timeout=1)  # 单任务结果超时
                        if result:
                            results.append((result, speed))
                            logging.info(f"有效: {result} ({speed}KB/s)")
                        else:
                            logging.debug(f"无效: {url}")
                    except concurrent.futures.TimeoutError:
                        logging.warning(f"任务超时: {url}")
            except concurrent.futures.TimeoutError:
                logging.error("总体执行超时，终止剩余任务")

        # 按速度排序并去重
        seen = set()
        return sorted(
            ([url, speed] for url, speed in results if not (url in seen or seen.add(url))),
            key=lambda x: x[1], 
            reverse=True
        )

# 使用示例
if __name__ == "__main__":
    tester = StableSpeedTester()
    
    test_urls = [
        "example.com:8080",
        "http://125.44.164.36:8888",
        "invalid.url:9999"
    ]
    
    print("开始稳定测试...")
    valid_list = tester.batch_test(test_urls)
    
    print("\n最终有效地址：")
    for idx, (url, speed) in enumerate(valid_list, 1):
        print(f"{idx}. {url.ljust(50)} 速度: {speed}KB/s")
