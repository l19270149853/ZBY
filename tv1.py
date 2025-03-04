import re
import time
import logging
import requests
import os
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


# 提取URL
def extract_urls(text):
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
    return pattern.findall(text)


# 验证视频加载速度
def check_video_speed(url, timeout=3, duration=3, min_speed=10):
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
        if elapsed_time == 0:  # 防止除零错误
            return None

        speed = (downloaded_size / 1024) / elapsed_time  # KB/s
        if speed >= min_speed:
            logging.info(f"有效地址: {url} (网速: {speed:.2f} KB/s)")
            return url.rstrip('/')  # 返回处理后的URL
        else:
            logging.warning(f"无效地址: {url} (网速: {speed:.2f} KB/s)")
    except requests.RequestException as e:
        logging.error(f"请求失败: {url} (错误: {e})")
    return None


# 提取基础URL
def extract_base_url(url):
    """
    从URL中提取基础URL（去掉路径部分）。
    例如：http://36.129.204.117:9003/hls/1/index.m3u8 -> http://36.129.204.117:9003
    """
    pattern = re.compile(r"(http://[^/]+)")
    match = pattern.match(url)
    if match:
        return match.group(1)
    return None


# 多线程验证URL
def validate_urls(urls, num_threads=10):
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        future_url_dict = {}
        for url in urls:
            future = executor.submit(check_video_speed, url)
            future_url_dict[future] = url

        for future in future_url_dict:
            result = future.result()
            if result:
                valid_urls.append(result)
            else:
                url = future_url_dict[future]
                base_url = extract_base_url(url)
                if base_url:
                    for i in range(1, 21):
                        new_url = f"{base_url}/hls/{i}/index.m3u8"
                        new_result = check_video_speed(new_url)
                        if new_result:
                            valid_urls.append(new_result)
                            break

    return valid_urls


# 保存有效URL到文件
def save_urls_to_file(urls, filename):
    with open(filename, "w") as file:
        for index, base_url in enumerate(urls, start=1):
            full_url = f"{base_url}/hls/1/index.m3u8"
            file.write(f"{index},{full_url}\n")
    logging.info(f"已保存 {len(urls)} 个有效地址到 {filename}")


# 处理每一行数据
def process_line(base_url):
    results = []
    base = "http://112.2.16.180:808"
    for i in range(1, 101):
        new_url = f"{base}/hls/{i}/index.m3u8"
        result = check_video_speed(new_url)
        if result:
            results.append(result)
    return results


# 主函数
def main():
    file_url = "https://d.kstore.dev/download/10694/hlstvid.txt"
    output_file = "tv1.txt"
    final_output_file = "tv2.txt"

    # 检查当前工作目录
    logging.info(f"当前工作目录: {os.getcwd()}")

    # 下载并处理文件
    if (content := download_file(file_url)) is not None:
        # 提取并去重URL
        raw_urls = list(set(extract_urls(content)))
        logging.info(f"发现 {len(raw_urls)} 个待验证地址")

        # 验证地址
        valid_urls = validate_urls(raw_urls)

        # 保存结果
        if valid_urls:
            save_urls_to_file(valid_urls, output_file)
        else:
            logging.warning("未找到有效地址")

    # 处理生成的新地址
    try:
        all_valid_urls = []
        with open(output_file, "r") as infile:
            for line in infile:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"(\d+),http://(.+?)/hls/\d+/index\.m3u8", line)
                if match:
                    base_url = match.group(2)
                    new_valid_urls = process_line(base_url)
                    all_valid_urls.extend(new_valid_urls)

        with open(final_output_file, "w") as outfile:
            for index, url in enumerate(all_valid_urls, start=1):
                outfile.write(f"{index},{url}\n")

        logging.info(f"处理完成，结果已保存到 {final_output_file}")
    except Exception as e:
        logging.error(f"处理文件时出错: {e}")


if __name__ == "__main__":
    main()

