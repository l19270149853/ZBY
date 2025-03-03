import re
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler("process.log")  # 输出到日志文件
    ]
)

# ----------------- 第一步：下载并解析原始文件 -----------------
def download_file(url):
    """下载远程文件内容"""
    try:
        logging.info(f"开始下载文件: {url}")
        response = requests.get(url)
        response.raise_for_status()  # 检查HTTP状态码
        return response.text
    except requests.RequestException as e:
        logging.error(f"文件下载失败: {e}")
        return None

def extract_urls(text):
    """从文本中提取URL地址"""
    pattern = re.compile(
        r'http://'  # 协议头
        r'(?:'  # 开始非捕获组
        r'(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IPv4地址
        r'|'  # 或
        r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'  # 域名
        r')'  # 结束非捕获组
        r'(?::\d{1,4})'  # 端口号
        r'(?=/|$)',  # 确保URL结束或有路径
        re.IGNORECASE
    )
    urls = pattern.findall(text)
    logging.info(f"从文件中提取到 {len(urls)} 个URL地址")
    return urls

def validate_urls(urls, num_threads=10):
    """多线程验证URL地址的有效性"""
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(check_video_speed, url) for url in urls]
        for future in futures:
            if (result := future.result()):
                valid_urls.append(result)
    logging.info(f"验证完成，共 {len(valid_urls)} 个有效地址")
    return valid_urls

def check_video_speed(url, timeout=5, duration=5, min_speed=10):
    """测试URL的加载速度"""
    try:
        start_time = time.time()
        downloaded_size = 0
        
        with requests.get(url, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    downloaded_size += len(chunk)
                if time.time() - start_time >= duration:
                    break
        
        elapsed_time = max(time.time() - start_time, 0.1)
        speed = (downloaded_size / 1024) / elapsed_time  # 计算速度（KB/s）
        
        if speed >= min_speed:
            logging.info(f"有效地址: {url} (速度: {speed:.2f} KB/s)")
            return url.rstrip('/')  # 返回处理后的URL
        else:
            logging.warning(f"低速地址: {url} (速度: {speed:.2f} KB/s)")
    except requests.RequestException as e:
        logging.error(f"请求失败: {url} (错误: {e})")
    return None

def save_urls_to_file(urls, filename):
    """将有效地址保存到文件"""
    try:
        with open(filename, "w") as file:
            for index, base_url in enumerate(urls, start=1):
                full_url = f"{base_url}/hls/1/index.m3u8"
                file.write(f"{index},{full_url}\n")
        logging.info(f"已保存 {len(urls)} 个有效地址到 {filename}")
    except Exception as e:
        logging.error(f"保存文件失败: {e}")

# ----------------- 第二步：生成扩展地址 -----------------
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
        pattern = re.compile(r"/hls/\d+/index\.m3u8$")
        
        for original_id, url in entries:
            if not pattern.search(url):
                continue
                
            base_url = re.sub(r"/hls/\d+/index\.m3u8$", "", url)
            for i in range(1, 151):
                new_id = f"{original_id}A{i}"
                new_url = f"{base_url}/hls/{i}/index.m3u8"
                extended.append((new_id, new_url))
                
        logging.info(f"已生成 {len(extended)} 个扩展地址")
        return extended

    @staticmethod
    def save_extensions(entries, filename):
        """保存扩展地址到文件"""
        try:
            with open(filename, "w") as f:
                for entry_id, url in entries:
                    f.write(f"{entry_id},{url}\n")
            logging.info(f"已保存 {len(entries)} 条扩展地址到 {filename}")
        except Exception as e:
            logging.error(f"保存扩展地址失败: {e}")

# ----------------- 第三步：测速验证扩展地址 -----------------
class SpeedValidator:
    @staticmethod
    def load_extensions(filename):
        """从文件加载扩展地址"""
        entries = []
        try:
            with open(filename, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(",", 1)
                        if len(parts) == 2:
                            entries.append((parts[0], parts[1]))
            logging.info(f"从 {filename} 加载 {len(entries)} 条扩展地址")
            return entries
        except Exception as e:
            logging.error(f"加载扩展地址失败: {e}")
            return []

    @staticmethod
    def check_speed(entry):
        """测试单个扩展地址的速度"""
        entry_id, url = entry
        try:
            start_time = time.time()
            total_size = 0
            
            # 设置连接超时2秒，总超时6秒
            with requests.get(url, stream=True, timeout=(2, 6)) as response:
                response.raise_for_status()
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        total_size += len(chunk)
                    if time.time() - start_time >= 6:
                        break
            
            elapsed_time = max(time.time() - start_time, 0.1)
            speed = (total_size / 1024) / elapsed_time  # 计算速度（KB/s）
            
            if speed >= 1.0:
                logging.info(f"有效地址: {entry_id} (速度: {speed:.2f} KB/s)")
                return (entry_id, url)
        except Exception as e:
            logging.debug(f"测速失败: {entry_id} ({str(e)})")
        return None

    @staticmethod
    def batch_validate(entries, workers=10):
        """批量验证扩展地址"""
        valid_entries = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(SpeedValidator.check_speed, entry) for entry in entries]
            for future in futures:
                if (result := future.result()):
                    valid_entries.append(result)
        logging.info(f"测速完成，共 {len(valid_entries)} 个有效扩展地址")
        return valid_entries

    @staticmethod
    def save_results(results, filename):
        """保存最终结果"""
        try:
            # 按数字顺序排序（1A1,1A2...2A1,2A2）
            sorted_results = sorted(
                results,
                key=lambda x: (
                    int(re.search(r"^\d+", x[0]).group()),
                    int(re.search(r"A(\d+)$", x[0]).group(1))
                )
            )
            
            with open(filename, "w") as f:
                for entry_id, url in sorted_results:
                    f.write(f"{entry_id},{url}\n")
            logging.info(f"已保存 {len(sorted_results)} 个有效地址到 {filename}")
        except Exception as e:
            logging.error(f"保存结果失败: {e}")

# ----------------- 主程序 -----------------
def main():
    # 配置文件路径
    source_url = "https://d.kstore.dev/download/10694/hlstvid.txt"
    base_output_file = "iptv.txt"
    extended_output_file = "ls.txt"
    final_output_file = "zszby.txt"

    # 第一步：下载并验证基础地址
    if (content := download_file(source_url)) is not None:
        raw_urls = list(set(extract_urls(content)))
        logging.info(f"发现 {len(raw_urls)} 个待验证地址")
        
        valid_urls = validate_urls(raw_urls)
        if valid_urls:
            save_urls_to_file(valid_urls, base_output_file)
        else:
            logging.warning("未找到有效地址")
            return

    # 第二步：生成并保存扩展地址
    source_entries = AddressExpander.read_source_file(base_output_file)
    extended_entries = AddressExpander.generate_extensions(source_entries)
    
    if not extended_entries:
        logging.error("未生成扩展地址")
        return
    
    AddressExpander.save_extensions(extended_entries, extended_output_file)

    # 第三步：加载并验证扩展地址
    loaded_entries = SpeedValidator.load_extensions(extended_output_file)
    if not loaded_entries:
        logging.error("未加载到扩展地址")
        return
    
    start_time = time.time()
    valid_results = SpeedValidator.batch_validate(loaded_entries)
    logging.info(f"测速完成，总耗时 {time.time()-start_time:.1f}秒")
    
    # 保存最终结果
    if valid_results:
        SpeedValidator.save_results(valid_results, final_output_file)
    else:
        logging.warning("未找到有效扩展地址")

if __name__ == "__main__":
    main()
