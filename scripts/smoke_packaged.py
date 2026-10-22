"""Verify an exe with Python/ADB removed from PATH, without touching a phone."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen


def smoke(executable, output=None):
    executable = Path(executable).resolve()
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    result = {'exe': executable.name}
    with tempfile.TemporaryDirectory(prefix='miao-package-check-') as work:
        folder = Path(work)
        env = os.environ.copy()
        windows = env.get('SystemRoot', r'C:\Windows')
        env['PATH'] = os.pathsep.join([str(Path(windows) / 'System32'), windows])
        env['MIAO_DATA_DIR'] = str(folder / 'data')
        for key in ('PYTHONPATH', 'PYTHONHOME', 'ADBUTILS_ADB_PATH'):
            env.pop(key, None)
        report = folder / 'self-test.json'
        self_check = subprocess.run([str(executable), '--self-test', '--output', str(report)], cwd=work,
                                    env=env, creationflags=flags, timeout=120)
        if self_check.returncode:
            details = report.read_text(encoding='utf-8') if report.exists() else 'No self-test report was written'
            raise RuntimeError(f'Packaged self-test failed ({self_check.returncode}): {details}')
        result['offline'] = json.loads(report.read_text(encoding='utf-8'))
        if not result['offline']['ok'] or not result['offline']['frozen']:
            raise RuntimeError(f'Packaged self-test failed: {result}')
        port_file = folder / 'port.json'
        process = subprocess.Popen([str(executable), '--no-browser', '--port', '0', '--port-file', str(port_file)],
                                   cwd=work, env=env, creationflags=flags)
        try:
            deadline = time.monotonic() + 30
            while not port_file.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('The packaged web service did not start')
                time.sleep(.2)
            base = json.loads(port_file.read_text(encoding='utf-8'))['url']
            with urlopen(base + '/api/health', timeout=5) as response:
                result['health'] = json.load(response)
            for name, expected in [('/', '双11'), ('/app.js', 'browse_extra_seconds'), ('/style.css', '.topbar')]:
                with urlopen(base + name, timeout=5) as response:
                    if expected not in response.read().decode('utf-8'):
                        raise RuntimeError(f'Unexpected packaged response: {name}')
            with urlopen(base + '/api/state', timeout=5) as response:
                state = json.load(response)
            with urlopen(base + '/api/apps', timeout=5) as response:
                catalog = json.load(response)['apps']
            if state.get('catalog') != catalog:
                raise RuntimeError('Panel catalog does not match the registry API')
            result['activity_catalog'] = True
            for asset in ('/assets/miaotask-32.png', '/assets/miaotask-128.png', '/favicon.ico'):
                with urlopen(base + asset, timeout=5) as response:
                    expected = b'\x00\x00\x01\x00' if asset.endswith('.ico') else b'\x89PNG\r\n\x1a\n'
                    if not response.read().startswith(expected):
                        raise RuntimeError(f'Packaged icon missing or invalid: {asset}')
            result['brand_icons'] = True
            if state['connected']:
                raise RuntimeError('Package should not connect to a device automatically')
            if state.get('version') != result['health']['version']:
                raise RuntimeError('Panel version does not match the running executable')
            # Include real browser security headers, not just a headerless CLI POST.
            request = Request(base + '/api/configure', data=b'{}', method='POST', headers={
                'Content-Type': 'application/json', 'X-Miao-Token': state['token'],
                'Origin': base, 'Sec-Fetch-Site': 'same-origin'})
            with urlopen(request, timeout=5) as response:
                result['browser_headers_post'] = response.status == 202
            def post(path, payload):
                request = Request(base+path, data=json.dumps(payload).encode(), headers={
                    'Content-Type':'application/json','X-Miao-Token':state['token'],
                    'Origin':base,'Sec-Fetch-Site':'same-origin'})
                with urlopen(request,timeout=5) as response:
                    return json.load(response)
            added=post('/api/workspaces',{'label':'offline check'})['id']
            post('/api/configure?device='+added,{'config':{'max_tasks':3}})
            with urlopen(base+'/api/state?device='+added,timeout=5) as response:
                child=json.load(response)
            with urlopen(base+'/api/state',timeout=5) as response:
                original=json.load(response)
            if child['config']['max_tasks']!=3 or original['config']['max_tasks']!=state['config']['max_tasks']:
                raise RuntimeError('Packaged workspaces do not isolate configuration')
            post('/api/workspaces/remove',{'id':added})
            for path in ['/js/components/device-manager.js','/js/components/wifi-connect.js']:
                with urlopen(base+path,timeout=5) as response:
                    if not response.read():
                        raise RuntimeError('Packaged frontend component missing: '+path)
            result['multi_device_isolation']=True
            # Launching twice should reuse the existing service.
            port = base.rsplit(':', 1)[1]
            subprocess.run([str(executable), '--no-browser', '--port', port], cwd=work, env=env,
                           creationflags=flags, check=True, timeout=20)
            result['second_launch_reuses_service'] = True
            request = Request(base + '/api/shutdown', data=b'{}', method='POST',
                              headers={'Content-Type': 'application/json', 'X-Miao-Token': state['token']})
            with urlopen(request, timeout=5) as response:
                result['shutdown'] = response.status == 202
            process.wait(timeout=10)
            if process.returncode != 0:
                raise RuntimeError(f'Unexpected exit code: {process.returncode}')
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    result['ok'] = True
    if output:
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('exe')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(smoke(args.exe, args.output), ensure_ascii=False, indent=2))
