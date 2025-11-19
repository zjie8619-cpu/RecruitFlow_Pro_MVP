import uuid
import shutil
import datetime as dt
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_TRACKED_FILES = [
    "backend/configs/model_config.json",
    "data/templates/岗位配置示例.csv",
    "data/templates/题库示例.csv",
]


class VersionManager:
    def __init__(self, storage_dir: str = "backend/storage"):
        self.dir = Path(storage_dir)
        self.snap_dir = self.dir / "snapshots"
        self.snap_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self, files: Optional[Iterable[str]] = None) -> str:
        """
        Create a timestamped snapshot directory and copy the tracked files into it.
        Returns the snapshot tag.
        """
        tracked = list(files) if files else DEFAULT_TRACKED_FILES
        tag = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + str(uuid.uuid4())[:8]
        target = self.snap_dir / tag
        target.mkdir(parents=True, exist_ok=True)

        for rel_path in tracked:
            src = Path(rel_path)
            if not src.exists():
                continue
            shutil.copy(src, target / src.name)

        return tag
