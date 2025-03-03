import re
import time
import logging
import requests
from urllib.parse import urlparse, urlunparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置参数（可根据需要调整）
CONFIG = {
    "source_url": "https://d.kstore.dev/download/10694/hlstvid.txt",
    "output_file": "tv1.txt",
    "request_timeout": 15,          # 请求超时时间（秒）
    "speed_test_duration": 8,       # 测速持续时间（秒）
    "min_speed": 0.5,               # 最低有效速度（KB/s）
    "max_workers": 15,              # 最大并发线程数
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 初始化日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("iptv_scan.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("IPTV-Scanner")

class IPTVScanner:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": CONFIG["user_agent"]})
        
        # 配置重试策略
        retry_adapter = requests.adapters.HTTPAdapter(
            max_retries=3,
            pool_connections=20,
            pool_maxsize=100
        )
        self.session.mount("http://", retry_adapter)
        self.session.mount("https://", retry_adapter)

    def _standardize_url(self, raw_url):
        """
        URL标准化处理
        输入示例: "example.com:8080/path" 
        输出示例: "http://example.com:8080/hls/1/index.m3u8"
        """
        try:
            # 补充协议头
            if not re.match(r"^https?://", raw_url, re.I):
                raw_url = f"http://{raw_url}"
            
            parsed = urlparse(raw_url)
            
            # 验证主机格式
            if not re.match(
                r"^([\w-]+\.)+[\w-]+(:\d{1,5})?$",  # 域名格式
                parsed.netloc,
                re.IGNORECASE
            ) and not re.match(
                r"^\d{1,3}(\.\d{1,3}){3}(:\d{1,5})?$",  # IP格式
                parsed.netloc
            ):
                raise ValueError("Invalid host format")
            
            # 重组标准化URL
            return urlunparse((
                parsed.scheme or "http",
                parsed.netloc,
                "/hls/1/index.m3u8",  # 固定路径
                "",    # 清除参数
                "",    # 清除查询
                ""     # 清除片段
            )).replace("///", "/")  # 处理空路径情况
        
        except Exception as e:
            logger.warning(f"URL标准化失败 [{raw_url}]: {type(e).__name__}")
            return None

    def _extract_base_urls(self, text):
        """从文本中提取基础URL"""
        pattern = re.compile(
            r"(?i)(?:https?://)?"  # 可选协议头
            r"("
            r"(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IPv4地址
            r"|"  # 或
            r"(?:[a-z0-9-]+\.)+[a-z]{2,}"  # 域名
            r")"
            r"(?::\d{1,5})?"  # 可选端口
            r"(?=/|$)",        # 路径开始或结束
            re.IGNORECASE
        )
        return list({match.group(0) for match in pattern.finditer(text)})

    def _speed_test(self, base_url):
        """执行速度测试"""
        try:
            # 生成标准URL
            std_url = self._standardize_url(base_url)
            if not std_url:
                return None
                
            logger.debug(f"正在测试: {std_url}")
            start_time = time.time()
            downloaded = 0
            
            with self.session.get(
                std_url,
                stream=True,
                timeout=CONFIG["request_timeout"]
            ) as response:
                response.raise_for_status()
                
                # 限时下载测速
                for chunk in response.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    if time.time() - start_time > CONFIG["speed_test_duration"]:
                        break
                
            # 计算有效速度
            duration = max(time.time() - start_time, 0.1)
            speed = (downloaded / 1024) / duration
            return (std_url, speed) if speed >= CONFIG["min_speed"] else None
            
        except Exception as e:
            logger.debug(f"测速失败 [{base_url}]: {type(e).__name__}")
            return None

    def batch_process(self, base_urls):
        """批量处理URL列表"""
        valid_results = []
        
        with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
            futures = {executor.submit(self._speed_test, url): url for url in base_urls}
            
            for future in as_completed(futures):
                base_url = futures[future]
                try:
                    if result := future.result():
                        valid_results.append(result)
                        logger.info(f"有效地址: {result[0]} (速度: {result[1]:.2f}KB/s)")
                except Exception as e:
                    logger.error(f"处理异常 [{base_url}]: {type(e).__name__}")
        
        # 按速度降序排序
        return sorted(valid_results, key=lambda x: x[1], reverse=True)

    def run_pipeline(self):
        """执行完整处理流程"""
        logger.info("=== IPTV扫描流程开始 ===")
        
        # 阶段1：下载源数据
        if not (source_text := self._download_source()):
            logger.error("源数据获取失败，终止流程")
            return []
        
        # 阶段2：提取基础URL
        base_urls = self._extract_base_urls(source_text)
        logger.info(f"发现 {len(base_urls)} 个待验证地址")
        
        if not base_urls:
            logger.warning("未找到有效基础地址")
            return []
        
        # 阶段3：批量验证
        valid_results = self.batch_process(base_urls)
        
        # 阶段4：保存结果
        if valid_results:
            self._save_results([url for url, _ in valid_results])
            logger.info(f"有效地址率: {len(valid_results)/len(base_urls):.1%}")
        else:
            logger.warning("未发现有效地址")
        
        logger.info("=== 流程结束 ===")
        return valid_results

    def _download_source(self):
        """下载源文件"""
        try:
            response = self.session.get(
                CONFIG["source_url"],
                timeout=CONFIG["request_timeout"]
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"源文件下载失败: {type(e).__name__}")
            return None

    def _save_results(self, urls):
        """保存结果到文件"""
        try:
            with open(CONFIG["output_file"], "w", encoding="utf-8") as f:
                f.write(f"# 最后更新: {time.strftime('%Y-%m-%d %H:%M')}\n")
                for idx, url in enumerate(urls, 1):
                    f.write(f"{idx},{url}\n")
            logger.info(f"结果已保存至 {CONFIG['output_file']}")
        except Exception as e:
            logger.error(f"文件保存失败: {type(e).__name__}")

# 测试模式
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        "39.165.257hfhh52:9003/hls/23/ind",
        "http://39.165hfdkbhb.218.252",
        "http://39.165fgggg.218.252:9003",
        "192.168.1.1:8080/any/path",
        "invalid.url:abc"
    ]
    
    # 初始化扫描器
    scanner = IPTVScanner()
    
    # 执行测试流程
    logger.setLevel(logging.DEBUG)  # 测试时开启DEBUG日志
    test_results = scanner.batch_process(test_cases)
    
    # 显示测试结果
    print("\n测试结果:")
    for url, speed in test_results:
        print(f"{url} => {speed:.2f}KB/s")
