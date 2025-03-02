import re
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 下载文件内容
def download_file(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        return response.text
    except requests.RequestException as e:
        logging.error(f"下载文件失败: {e}")
        return None

# 匹配类似 http://59.32.97.183:9901 的地址
def extract_urls(text):
    pattern = re.compile(r'http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,4}')
    return pattern.findall(text)

# 验证视频加载速度
def check_video_speed(url, timeout=5, duration=5, min_speed=10):  # 将 min_speed 改为 10 KB/s
    try:
        start_time = time.time()
        response = requests.get(url, stream=True, timeout=timeout)
        downloaded_size = 0
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                downloaded_size += len(chunk)
                if time.time() - start_time >= duration:
                    break
        elapsed_time = time.time() - start_time
        speed = (downloaded_size / 1024) / elapsed_time  # 计算网速（KB/s）
        if speed >= min_speed:
            logging.info(f"有效地址: {url} (网速: {speed:.2f} KB/s)")
            return url
        else:
            logging.warning(f"无效地址: {url} (网速: {speed:.2f} KB/s)")
    except requests.RequestException as e:
        logging.error(f"请求失败: {url} (错误: {e})")
    return None

# 多线程验证地址
def validate_urls(urls, num_threads=10):
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = executor.map(check_video_speed, urls)
        for result in results:
            if result:
                valid_urls.append(result)
    return valid_urls

# 保存有效地址到文件，并添加序号
def save_urls_to_file(urls, filename):
    with open(filename, "w") as file:
        for index, url in enumerate(urls, start=1):  # 从 1 开始编号
            file.write(f"{index},{url}\n")  # 修改为序号,URL 的格式
    logging.info(f"有效地址已保存到 {filename}")

# 主函数
def main():
    file_url = "https://d.kstore.dev/download/10694/1iptvid.txt"
    output_file = "iptv.txt"

    # 下载文件并提取地址
    file_content = download_file(file_url)
    if file_content:
        urls = extract_urls(file_content)
        valid_urls = validate_urls(urls)
        save_urls_to_file(valid_urls, output_file)

if __name__ == "__main__":
    main()
