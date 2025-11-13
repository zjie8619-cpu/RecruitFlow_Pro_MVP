import os
import sys
import io

# 设置标准输出为 UTF-8 编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def fix_indentation(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                # 统一替换制表符为4个空格
                new_lines = [line.replace("\t", "    ") for line in lines]

                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                print(f"Fixed indentation in {filepath}")

if __name__ == "__main__":
    fix_indentation(".")
    print("\nAll indentation has been unified to 4 spaces!")

