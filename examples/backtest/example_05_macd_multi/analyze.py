"""
analyze.py
回测结果分析与可视化（可选）
"""
import collections

def analyze_results():
    # 假设run_example.py输出已重定向到result.txt
    rank_counter = collections.Counter()
    try:
        with open("result.txt", "r") as f:
            for line in f:
                if "Top" in line:
                    parts = line.strip().split(":")
                    if len(parts) > 2:
                        symbols = parts[-1].strip().strip("[]").replace("'", "").split(",")
                        for s in symbols:
                            s = s.strip()
                            if s:
                                rank_counter[s] += 1
        print("Top symbol appearance counts:")
        for symbol, count in rank_counter.most_common():
            print(f"{symbol}: {count}")
    except FileNotFoundError:
        print("result.txt not found. 请先运行run_example.py并将输出重定向到result.txt")

if __name__ == "__main__":
    analyze_results() 