import requests
import re
import time

def extract_base_urls(text):
    """从文本中提取基础URL"""
    pattern = r'(http://[^/]+)'
    return list(set(match.group(1) for match in re.finditer(pattern, text)))

def test_url(url, total_duration=6, timeout=3, min_speed_kb=10):
    """测试URL的有效性和速度"""
    start_time = time.time()
    end_time = start_time + total_duration
    bytes_downloaded = 0
    speed = 0.0

    try:
        with requests.get(url, stream=True, timeout=(timeout, timeout)) as response:
            response.raise_for_status()
            
            # 流式下载数据
            for chunk in response.iter_content(chunk_size=1024):
                if time.time() > end_time:
                    break
                bytes_downloaded += len(chunk)
            
            # 计算实际下载时间
            duration = max(time.time() - start_time, 0.1)
            speed = (bytes_downloaded / duration) / 1024  # 转换为KB/s
            return speed >= min_speed_kb, round(speed, 2)
            
    except requests.exceptions.RequestException as e:
        return False, 0.0

def main():
    """主函数"""
    try:
        # 下载源文件
        source_url = "https://d.kstore.dev/download/10694/hlstvid.txt"
        response = requests.get(source_url, timeout=15)
        response.raise_for_status()
        text_content = response.text
        
        # 生成目标URL列表
        base_urls = extract_base_urls(text_content)
        target_urls = [f"{base}/hls/1/index.m3u8" for base in base_urls]
        
        valid_urls = []
        print(f"开始测试 {len(target_urls)} 个URL...")
        
        # 测试每个URL
        for index, url in enumerate(target_urls, 1):
            print(f"[{index}/{len(target_urls)}] 正在测试 {url.ljust(50)}", end="")
            is_valid, speed = test_url(url)
            
            if is_valid:
                valid_urls.append(url)
                print(f" ✅ 有效 | 速度: {speed}KB/s")
            else:
                status = f"速度不足 {speed}KB/s" if speed > 0 else "连接失败/超时"
                print(f" ❌ 无效 | {status}")
        
        # 保存结果
        with open("tv1.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(f"{idx},{url}" for idx, url in enumerate(valid_urls, 1)))
            
        print(f"\n测试完成，有效URL数量：{len(valid_urls)}")
        
    except Exception as e:
        print(f"\n发生错误: {str(e)}")

if __name__ == "__main__":  # 修正后的正确语法
    main()
