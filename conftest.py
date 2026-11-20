"""把仓库根目录加入 sys.path，保证从任意 cwd 调用 pytest 都能 import anim。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
