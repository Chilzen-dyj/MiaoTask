"""Activity-scoped storage with explicit, non-destructive legacy adoption."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from backend.core.registry import checked_id


def legacy_folder(root, day, device_key, instance_id='', primary_instances=()):
    folder = Path(root) / 'daily' / day / device_key
    if instance_id and instance_id not in primary_instances:
        folder /= 'instances/' + hashlib.sha256(instance_id.encode()).hexdigest()[:16]
    return folder


@dataclass(frozen=True)
class StorageNamespace:
    app: str
    activity: str
    legacy: bool = False
    primary_instances: tuple = ()

    def __post_init__(self):
        checked_id(self.app)
        checked_id(self.activity)

    def folder(self, root, day, device_key, instance_id):
        instance_key = hashlib.sha256((instance_id or 'default').encode()).hexdigest()[:16]
        return Path(root) / 'apps' / self.app / 'activities' / self.activity / 'daily' / day / device_key / 'instances' / instance_key

    def adopt_legacy(self, root, day, device_key, instance_id):
        destination = self.folder(root, day, device_key, instance_id)
        source = legacy_folder(root, day, device_key, instance_id, self.primary_instances)
        if not self.legacy or destination.exists() or not (source / 'state.json').is_file():
            return
        try:
            loaded = json.loads((source / 'state.json').read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            loaded = None  # DailyState retains its normal corrupt-file recovery.
        if isinstance(loaded, dict):
            if loaded.get('device_key') != device_key or loaded.get('date') != day:
                raise ValueError('旧记录不属于当前设备或日期')
            recorded = loaded.get('instance_id', '')
            if recorded != instance_id and not (not recorded and instance_id in self.primary_instances):
                raise ValueError('旧记录不属于当前应用实例')
            if loaded.get('app_id') not in (None, '', self.app) or loaded.get('activity_id') not in (None, '', self.activity):
                raise ValueError('旧记录不属于当前活动')
            loaded.update(app_id=self.app, activity_id=self.activity)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.migrating-' + uuid.uuid4().hex)
        temporary.mkdir()
        try:
            for name in ('state.json', 'events.jsonl'):
                path = source / name
                if path.is_file() and not path.is_symlink():
                    shutil.copy2(path, temporary / name)
            if isinstance(loaded, dict):
                (temporary / 'state.json').write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding='utf-8')
            failures = temporary / 'failures'
            failures.mkdir()
            if (source / 'failures').is_dir():
                for path in (source / 'failures').iterdir():
                    if path.is_file() and not path.is_symlink() and path.suffix in ('.json', '.png'):
                        shutil.copy2(path, failures / path.name)
            os.replace(temporary, destination)
        finally:
            # Only files created above, inside this exact temporary directory.
            if temporary.exists():
                for path in (temporary / 'failures').glob('*'):
                    path.unlink()
                if (temporary / 'failures').exists():
                    (temporary / 'failures').rmdir()
                for path in temporary.iterdir():
                    path.unlink()
                temporary.rmdir()
