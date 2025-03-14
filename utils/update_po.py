import os
import subprocess
import sys

def run_command(command):
    print("Running:", " ".join(command))
    env = os.environ.copy()
    env["LANG"] = "en_US.UTF-8"  # ここで環境変数を指定
    result = subprocess.run(command, shell=False, stdin=subprocess.DEVNULL, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)

def generate_file_list(file_list_path="file_list.txt"):
    files = []
    for root, dirs, filenames in os.walk("."):
        for file in filenames:
            if file.endswith(".py"):
                full_path = os.path.join(root, file).replace("\\", "/")
                files.append(full_path)
    with open(file_list_path, "w", encoding="utf-8") as f:
        for path in files:
            f.write(path + "\n")
    print(f"Generated file list with {len(files)} entries.")

def generate_pot():
    generate_file_list("file_list.txt")
    command = [
        "xgettext",
        "--language=Python",
        "--from-code=UTF-8",  # 追加
        "--keyword=_",
        "--output=locale/messages.pot",
        "-f", "file_list.txt"
    ]
    run_command(command)
    print("POT file generated at locale/messages.pot")

def update_po_files():
    locale_dir = "locale"
    pot_file = os.path.join(locale_dir, "messages.pot")
    for lang in os.listdir(locale_dir):
        lang_dir = os.path.join(locale_dir, lang, "LC_MESSAGES")
        if os.path.isdir(lang_dir):
            po_file = os.path.join(lang_dir, "messages.po")
            if os.path.exists(po_file):
                print(f"Updating PO file for {lang}")
                command = ["msgmerge", "--update", po_file, pot_file]
                run_command(command)
            else:
                print(f"Creating new PO file for {lang}")
                with open(pot_file, "r", encoding="utf-8") as src, open(po_file, "w", encoding="utf-8") as dst:
                    dst.write(src.read())

if __name__ == "__main__":
    generate_pot()
    update_po_files()
    print("PO files updated successfully.")
