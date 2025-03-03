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
    
    try:
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1024):
                bytes_downloaded += len(chunk)
                if time.time() > end_time:
                    break
                
            duration = max(time.time() - start, 0.1)
            return (bytes_downloaded / duration) >= min_speed_kb * 1024
    except:
        return False

def main():
    try:
        text = requests.get("https://d.kstore.dev/download/10694/hlstvid.txt", timeout=10).text
        bases = extract_base_urls(text)
        targets = [f"{base}/hls/1/index.m3u8" for base in bases]
        
        valid = []
        for url in targets:
            print(f"Testing {url}")
            if test_url(url):
                valid.append(url)
                print("✅ Valid")
            else:
                print("❌ Invalid")
        
        with open("tv1.txt", "w") as f:
            f.write("\n".join(f"{i+1},{url}" for i, url in enumerate(valid)))
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
