import os

def main():
    # このスクリプトはルートディレクトリに置くことを想定
    root_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(root_dir, "src")
    
    # srcディレクトリ内を再帰的に探索して.pyファイルを見つける
    for dirpath, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                size = os.path.getsize(filepath)
                print(f"{filepath}: {size} bytes")

if __name__ == "__main__":
    main()
