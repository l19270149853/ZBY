import re
import time
import logging
import requests  # 导入 requests 库
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from concurrent.futures import ThreadPoolExecutor  # 导入线程池

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 初始化 Chrome WebDriver
def init_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式，不打开浏览器窗口
    chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    chrome_options.add_argument("--no-sandbox")  # 禁用沙盒模式
    chrome_options.add_argument("--disable-dev-shm-usage")  # 解决内存不足问题
    service = Service(executable_path="/path/to/chromedriver")  # 替换为您的 ChromeDriver 路径
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(5)  # 设置页面加载超时为 5 秒
    return driver

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

# 使用 Chrome WebDriver 验证视频加载速度
def check_video_speed_with_webdriver(url, timeout=5):
    driver = None
    try:
        driver = init_chrome_driver()
        start_time = time.time()
        driver.get(url)  # 打开视频 URL
        end_time = time.time()
        load_time = end_time - start_time
        logging.info(f"视频加载成功: {url} (加载时间: {load_time:.2f} 秒)")
        return url, load_time
    except TimeoutException:
        logging.warning(f"视频加载超时: {url} (超过 {timeout} 秒)")
    except WebDriverException as e:
        logging.error(f"WebDriver 错误: {url} (错误: {e})")
    finally:
        if driver:
            driver.quit()  # 关闭浏览器
    return None, None

# 多线程验证地址
def validate_urls(urls, num_threads=5):
    valid_urls = []
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = executor.map(check_video_speed_with_webdriver, urls)
        for result in results:
            url, load_time = result
            if url and load_time:
                valid_urls.append(url)
    return valid_urls

# 保存有效地址到文件，并添加序号
def save_urls_to_file(urls, filename):
    with open(filename, "w") as file:
        for index, url in enumerate(urls, start=1):  # 从 1 开始编号
            file.write(f"{index}\t{url}\n")
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
