import uuid, shutil, datetime as dt
from pathlib import Path

class VersionManager:
    def __init__(self, storage_dir: str = "backend/storage"):
        self.dir = Path(storage_dir)
        self.snap_dir = self.dir / "snapshots"
        self.snap_dir.mkdir(parents=True, exist_ok=True)

    def snapshot(self) -> str:
        tag = dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + str(uuid.uuid4())[:8]
        target = self.snap_dir / tag
        target.mkdir(parents=True, exist_ok=True)
        for p in ["backend/configs/model_config.json","data/templates/岗位配置示例.csv","data/templates/题库示例.csv"]:
            if Path(p).exists():
                shutil.copy(p, target / Path(p).name)
        return tag

