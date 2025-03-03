import logging
import time  # 新增必要的导入
import re
import requests
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志（现在可以正常工作了）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("iptv_scan.log"),
        logging.StreamHandler()
    ]
)

class M3U8Scanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _standardize_m3u8_url(self, raw_url):
        """核心标准化方法"""
        try:
            if not re.match(r'^https?://', raw_url, re.I):
                raw_url = f'http://{raw_url}'

            parsed = urlparse(raw_url)
            return urlunparse((
                parsed.scheme or 'http',
                parsed.netloc,
                '/hls/1/index.m3u8',
                '',
                '',
                ''
            )).replace('//hls', '/hls')
        except Exception as e:
            logging.error(f"URL标准化失败: {raw_url} - {str(e)}")
            return None

    def _speed_test(self, url):
        """增强版速度测试"""
        try:
            start = time.time()
            downloaded = 0
            
            with self.session.get(url, stream=True, timeout=5) as response:
                response.raise_for_status()
                
                for chunk in response.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    if time.time() - start > 5:
                        break
                
            speed = (downloaded / 1024) / max(time.time() - start, 0.1)
            return speed >= 1.0
        except Exception as e:
            logging.debug(f"测速失败 {url}: {str(e)}")
            return False

    def process_url(self, raw_url):
        """完整处理流程"""
        std_url = self._standardize_m3u8_url(raw_url)
        if not std_url:
            return None
        
        logging.info(f"正在验证: {std_url}")
        if self._speed_test(std_url):
            return std_url
        return None

    def batch_process(self, url_list):
        """批量处理URL"""
        valid_urls = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.process_url, url): url for url in url_list}
            
            for future in as_completed(futures):
                url = futures[future]
                try:
                    if result := future.result():
                        valid_urls.append(result)
                        logging.info(f"验证通过: {result}")
                except Exception as e:
                    logging.error(f"处理异常 {url}: {str(e)}")
        
        return valid_urls

    def save_results(self, valid_urls):
        """保存结果文件"""
        with open("valid_m3u8.txt", "w") as f:
            f.write("# 最后更新: " + time.strftime("%Y-%m-%d %H:%M") + "\n")
            for idx, url in enumerate(valid_urls, 1):
                f.write(f"{idx},{url}\n")
        logging.info(f"已保存 {len(valid_urls)} 个有效地址")

if __name__ == "__main__":
    scanner = M3U8Scanner()
    
    test_urls = [
        "39.165.257hfhh52:9003/hls/23/ind",
        "http://39.165hfdkbhb.218.252",
        "http://39.165fgggg.218.252:9003",
        "invalid.url:abc",
        "https://example.com:8080/live/stream?token=123"
    ]
    
    valid = scanner.batch_process(test_urls)
    scanner.save_results(valid)
