import re
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ----------------- 原有代码保持不变 -----------------
def download_file(url):
    # 原有实现不变
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logging.error(f"下载文件失败: {e}")
        return None

def extract_urls(text):
    # 原有实现不变
    pattern = re.compile(
        r'http://'
        r'(?:'
        r'(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'|'
        r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
        r')'
        r'(?::\d{1,4})'
        r'(?=/|$)',
        re.IGNORECASE
    )
    return pattern.findall(text)

def check_video_speed(url, timeout=5, duration=5, min_speed=10):
    # 原有实现不变
    try:
        start_time = time.time()
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        downloaded_size = 0
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                downloaded_size += len(chunk)
                if time.time() - start_time >= duration:
                    break
        
        elapsed_time = time.time() - start_time
        if elapsed_time == 0:
            return None
            
        speed = (downloaded_size / 1024) / elapsed_time
        if speed >= min_speed:
            logging.info(f"有效地址: {url} (网速: {speed:.2f} KB/s)")
            return url.rstrip('/')
        else:
            logging.warning(f"无效地址: {url} (网速: {speed:.2f} KB/s)")
    except requests.RequestException as e:
        logging.error(f"请求失败: {url} (错误: {e})")
    return None

def validate_urls(urls, num_threads=10):
    # 原有实现不变
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(check_video_speed, url) for url in urls]
        for future in futures:
            result = future.result()
            if result:
                valid_urls.append(result)
    return valid_urls

def save_urls_to_file(urls, filename):
    # 原有实现不变
    with open(filename, "w") as file:
        for index, base_url in enumerate(urls, start=1):
            full_url = f"{base_url}/hls/1/index.m3u8"
            file.write(f"{index},{full_url}\n")
    logging.info(f"已保存 {len(urls)} 个有效地址到 {filename}")

# ---------------- 新增扩展地址处理模块 ----------------
class AddressExpander:
    @staticmethod
    def read_source_file(filename):
        """读取原始文件并解析条目"""
        entries = []
        try:
            with open(filename, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        entries.append((parts[0], parts[1]))
            logging.info(f"成功读取 {len(entries)} 条原始地址")
            return entries
        except Exception as e:
            logging.error(f"文件读取失败: {e}")
            return []

    @staticmethod
    def generate_extensions(entries):
        """生成150个扩展地址"""
        extended = []
        pattern = re.compile(r"(/hls/)(\d+)(/index\.m3u8)$")
        
        for original_id, url in entries:
            match = pattern.search(url)
            if not match:
                continue
                
            base = match.group(1)
            suffix = match.group(3)
            
            for i in range(1, 151):
                new_id = f"{original_id}A{i}"
                new_url = re.sub(r"/hls/\d+/", f"{base}{i}/", url)
                extended.append((new_id, new_url))
                
        logging.info(f"已生成 {len(extended)} 个扩展地址")
        return extended

class SpeedValidator:
    @staticmethod
    def check_speed(entry, timeout=(3, 6), min_speed=1.0):
        """新版测速验证（3秒连接超时，6秒下载测速）"""
        entry_id, url = entry
        try:
            start = time.time()
            total_size = 0
            
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024):
                    if time.time() - start > 6:  # 总测速时间6秒
                        break
                    if chunk:
                        total_size += len(chunk)
            
            elapsed = max(time.time() - start, 0.1)
            speed = (total_size / 1024) / elapsed
            
            if speed >= min_speed:
                logging.info(f"[有效] {entry_id} 速度 {speed:.2f}KB/s")
                return (entry_id, url, speed)
                
        except Exception as e:
            logging.debug(f"[失败] {entry_id} {str(e)}")
        return None

    @staticmethod
    def batch_check(entries, workers=10):
        """批量测速"""
        valid = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(SpeedValidator.check_speed, entry) for entry in entries]
            for future in futures:
                result = future.result()
                if result:
                    valid.append(result)
        return valid

    @staticmethod
    def save_results(results, filename):
        """保存有效结果"""
        try:
            # 按数字顺序排序（1A1,1A2...2A1,2A2）
            sorted_results = sorted(results, 
                key=lambda x: (int(re.search(r"^\d+", x[0]).group()), 
                        int(re.search(r"A(\d+)$", x[0]).group(1)))
            
            with open(filename, "w") as f:
                for entry_id, url, _ in sorted_results:
                    f.write(f"{entry_id},{url}\n")
            logging.info(f"已保存 {len(sorted_results)} 个有效地址到 {filename}")
        except Exception as e:
            logging.error(f"保存失败: {e}")

def enhanced_main():
    # 原有主流程
    file_url = "https://d.kstore.dev/download/10694/hlstvid.txt"
    output_file = "iptv.txt"
    
    if (content := download_file(file_url)) is not None:
        raw_urls = list(set(extract_urls(content)))
        logging.info(f"发现 {len(raw_urls)} 个待验证地址")
        valid_urls = validate_urls(raw_urls)
        if valid_urls:
            save_urls_to_file(valid_urls, output_file)
        else:
            logging.warning("未找到有效地址")
    
    # 新增扩展地址处理流程
    # 第一阶段：生成扩展地址
    source_entries = AddressExpander.read_source_file("iptv.txt")
    extended_entries = AddressExpander.generate_extensions(source_entries)
    
    # 第二阶段：执行批量测速
    start_time = time.time()
    valid_results = SpeedValidator.batch_check(extended_entries)
    logging.info(f"测速完成 总耗时 {time.time()-start_time:.1f}秒")
    
    # 第三阶段：保存最终结果
    SpeedValidator.save_results(valid_results, "zszby.txt")

if __name__ == "__main__":
    enhanced_main()
