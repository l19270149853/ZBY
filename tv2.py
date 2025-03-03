import re

def process_line(line):
    """
    处理每一行数据，生成 150 个新地址
    """
    # 提取原始行信息
    match = re.match(r"(\d+),http://(.+?)/hls/\d+/index\.m3u8", line)
    if not match:
        return None

    index, base_url = match.groups()
    results = []

    # 生成 150 个新地址
    for i in range(1, 151):
        new_index = f"{index}A{i}"
        new_url = f"http://{base_url}/hls/{i}/index.m3u8"
        results.append(f"{new_index},{new_url}")

    return results

def main():
    input_file = "tv1.txt"
    output_file = "tv2.txt"

    try:
        with open(input_file, "r") as infile, open(output_file, "w") as outfile:
            for line in infile:
                line = line.strip()
                if not line:
                    continue

                # 处理每一行
                processed_lines = process_line(line)
                if processed_lines:
                    for processed_line in processed_lines:
                        outfile.write(processed_line + "\n")

        print(f"处理完成，结果已保存到 {output_file}")
    except Exception as e:
        print(f"处理文件时出错: {e}")

if __name__ == "__main__":
    main()
