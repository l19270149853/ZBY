import requests
import re

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
    pattern = re.compile(r'http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,4}')
    return pattern.findall(text)

# 替换并检测地址有效性
def check_and_replace_urls(base_url, new_urls):
    valid_urls = []
    for url in new_urls:
        new_full_url = base_url.replace("http://111.36.102.239:8089", url)
        try:
            response = requests.get(new_full_url, timeout=5)
            if response.status_code == 200:
                print(f"有效地址: {new_full_url}")
                valid_urls.append(new_full_url)
            else:
                print(f"无效地址: {new_full_url} (状态码: {response.status_code})")
        except requests.RequestException as e:
            print(f"请求失败: {new_full_url} (错误: {e})")
    return valid_urls

# 保存有效地址到文件，并添加序号
def save_urls_to_file(urls, filename):
    with open(filename, "w") as file:
        for index, url in enumerate(urls, start=1):  # 从 1 开始编号
            file.write(f"{index},{url}\n")
    print(f"有效地址已保存到 {filename}")

# 主函数
def main():
    file_url = "https://d.kstore.dev/download/10694/iptvID.txt"
    base_url = "http://111.36.102.239:8089/hls/1/index.m3u8"
    output_file = "iptv.txt"

    # 下载文件并提取地址
    file_content = download_file(file_url)
    if file_content:
        new_urls = extract_urls(file_content)
        valid_urls = check_and_replace_urls(base_url, new_urls)
        save_urls_to_file(valid_urls, output_file)

if __name__ == "__main__":
    main()
