import requests
import re
import time
import threading
from queue import Queue

# 下载文件内容
def download_file(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # 检查请求是否成功
        return response.text
    except requests.RequestException as e:
        print(f"下载文件失败: {e}")
        return None

# 匹配类似 http://59.32.97.183:9901 的地址
def extract_urls(text):
    pattern = re.compile(r'http://(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9]):\d{1,4}')
    matches = pattern.findall(text)
    # 将元组转换为字符串
    return [f"http://{'.'.join(match)}:9901" for match in matches]

# 下载视频文件并验证网速
def download_video_and_check_speed(url, timeout=2, duration=5, min_speed=100):
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
            print(f"有效地址: {url} (网速: {speed:.2f} KB/s)")
            return url
        else:
            print(f"无效地址: {url} (网速: {speed:.2f} KB/s)")
    except requests.RequestException as e:
        print(f"请求失败: {url} (错误: {e})")
    return None

# 多线程验证地址
def validate_urls(base_url, new_urls, num_threads=10):
    valid_urls = []
    queue = Queue()
    results = Queue()

    # 将任务放入队列
    for url in new_urls:
        new_full_url = base_url.replace("http://111.36.102.239:8089", url)
        queue.put(new_full_url)

    # 工作线程函数
    def worker():
        while not queue.empty():
            url = queue.get()
            result = download_video_and_check_speed(url)
            if result:
                results.put(result)
            queue.task_done()

    # 启动线程
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    # 等待所有任务完成
    queue.join()

    # 获取结果
    while not results.empty():
        valid_urls.append(results.get())

    return valid_urls

# 保存有效地址到文件，并添加序号
def save_urls_to_file(urls, filename):
    with open(filename, "w") as file:
        for index, url in enumerate(urls, start=1):  # 从 1 开始编号
            file.write(f"{index}\t{url}\n")
    print(f"有效地址已保存到 {filename}")

# 主函数
def main():
    file_url = "https://d.kstore.dev/download/10694/1iptvid.txt"
    base_url = "http://111.36.102.239:8089/hls/1/index.m3u8"
    output_file = "iptv.txt"

    # 下载文件并提取地址
    file_content = download_file(file_url)
    if file_content:
        new_urls = extract_urls(file_content)
        valid_urls = validate_urls(base_url, new_urls)
        save_urls_to_file(valid_urls, output_file)

if __name__ == "__main__":
    main()
