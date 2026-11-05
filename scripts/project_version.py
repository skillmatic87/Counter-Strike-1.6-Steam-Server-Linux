"""Read the package version from the repository or installed server VERSION file."""
from pathlib import Path
import re

_source = Path(__file__).resolve()
ROOT = _source.parents[2] if _source.parent.name == 'tools' else _source.parents[1]
VERSION = (ROOT / 'VERSION').read_text(encoding='ascii').strip()
if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', VERSION):
    raise ValueError('VERSION must contain a semantic version such as 0.1.0.')
