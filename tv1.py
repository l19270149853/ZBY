import requests
import re
import time

def extract_base_urls(text):
    pattern = r'(http://[^/]+)'
    return list(set(match.group(1) for match in re.finditer(pattern, text)))

def test_url(url, total_duration=6, timeout=3, min_speed_kb=10):
    start = time.time()
    end_time = start + total_duration
    bytes_downloaded = 0
    speed = 0.0

    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1024):
                bytes_downloaded += len(chunk)
                if time.time() > end_time:
                    break
            
            duration = max(time.time() - start, 0.1)
            speed = (bytes_downloaded / duration) / 1024  # 转换为KB/s
            return speed >= min_speed_kb, round(speed, 2)
            
    except Exception as e:
        return False, 0.0

def main():
    try:
        text = requests.get("https://d.kstore.dev/download/10694/hlstvid.txt", timeout=10).text
        bases = extract_base_urls(text)
        targets = [f"{base}/hls/1/index.m3u8" for base in bases]
        
        valid = []
        for url in targets:
            print(f"测试 {url}", end="")
            valid_flag, speed = test_url(url)
            
            if valid_flag:
                valid.append(url)
                print(f" ✅ 有效 {speed}KB/s")
            else:
                if speed > 0:
                    print(f" ❌ 无效 {speed}KB/s")
                else:
                    print(" ❌ 超时/连接失败")
        
        with open("tv1.txt", "w") as f:
            f.write("\n".join(f"{i+1},{url}" for i, url in enumerate(valid)))
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__
