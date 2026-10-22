"""Application identity policy, injected into the driver and session."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ApplicationProfile:
    label: str
    android_package: str
    package_pattern: str
    native_package: str = ''
    legacy_primary_instances: tuple = ()

    def matches(self, package):
        return isinstance(package, str) and (bool(self.native_package and package == self.native_package)
                                             or bool(re.fullmatch(self.package_pattern, package)))

    def package_for(self, driver):
        package = self.native_package if driver == 'hmdriver2' else self.android_package
        if not package:
            raise ValueError('此应用未声明当前设备驱动的包名')
        return package
