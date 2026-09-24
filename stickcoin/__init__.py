from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
