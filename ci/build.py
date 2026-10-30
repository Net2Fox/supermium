#!/usr/bin/env python3
"""Staged Windows build of Supermium for GitHub Actions.

Each GitHub-hosted runner job may run for at most 6 hours, which is not enough
to build Chromium on 4 cores. This script does as much as it can before a
deadline and leaves the tree in a state that the workflow packs into an
artifact, so that the next job can continue where this one stopped.

Layout below --root:
  depot_tools/   depot_tools at the revision pinned by Chromium's DEPS
  src/           Chromium 150.0.7871.287 with the Supermium patches applied
  applied/       copies of the patch files that are applied to src/
  state.json     which of the one-time steps are done
  logs/          ninja output and the errors of the current stage
  dist/          the packaged browser, once the build is finished

Exit codes:
  0    the browser is built and packaged in dist/
  124  the deadline was reached; save the tree and continue in the next stage
  125  there were build errors; the tree is still worth saving, so that a
       later run can continue from it after the patches are fixed
  other: a fatal error; the tree is not worth saving
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path

CHROMIUM_VERSION = '150.0.7871.287'
# chromium/src DEPS at CHROMIUM_VERSION pins depot_tools to this revision.
DEPOT_TOOLS_COMMIT = 'f4fadaf6a5ba1bced9d3d9021060667b563bf583'

REPO = Path(__file__).resolve().parent.parent

# The order matters: several files are changed by more than one patch.
SRC_PATCHES = [
    'supermium_150_core_encrypt_mojo.patch',
    'supermium_150_core_mem.patch',
    'supermium_150_core_sandbox.patch',
    'ui_part_1.patch',
    'ui_part_2.patch',
    'general_features.patch',
    '150_about_flags_and_finishing_touches.patch',
    'client_hints.patch',
    'ungoogled_supermium_and_mv2.patch',
    'misc_changes_20261002.patch',
    'time_ticks_patch.diff',
    'waveinput_output_restore.patch',
    'win7_notification_bug_and_improved_pwa_install_prompt_block.patch',
    'xp_tts_fix.patch',
    'ptr_device_fix.patch',
    'quic_fix.patch',
    'touch_device_support_win7.patch',
]
# Patches for the separate repositories that DEPS checks out below src/.
SUBREPO_PATCHES = [
    ('third_party/pdfium', 'pdfium_fix.patch'),
    ('third_party/search_engines_data/resources', 'search_engines_data.patch'),
]

GCLIENT_CONFIG = """\
solutions = [
  {
    "name": "src",
    "url": "https://chromium.googlesource.com/chromium/src.git",
    "managed": False,
    "custom_deps": {
      "src/third_party/angle/third_party/VK-GL-CTS/src": None,
    },
    "custom_vars": {
      "checkout_configuration": "small",
      "checkout_pgo_profiles": %(pgo)s,
      "generate_location_tags": False,
    },
  },
]
target_os = ["win"]
target_os_only = True
target_cpu = ["x64"]
target_cpu_only = True
"""

OUT_DIR = 'out/Release'
NINJA_TARGETS = ['chrome', 'mini_installer']
TIMEOUT_EXIT = 124
BUILD_ERRORS_EXIT = 125
STATUS_LINE = re.compile(r'^\[\d+/\d+\] ')


class DeadlineReached(Exception):
    pass


def log(msg):
    print('[build.py %s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


def group(title):
    print('::group::' + title, flush=True)


def endgroup():
    print('::endgroup::', flush=True)


def log_disk(root):
    usage = shutil.disk_usage(root)
    log('disk: %.1f GB free of %.1f GB' % (usage.free / 2**30, usage.total / 2**30))


def setup_environment(root):
    depot_tools = root / 'depot_tools'
    os.environ['PATH'] = str(depot_tools) + os.pathsep + os.environ['PATH']
    # Use the locally installed Visual Studio 2022 and Windows SDK instead of
    # Google's internal toolchain package.
    os.environ['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
    os.environ['DEPOT_TOOLS_UPDATE'] = '0'
    os.environ['DEPOT_TOOLS_METRICS'] = '0'
    os.environ['GCLIENT_SUPPRESS_GIT_VERSION_WARNING'] = '1'
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'


def run(cmd, cwd=None, check=True, **kwargs):
    cmd = [str(c) for c in cmd]
    log('$ ' + ' '.join(cmd) + ('   (in %s)' % cwd if cwd else ''))
    if cmd[0].lower().endswith('.bat'):
        cmd = ['cmd.exe', '/c'] + cmd
    return subprocess.run(cmd, cwd=cwd, check=check, **kwargs)


def load_state(root):
    path = root / 'state.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {}


def save_state(root, state):
    (root / 'state.json').write_text(json.dumps(state, indent=1), encoding='utf-8')


def remove_tree(path):
    def onerror(func, p, _):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerror)


def sync(root, pgo):
    group('Fetch Chromium %s' % CHROMIUM_VERSION)
    depot_tools = root / 'depot_tools'
    if not (depot_tools / 'gclient.py').exists():
        depot_tools.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', '-q'], cwd=depot_tools)
        run(['git', 'remote', 'add', 'origin',
             'https://chromium.googlesource.com/chromium/tools/depot_tools.git'],
            cwd=depot_tools)
        run(['git', 'fetch', '-q', '--depth=1', 'origin', DEPOT_TOOLS_COMMIT],
            cwd=depot_tools)
        run(['git', 'checkout', '-q', 'FETCH_HEAD'], cwd=depot_tools)
    # depot_tools runs git through git.bat, which only its full bootstrap
    # creates. Point it at the runner's git, in the form that depot_tools'
    # git_common.py parses (an absolute path to git.exe on the last line).
    git = os.path.splitext(shutil.which('git'))[0] + '.exe'
    (depot_tools / 'git.bat').write_text('@echo off\n"%s" %%*\n' % git,
                                         encoding='utf-8')
    # Bootstraps depot_tools' own Python and other tools.
    run([depot_tools / 'gclient.bat', '--version'], cwd=root)

    src = root / 'src'
    if not (src / 'BUILD.gn').exists():
        # Two commits, since LASTCHANGE and gpu_lists_version.h need a parent.
        run(['git', 'clone', '-q', '-c', 'advice.detachedHead=false',
             '--depth=2', '-b', CHROMIUM_VERSION,
             'https://chromium.googlesource.com/chromium/src.git', src])
    (root / '.gclient').write_text(
        GCLIENT_CONFIG % {'pgo': 'True' if pgo else 'False'}, encoding='utf-8')
    run([depot_tools / 'gclient.bat', 'sync', '--no-history', '-D', '--force',
         '--reset', '-j', '8'], cwd=root)
    log_disk(root)
    endgroup()


def strip_git_dirs(root):
    """Removes the git metadata, which the build does not need, to keep the
    state artifact small. The hooks already generated LASTCHANGE & co."""
    group('Remove .git directories')
    removed = 0
    for top in (root / 'src',):
        for dirpath, dirnames, _ in os.walk(top):
            if '.git' in dirnames:
                remove_tree(Path(dirpath) / '.git')
                dirnames.remove('.git')
                removed += 1
    log('removed %d .git directories' % removed)
    log_disk(root)
    endgroup()


def patch_dirs(root):
    """Yields (patch file name, directory to apply it in), in order."""
    for name in SRC_PATCHES:
        yield name, root / 'src'
    for subdir, name in SUBREPO_PATCHES:
        yield name, root / 'src' / subdir


def git_apply(patch, cwd, reverse=False):
    cmd = ['git', 'apply', '--whitespace=nowarn']
    if reverse:
        cmd.append('-R')
    # Outside of a git repository, git apply works like patch(1).
    run(cmd + [patch], cwd=cwd)


def apply_patches(root):
    group('Apply the Supermium patches')
    applied = root / 'applied'
    applied.mkdir(exist_ok=True)
    for name, cwd in patch_dirs(root):
        git_apply(REPO / name, cwd)
        shutil.copyfile(REPO / name, applied / name)
    endgroup()


def files_in_patch(patch):
    paths = set()
    for line in patch.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('+++ b/') or line.startswith('--- a/'):
            paths.add(line[6:].strip())
    return paths


def file_digest(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def reapply_changed_patches(root):
    """Replaces the patches applied to a tree from an earlier run with the
    current ones. Files whose content ends up unchanged keep their old
    modification time, so ninja only rebuilds what really changed."""
    applied = root / 'applied'
    changed = [name for name, _ in patch_dirs(root)
               if not (applied / name).exists()
               or (applied / name).read_bytes() != (REPO / name).read_bytes()]
    if not changed:
        return False
    group('Replace the applied patches (changed: %s)' % ', '.join(changed))
    touched = set()
    for name, cwd in patch_dirs(root):
        for patch in (applied / name, REPO / name):
            if patch.exists():
                touched.update(cwd / p for p in files_in_patch(patch))
    before = {}
    for path in touched:
        if path.is_file():
            st = path.stat()
            before[path] = (file_digest(path), st.st_atime_ns, st.st_mtime_ns)
    for name, cwd in reversed(list(patch_dirs(root))):
        if (applied / name).exists():
            git_apply(applied / name, cwd, reverse=True)
    for name, cwd in patch_dirs(root):
        git_apply(REPO / name, cwd)
        shutil.copyfile(REPO / name, applied / name)
    kept = 0
    for path, (digest, atime, mtime) in before.items():
        if path.is_file() and file_digest(path) == digest:
            os.utime(path, ns=(atime, mtime))
            kept += 1
    log('%d of %d touched files are unchanged and keep their timestamps' %
        (kept, len(touched)))
    endgroup()
    return True


def write_args(root, official):
    args = (REPO / 'ci' / 'args.gn').read_text(encoding='utf-8')
    if official:
        args += '\nis_official_build = true\nchrome_pgo_phase = 2\n'
    else:
        args += '\nis_official_build = false\n'
    out = root / 'src' / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'args.gn'
    if not path.exists() or path.read_text(encoding='utf-8') != args:
        path.write_text(args, encoding='utf-8')


def gn_gen(root):
    group('gn gen')
    src = root / 'src'
    run([src / 'buildtools' / 'win' / 'gn.exe', 'gen', OUT_DIR], cwd=src)
    endgroup()


def compiled_patched_sources(root):
    """Returns the patched C++ sources that the Windows build compiles, as
    ninja paths relative to the output directory."""
    candidates = set()
    for name in SRC_PATCHES:
        for path in files_in_patch(REPO / name):
            if path.endswith(('.cc', '.cpp', '.c')):
                candidates.add('../../' + path)
    referenced = set()
    pattern = re.compile(r'\.\./\.\./[^\s|:$]+\.(?:cc|cpp|c)\b')
    out = root / 'src' / OUT_DIR
    for ninja_file in out.rglob('*.ninja'):
        text = ninja_file.read_text(encoding='utf-8', errors='replace')
        referenced.update(m for m in pattern.findall(text) if m in candidates)
    return sorted(referenced)


def run_ninja(root, targets, deadline, jobs, label):
    """Runs ninja with -k 0, so that one run reports all errors. Prints the
    output of failed steps and a progress line now and then."""
    src = root / 'src'
    logs = root / 'logs'
    logs.mkdir(exist_ok=True)
    full_log = logs / ('ninja-%s.log' % label)
    errors_log = logs / 'errors.txt'
    ninja = src / 'third_party' / 'ninja' / 'ninja.exe'
    cmd = [str(ninja), '-C', OUT_DIR, '-k', '0', '-j', str(jobs)] + targets
    log('$ ' + ' '.join(cmd))
    proc = subprocess.Popen(cmd, cwd=src, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True,
                            encoding='utf-8', errors='replace', bufsize=1)
    failed_steps = 0
    capturing = False
    last_progress = 0.0
    timed_out = False

    def killer():
        nonlocal timed_out
        while proc.poll() is None:
            if time.time() >= deadline:
                timed_out = True
                log('deadline reached, stopping ninja')
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            time.sleep(10)

    threading.Thread(target=killer, daemon=True).start()
    with full_log.open('a', encoding='utf-8') as full, \
            errors_log.open('a', encoding='utf-8') as errors:
        for line in proc.stdout:
            full.write(line)
            if STATUS_LINE.match(line):
                capturing = False
                if time.time() - last_progress > 120:
                    last_progress = time.time()
                    print(line.rstrip()[:200], flush=True)
                continue
            if line.startswith('FAILED: '):
                capturing = True
                if timed_out:
                    # A step that the deadline killed, not a build error.
                    print('(stopped at the deadline) ' + line.rstrip(), flush=True)
                    continue
                failed_steps += 1
                print('::error::' + line.rstrip(), flush=True)
            if capturing or line.startswith('ninja: '):
                print(line.rstrip(), flush=True)
                if not timed_out:
                    errors.write(line)
    proc.wait()
    if timed_out:
        # Give killed compilers a moment to release their files.
        time.sleep(15)
    log('ninja exited with %s, %d failed steps' % (proc.returncode, failed_steps))
    return proc.returncode, failed_steps, timed_out


def package(root):
    group('Package')
    src = root / 'src'
    out = src / OUT_DIR
    dist = root / 'dist'
    if dist.exists():
        remove_tree(dist)
    dist.mkdir()
    base = 'supermium_%s_win64' % CHROMIUM_VERSION
    shutil.copyfile(out / 'mini_installer.exe', dist / (base + '_installer.exe'))

    exec_globals = {'__builtins__': None}
    exec((src / 'chrome' / 'tools' / 'build' / 'win' / 'FILES.cfg').read_text(
        encoding='utf-8'), exec_globals)
    excluded = {'mini_installer.exe', 'mini_installer_exe_version.rc', 'setup.exe',
                'chrome.packed.7z'}
    files = set()
    for spec in exec_globals['FILES']:
        if 'official' not in spec['buildtype']:
            continue
        if 'arch' in spec and '64bit' not in spec['arch']:
            continue
        for path in out.glob(spec['filename']):
            rel = path.relative_to(out)
            if path.suffix.lower() == '.pdb' or str(rel) in excluded:
                continue
            if path.is_dir():
                files.update(p for p in path.rglob('*') if p.is_file())
            else:
                files.add(path)
    with zipfile.ZipFile(dist / (base + '.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, Path('Supermium') / path.relative_to(out))
    log('packaged %d files' % len(files))
    for path in dist.iterdir():
        log('%s: %.1f MB' % (path.name, path.stat().st_size / 2**20))
    endgroup()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--deadline', type=float, required=True,
                        help='Unix time at which ninja has to be stopped')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--official', action='store_true')
    args = parser.parse_args()

    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    setup_environment(root)
    state = load_state(root)
    log('state: %s' % state)

    if not state.get('patched'):
        sync(root, args.official)
        apply_patches(root)
        strip_git_dirs(root)
        state.update(patched=True, checked=False)
        save_state(root, state)
    elif reapply_changed_patches(root):
        state['checked'] = False
        save_state(root, state)

    write_args(root, args.official)
    gn_gen(root)

    if not state.get('checked'):
        # Compile the patched files first, so that errors in the patches show
        # up within the first hours instead of at the end of the build.
        sources = compiled_patched_sources(root)
        log('compiling %d patched sources first' % len(sources))
        if sources:
            code, failed, timed_out = run_ninja(
                root, [s + '^' for s in sources], args.deadline, args.jobs, 'check')
            if failed or (code != 0 and not timed_out):
                return BUILD_ERRORS_EXIT
            if timed_out:
                return TIMEOUT_EXIT
        state['checked'] = True
        save_state(root, state)

    code, failed, timed_out = run_ninja(root, NINJA_TARGETS, args.deadline,
                                        args.jobs, 'build')
    log_disk(root)
    if failed:
        return BUILD_ERRORS_EXIT
    if timed_out:
        return TIMEOUT_EXIT
    if code != 0:
        return code
    package(root)
    return 0


if __name__ == '__main__':
    sys.exit(main())
