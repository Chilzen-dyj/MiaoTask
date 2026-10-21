"""Android app instances are a package AND a user, never a package alone."""
from dataclasses import asdict, dataclass
import re


@dataclass(frozen=True)
class AppInstance:
    package: str
    user_id: int | None
    label: str

    @property
    def id(self):
        return f'{self.package}@{self.user_id if self.user_id is not None else "native"}'

    def to_dict(self):
        return dict(asdict(self), id=self.id)


class InstanceMismatch(RuntimeError):
    """Do not send any more input to a different/unknown application instance."""
    kind = 'instance'
    evidence_saved = False


def parse_foreground(output):
    # Window focus is the visible surface, not any background activity record.
    patterns = (
        r'mCurrentFocus=Window\{[^\n]*?\bu(\d+)\s+([\w.]+)/([\w.$]+)',
        r'topResumedActivity=ActivityRecord\{[^\n]*?\bu(\d+)\s+([\w.]+)/([\w.$]+)',
        r'mResumedActivity[:=]\s*ActivityRecord\{[^\n]*?\bu(\d+)\s+([\w.]+)/([\w.$]+)',
    )
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            user_id, package, activity = match.groups()
            return dict(package=package, activity=activity, user_id=int(user_id))
    return None


def discover_android_instances(shell, profile=None):
    if profile is None:
        from backend.core.registry import default_registry
        profile = default_registry().default_app().profile
    result = shell(['pm', 'list', 'users'])
    if result.exit_code != 0:
        raise RuntimeError('无法读取应用用户空间，不能可靠区分应用分身')
    users = sorted({int(value) for value in re.findall(r'UserInfo\{(\d+):', result.output)})
    if not users:
        raise RuntimeError('未取得应用用户空间列表，请检查 USB 调试权限')
    instances, warnings = [], []
    for user in users:
        result = shell(['pm', 'list', 'packages', '--user', str(user), profile.package_for('uiautomator2')])
        if result.exit_code != 0 or re.search(r'SecurityException|Error:', result.output):
            warnings.append(f'用户空间 {user} 无法读取，未将其列为可执行实例')
            continue
        packages = sorted({p for p in re.findall(r'^package:(\S+)', result.output, re.M) if profile.matches(p)})
        for package in packages:
            label = profile.label + ' · 主应用（用户 0）' if user == 0 else f'{profile.label} · 分身 / 用户空间 {user}'
            if package != profile.package_for('uiautomator2'):
                label += f' · {package}'
            instances.append(AppInstance(package, user, label))
    return instances, warnings
