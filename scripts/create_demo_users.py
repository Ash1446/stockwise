r"""Creates the two accounts with passwords you type (nothing is stored in this file)."""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("change_passwords.py")), run_name="__main__")