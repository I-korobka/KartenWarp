import os
import subprocess
import sys

def run_command(command):
    print("Running:", " ".join(command))
    result = subprocess.run(command, shell=False)
    if result.returncode != 0:
        sys.exit(result.returncode)

def compile_mo_files():
    locale_dir = "locale"
    for lang in os.listdir(locale_dir):
        lang_dir = os.path.join(locale_dir, lang, "LC_MESSAGES")
        if os.path.isdir(lang_dir):
            po_file = os.path.join(lang_dir, "messages.po")
            mo_file = os.path.join(lang_dir, "messages.mo")
            print(f"Compiling MO file for {lang}")
            command = ["msgfmt", po_file, "-o", mo_file]
            run_command(command)
            print(f"MO file generated: {mo_file}")

if __name__ == "__main__":
    compile_mo_files()
    print("MO files compiled successfully.")
