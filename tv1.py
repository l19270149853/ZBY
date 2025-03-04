import requests
import re
import time
import concurrent.futures
from urllib.parse import urljoin, urlparse, urlunparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ======================
# 配置参数
# ======================
MAX_WORKERS = 10
SPEED_THRESHOLD = 0.5
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

class IPTVUpdater:
    def __init__(self):
        self.channels = []
        self.session = self._create_session()
        self.sources = [
            "https://d.kstore.dev/download/10694/zmtvid.txt",
            "https://raw.githubusercontent.com/iptv-org/iptv/master/scripts/sources.md"
        ]

    def _create_session(self):
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['GET']
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({'User-Agent': USER_AGENT})
        return session

    def _standardize_url(self, raw_url):
        try:
            if not raw_url.startswith(('http://', 'https://')):
                raw_url = f'http://{raw_url}'
            parsed = urlparse(raw_url)
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                '/iptv/live/1000.json',
                '',
                'key=txiptv',
                ''
            ))
        except Exception as e:
            print(f"URL标准化失败: {raw_url} - {str(e)}")
            return None

    def _fetch_sources(self):
        unique_urls = set()
        for source in self.sources:
            try:
                response = self.session.get(source, timeout=REQUEST_TIMEOUT)
                if response.ok:
                    matches = re.findall(
                        r"(?:https?://)?(?:[\w\-]+\.)+[\w\-]+(?::\d+)?/?", 
                        response.text
                    )
                    for url in matches:
                        std_url = self._standardize_url(url)
                        if std_url:
                            unique_urls.add(std_url)
            except Exception as e:
                print(f"源 {source} 获取失败: {str(e)}")
        return list(unique_urls)

    def _speed_test(self, url):
        try:
            start_time = time.time()
            with self.session.get(url, stream=True, timeout=(3, 6)) as response:
                response.raise_for_status()
                downloaded = 0
                for chunk in response.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    if time.time() - start_time > 8:
                        break
                duration = max(time.time() - start_time, 0.1)
                return (downloaded / 1024) / duration
        except Exception as e:
            print(f"测速失败 {url}: {str(e)}")
            return 0

    def _process_api(self, api_url):
        print(f"\n正在处理: {api_url}")
        try:
            response = self.session.get(api_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            try:
                data = response.json()
                if not isinstance(data.get('data'), list):
                    print(f"无效数据结构: {api_url}")
                    return
            except ValueError:
                print(f"JSON解析失败: {api_url}")
                return

            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = []
                for channel in data['data']:
                    if not all(k in channel for k in ('name', 'url')):
                        continue
                    try:
                        full_url = urljoin(api_url, channel['url'])
                        futures.append((
                            channel['name'],
                            full_url,
                            executor.submit(self._speed_test, full_url)
                        ))
                    except Exception as e:
                        print(f"URL拼接失败: {channel['url']} - {str(e)}")

                for name, url, future in futures:
                    try:
                        speed = future.result()
                        if speed > SPEED_THRESHOLD:
                            self.channels.append(f"{name},{url}")
                            print(f"✓ {name.ljust(15)} {speed:.2f} KB/s")
                        else:
                            print(f"× {name.ljust(15)} 速度不足 {speed:.2f} KB/s")
                    except Exception as e:
                        print(f"测速异常 {name}: {str(e)}")

        except requests.exceptions.RequestException as e:
            print(f"请求失败: {str(e)}")
        except Exception as e:
            print(f"处理异常: {str(e)}")

    def _save_channels(self):
        cctv = []
        satellite = []
        others = []
        cctv_pattern = re.compile(r"CCTV[\-\s]?(\d{1,2}\+?|4K|8K|HD)", re.I)
        satellite_pattern = re.compile(r"(.{2,4}卫视)台?")
        
        for line in set(self.channels):
            name, url = line.split(',', 1)
            if cctv_match := cctv_pattern.search(name):
                num = cctv_match.group(1)
                cctv.append(f"CCTV{num},{url}")
            elif sat_match := satellite_pattern.search(name):
                satellite.append(f"{sat_match.group(1)},{url}")
            else:
                others.append(line)
        
        def cctv_sort_key(item):
            nums = re.findall(r"\d+", item)
            return int(nums[0]) if nums else 999
        
        with open("zby.txt", "w", encoding="utf-8") as f:
            f.write(f"# 最后更新: {time.strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("央视频道,#genre#\n")
            f.write("\n".join(sorted(cctv, key=cctv_sort_key)) + "\n\n")
            f.write("卫视频道,#genre#\n")
            f.write("\n".join(sorted(set(satellite))) + "\n\n")
            f.write("其他频道,#genre#\n")
            f.write("\n".join(sorted(set(others))))

    def run(self):
        print("=== 开始获取源数据 ===")
        api_urls = self._fetch_sources()
        print(f"发现 {len(api_urls)} 个有效API端点")
        
        print("\n=== 开始处理API端点 ===")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(self._process_api, api_urls)
        
        print("\n=== 整理频道数据 ===")
        print(f"共收集到 {len(self.channels)} 个有效频道")
        self._save_channels()
        print("=== 更新完成 ===")

if __name__ == "__main__":
    updater = IPTVUpdater()
    updater.run()
