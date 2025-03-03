import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from urllib.parse import urlparse

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

class SpeedValidator:
    def __init__(self):
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

    def _enhance_url(self, url):
        """URL标准化处理"""
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"http://{url}"
        return url.strip()

    def check_video_speed(self, url, timeout=8, duration=6, min_speed=5, max_retries=2):
        """
        增强版速度检测函数
        :param url: 待检测的URL
        :param timeout: 单次请求超时时间(秒)
        :param duration: 最大检测时长(秒)
        :param min_speed: 最低速度要求(KB/s)
        :param max_retries: 最大重试次数
        :return: (有效URL, 实测速度) 或 (None, 0)
        """
        url = self._enhance_url(url)
        best_speed = 0
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                start_time = time.perf_counter()
                end_time = start_time + duration
                total_size = 0

                with requests.get(url, stream=True, 
                                 headers=self.default_headers,
                                 timeout=(timeout, timeout),
                                 verify=False) as response:
                    
                    response.raise_for_status()

                    # 分块下载数据
                    for chunk in response.iter_content(chunk_size=4096):
                        if chunk:
                            total_size += len(chunk)
                            if time.perf_counter() >= end_time:
                                break

                    # 计算实际有效时长
                    elapsed = max(time.perf_counter() - start_time, 0.1)
                    current_speed = (total_size / 1024) / elapsed

                    # 更新最佳速度
                    if current_speed > best_speed:
                        best_speed = current_speed

                    if best_speed >= min_speed:
                        logging.debug(f"尝试 {attempt+1} 成功: {url} ({best_speed:.2f}KB/s)")
                        return url, round(best_speed, 2)

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logging.debug(f"尝试 {attempt+1} 失败: {url} ({e.__class__.__name__})")
                time.sleep(1)  # 失败后等待
                continue

            except Exception as e:
                last_error = str(e)
                logging.error(f"未知错误: {url} ({str(e)})")
                break

        error_type = last_error.split(":")[0] if last_error else "Unknown"
        logging.warning(f"最终失败: {url} | 原因: {error_type} | 最佳速度: {best_speed:.2f}KB/s")
        return None, round(best_speed, 2)

    def validate_urls(self, urls, max_workers=15, progress_callback=None):
        """
        并发验证URL列表
        :param urls: URL列表
        :param max_workers: 最大并发数
        :param progress_callback: 进度回调函数
        :return: 有效URL列表 (带速度信息)
        """
        valid_results = []
        total = len(urls)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.check_video_speed, url): url for url in urls}
            
            for idx, future in enumerate(as_completed(futures), 1):
                result_url, speed = future.result()
                if result_url:
                    valid_results.append((result_url, speed))
                
                if progress_callback:
                    progress_callback(idx, total)

        # 按速度降序排序
        return sorted(valid_results, key=lambda x: x[1], reverse=True)

# 使用示例
if __name__ == "__main__":
    validator = SpeedValidator()
    
    # 测试URL列表
    test_urls = [
        "http://example.com:8080/hls/1/index.m3u8",
        "http://invalid.example.com/video.m3u8"
    ]
    
    print("开始速度验证...")
    valid_list = validator.validate_urls(test_urls)
    
    print("\n验证结果：")
    for idx, (url, speed) in enumerate(valid_list, 1):
        print(f"{idx}. {url.ljust(55)} 速度: {speed}KB/s")
