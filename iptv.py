import re
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ----------------- 基础功能模块 -----------------
def download_file(url):
    """下载远程文件"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"下载失败: {e}")
        return None

def extract_urls(text):
    """提取URL地址"""
    pattern = re.compile(
        r'http://(?:'
        r'\d{1,3}(?:\.\d{1,3}){3}|'          # IPv4地址
        r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})' # 域名
        r'(?::\d{1,4})'                      # 端口号
        r'(?=/|$)',                          # 路径或结束
        re.IGNORECASE
    )
    return pattern.findall(text)

def validate_urls(urls, num_threads=10):
    """多线程验证地址有效性"""
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(check_video_speed, url) for url in urls]
        for future in futures:
            if (result := future.result()):
                valid_urls.append(result)
    return valid_urls

def check_video_speed(url, timeout=5, duration=5, min_speed=10):
    """测速验证"""
    try:
        start = time.time()
        downloaded = 0
        
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            for chunk in r.iter_content(1024):
                if chunk:
                    downloaded += len(chunk)
                if time.time() - start >= duration:
                    break
        
        elapsed = max(time.time() - start, 0.1)
        speed = (downedloaded / 1024) / elapsed
        
        if speed >= min_speed:
            logging.info(f"有效 {url} ({speed:.2f}KB/s)")
            return url.rstrip('/')
        else:
            logging.warning(f"低速 {url} ({speed:.2f}KB/s)")
    except Exception as e:
        logging.debug(f"失败 {url}: {str(e)}")
    return None

def save_urls_to_file(urls, filename):
    """保存基础结果"""
    with open(filename, "w") as f:
        for idx, url in enumerate(urls, 1):
            f.write(f"{idx},{url}/hls/1/index.m3u8\n")
    logging.info(f"已保存 {len(urls)} 条基础地址")

# ---------------- 扩展地址处理模块 ----------------
class AddressExpander:
    @staticmethod
    def generate_from_file(filename):
        """从文件生成扩展地址"""
        entries = []
        try:
            with open(filename) as f:
                for line in f:
                    if not (line := line.strip()):
                        continue
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        entries.append((parts[0], parts[1]))
            logging.info(f"读取 {len(entries)} 条原始记录")
        except Exception as e:
            logging.error(f"文件读取错误: {e}")
            return []
        
        return AddressExpander.generate_extensions(entries)

    @staticmethod
    def generate_extensions(entries):
        """生成150个扩展地址"""
        extended = []
        pattern = re.compile(r"/hls/(\d+)/index\.m3u8$")
        
        for orig_id, url in entries:
            if not pattern.search(url):
                continue
                
            for i in range(1, 151):
                new_url = re.sub(r"/hls/\d+/", f"/hls/{i}/", url)
                extended.append((f"{orig_id}A{i}", new_url))
        
        logging.info(f"生成 {len(extended)} 扩展地址")
        return extended

class SpeedTester:
    def __init__(self, workers=10, min_speed=1.0):
        self.workers = workers
        self.min_speed = min_speed
    
    def _test_speed(self, entry):
        """单个地址测速"""
        entry_id, url = entry
        try:
            start = time.time()
            total = 0
            
            with requests.get(url, stream=True, timeout=(3, 6)) as r:
                r.raise_for_status()
                for chunk in r.iter_content(1024):
                    total += len(chunk)
                    if time.time() - start >= 6:
                        break
            
            elapsed = max(time.time() - start, 0.1)
            speed = (total / 1024) / elapsed
            
            if speed >= self.min_speed:
                logging.info(f"[通过] {entry_id} ({speed:.2f}KB/s)")
                return (entry_id, url)
        except Exception as e:
            logging.debug(f"[失败] {entry_id} {str(e)}")
        return None

    def batch_test(self, entries):
        """批量测试"""
        valid = []
        with ThreadPoolExecutor(self.workers) as executor:
            futures = [executor.submit(self._test_speed, e) for e in entries]
            for future in futures:
                if (result := future.result()):
                    valid.append(result)
        return valid

    @staticmethod
    def save_results(results, filename):
        """保存最终结果"""
        try:
            # 按数字排序：主ID -> 子ID
            sorted_list = sorted(
                results,
                key=lambda x: (
                    int(re.search(r"^\d+", x[0]).group()),
                    int(re.search(r"A(\d+)$", x[0]).group(1)
                )
            )
            
            with open(filename, "w") as f:
                for entry_id, url in sorted_list:
                    f.write(f"{entry_id},{url}\n")
            logging.info(f"保存 {len(sorted_list)} 条有效地址")
        except Exception as e:
            logging.error(f"保存失败: {e}")

# ----------------- 主程序 -----------------
def main():
    # 第一阶段：获取基础地址
    source_url = "https://d.kstore.dev/download/10694/hlstvid.txt"
    if (content := download_file(source_url)):
        raw_urls = list(set(extract_urls(content)))
        logging.info(f"发现 {len(raw_urls)} 潜在地址")
        
        valid_urls = validate_urls(raw_urls)
        if valid_urls:
            save_urls_to_file(valid_urls, "iptv.txt")
        else:
            logging.warning("无有效基础地址")
            return
    
    # 第二阶段：扩展地址测试
    tester = SpeedTester(workers=10)
    
    # 生成扩展地址
    extended = AddressExpander.generate_from_file("iptv.txt")
    if not extended:
        logging.error("无法生成扩展地址")
        return
    
    # 执行测速
    start = time.time()
    valid = tester.batch_test(extended)
    logging.info(f"测速完成 耗时 {time.time()-start:.1f}s")
    
    # 保存结果
    if valid:
        SpeedTester.save_results(valid, "zszby.txt")
    else:
        logging.warning("无有效扩展地址")

if __name__ == "__main__":
    main()
