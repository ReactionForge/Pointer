"""Bounded, process-local protocol for Pointer's independent backdrop window."""
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import subprocess
import uuid

from PySide6.QtCore import QObject, QProcess, QTimer, Signal
from PySide6.QtGui import QGuiApplication

BUNDLED_HELPER = 'native/CompositionSidecar.exe'


def bundled_helper(root=None):
    """Use the manifest-verified shipped binary without client compilation."""
    if root is None:
        from pointer.paths import ROOT
        root = ROOT
    root = Path(root).resolve()
    executable = (root / BUNDLED_HELPER).resolve()
    try:
        if not executable.is_relative_to(root):
            raise ValueError('helper path leaves the release directory')
        manifest = json.loads((root / 'PACKAGE.json').read_text(encoding='utf8'))
        files = manifest.get('files')
        expected = files.get(BUNDLED_HELPER) if isinstance(files, dict) else None
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError('helper is missing from the release manifest')
        binary = executable.read_bytes()
        if not binary.startswith(b'MZ') or hashlib.sha256(binary).hexdigest() != expected:
            raise ValueError('helper checksum does not match the release manifest')
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise OSError(f'The bundled Composition helper is unavailable: {error}') from error
    return executable


@dataclass(frozen=True)
class UnderlayState:
    visible: bool
    x: int
    y: int
    width: int
    height: int
    radius: int = 0
    sigma: float = 0.0

    def __post_init__(self):
        if type(self.visible) is not bool:
            raise ValueError('visible must be a boolean')
        for name in ('x', 'y', 'width', 'height', 'radius'):
            value = getattr(self, name)
            if type(value) is not int or not -(2**31) <= value < 2**31:
                raise ValueError(f'{name} must be a signed 32-bit integer')
        if self.width <= 0 or self.height <= 0 or self.radius < 0:
            raise ValueError('width and height must be positive; radius cannot be negative')
        if type(self.sigma) not in (int, float) or not 0 <= self.sigma <= 48 or not math.isfinite(self.sigma):
            raise ValueError('sigma must be finite and between 0 and 48 DIP')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate protocol field')
        result[key] = value
    return result


def _compiler_inputs():
    source_root = Path(__file__).with_name('composition')
    sources = [source_root / 'SidecarCommon.cs', source_root / 'CompositionSidecar.cs']
    for source in sources:
        if not source.is_file():
            raise OSError(f'Composition helper source is missing: {source.name}')
    windows = Path(os.environ.get('WINDIR', r'C:\Windows'))
    framework = windows / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319'
    compiler = framework / 'csc.exe'
    if not compiler.is_file():
        raise OSError('The installed .NET Framework compiler is unavailable')
    runtime = ['System.Runtime.dll', 'System.Runtime.WindowsRuntime.dll',
               'System.Numerics.Vectors.dll', 'System.Runtime.InteropServices.WindowsRuntime.dll']
    metadata = sorted((windows / 'System32' / 'WinMetadata').glob('*.winmd'))
    if not metadata or any(not (framework / name).is_file() for name in runtime):
        raise OSError('The installed Windows Composition metadata or .NET runtime is unavailable')
    references = ['/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
                  '/r:System.Numerics.dll', '/r:System.Web.Extensions.dll']
    references.extend('/r:' + str(framework / name) for name in runtime)
    references.extend('/r:' + str(path) for path in metadata)
    return compiler, sources, references


def prepare_helper(cache_dir):
    """Compile only with the existing Windows compiler; preserve prior cache builds."""
    if sys.platform != 'win32':
        raise OSError('Windows Composition helper requires Windows')
    if getattr(sys, 'frozen', False):
        return bundled_helper()
    compiler, sources, references = _compiler_inputs()
    digest = hashlib.sha256(b'Pointer Composition protocol 1; x64 winexe\0')
    for source in sources:
        digest.update(source.name.encode('utf8') + b'\0' + source.read_bytes() + b'\0')
    digest.update(str(compiler).encode('utf8'))
    digest.update('\0'.join(references).encode('utf8'))
    folder = Path(cache_dir).resolve()
    executable = folder / ('CompositionSidecar-' + digest.hexdigest() + '.exe')
    if executable.is_file():
        with executable.open('rb') as binary:
            if binary.read(2) == b'MZ':
                return executable
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder / ('.compile-' + uuid.uuid4().hex + '.exe')
    arguments = [str(compiler), '/nologo', '/platform:x64', '/target:winexe',
                 '/main:SidecarProgram', '/out:' + str(temporary), *references,
                 *(str(source) for source in sources)]
    try:
        result = subprocess.run(arguments, capture_output=True, timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            detail = (result.stdout + result.stderr).decode('utf8', errors='replace').strip()[:1024]
            raise OSError(f'Composition helper compilation failed: {detail}')
        if not temporary.is_file():
            raise OSError('Composition helper compilation did not produce a Windows executable')
        with temporary.open('rb') as binary:
            if binary.read(2) != b'MZ':
                raise OSError('Composition helper compilation did not produce a Windows executable')
        os.replace(temporary, executable)
        return executable
    except subprocess.TimeoutExpired as error:
        raise OSError('Composition helper compilation timed out') from error
    finally:
        temporary.unlink(missing_ok=True)


class CompositionHost(QObject):
    ready_changed = Signal(bool)
    failed = Signal(str)
    MAX_BUFFER = 65536
    MAX_LINE = 4096

    def __init__(self, helper_path, parent=None, *, process_factory=None,
                 handshake_ms=3000, apply_ms=2000, shutdown_ms=300):
        super().__init__(parent)
        self.helper_path = str(Path(helper_path).absolute())
        self._factory = process_factory or QProcess
        self._injected_process = process_factory is not None
        self.ready = False
        self.last_error = ''
        self._process = None
        self._started = False
        self._closing = False
        self._hwnd = 0
        self._pid = os.getpid()
        self._buffer = b''
        self._seq = 0
        self._desired = None
        self._inflight = None
        self._handshake_timer = QTimer(self)
        self._handshake_timer.setSingleShot(True)
        self._handshake_timer.setInterval(handshake_ms)
        self._handshake_timer.timeout.connect(lambda: self._fail('Backdrop helper ready timeout'))
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(apply_ms)
        self._apply_timer.timeout.connect(lambda: self._fail('Backdrop helper apply timeout'))
        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.setSingleShot(True)
        self._shutdown_timer.setInterval(shutdown_ms)
        self._shutdown_ms = shutdown_ms
        self._shutdown_timer.timeout.connect(self._kill_owned_process)

    def start(self, hwnd):
        if type(hwnd) is not int or hwnd <= 0:
            raise ValueError('hwnd must identify a live application window')
        if self._closing:
            return False
        if self._started:
            if hwnd != self._hwnd:
                self._fail('Backdrop helper cannot switch to a different window')
            return not bool(self.last_error)
        if not self._injected_process and (sys.platform != 'win32' or QGuiApplication.platformName() != 'windows'):
            self._fail('Native backdrop requires the Qt Windows platform')
            return False
        self._hwnd = hwnd
        self._started = True
        process = self._factory(self)
        self._process = process
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._drain_stderr)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self._handshake_timer.start()
        process.start(self.helper_path, ['--pid', str(self._pid), '--hwnd', str(hwnd)])
        return not bool(self.last_error)

    def update(self, state):
        if not isinstance(state, UnderlayState):
            if not isinstance(state, dict):
                raise ValueError('Backdrop state must be an UnderlayState or dictionary')
            try:
                state = UnderlayState(**state)
            except TypeError as error:
                raise ValueError('Invalid backdrop state fields') from error
        if self._closing:
            return False
        self._seq += 1
        self._desired = (self._seq, state)
        self._send_latest()
        return True

    def close(self):
        if self._closing:
            return
        self._closing = True
        self._set_ready(False)
        self._handshake_timer.stop()
        self._apply_timer.stop()
        self._desired = None
        self._inflight = None
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return
        process.write(b'{"command":"quit"}\n')
        process.closeWriteChannel()
        self._shutdown_timer.start()

    def shutdown(self):
        """Finish our child before GUI teardown releases the upgrade mutex."""
        self.close()
        self._shutdown_timer.stop()
        process = self._process
        if process is None or process.state() == QProcess.ProcessState.NotRunning:
            return True
        # The GUI event loop may already have stopped. QProcess's bounded wait
        # flushes the quit/EOF pipe and reaps the child without relying on timers.
        if not process.waitForFinished(self._shutdown_ms):
            process.kill()
            process.waitForFinished(self._shutdown_ms)
        return process.state() == QProcess.ProcessState.NotRunning

    def _set_ready(self, ready):
        if self.ready != ready:
            self.ready = ready
            self.ready_changed.emit(ready)

    def _fail(self, message):
        if self._closing:
            return
        self.last_error = str(message)[:1024]
        self.close()
        self.failed.emit(self.last_error)

    def _kill_owned_process(self):
        process = self._process
        if process is not None and process.state() != QProcess.ProcessState.NotRunning:
            process.kill()

    def _drain_stderr(self):
        if self._process is not None:
            self._process.readAllStandardError()

    def _process_error(self, error):
        if self._process is not None:
            self._fail(f'Backdrop helper process error: {self._process.errorString()}')

    def _process_finished(self, exit_code, exit_status):
        self._shutdown_timer.stop()
        if not self._closing:
            self._fail(f'Backdrop helper ended before shutdown ({exit_code})')
        self._process = None

    def _read_stdout(self):
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput())
        if self._closing:
            return
        if len(self._buffer) + len(data) > self.MAX_BUFFER:
            self._fail('Backdrop helper protocol buffer exceeded 64 KiB')
            return
        self._buffer += data
        while b'\n' in self._buffer and not self._closing:
            line, self._buffer = self._buffer.split(b'\n', 1)
            if len(line) > self.MAX_LINE:
                self._fail('Backdrop helper protocol line exceeded 4 KiB')
                return
            try:
                message = json.loads(line.decode('utf8'), object_pairs_hook=_unique_object)
                self._accept_message(message)
            except (UnicodeError, ValueError, TypeError) as error:
                self._fail(f'Invalid backdrop helper protocol: {error}')
        if len(self._buffer) > self.MAX_LINE:
            self._fail('Backdrop helper protocol line exceeded 4 KiB')

    def _accept_message(self, message):
        if not isinstance(message, dict):
            raise ValueError('message must be an object')
        event = message.get('event')
        if event == 'ready':
            if self.ready or set(message) != {'event', 'protocol', 'pid', 'hwnd'}:
                raise ValueError('unexpected ready fields')
            for name, expected in (('protocol', 1), ('pid', self._pid), ('hwnd', self._hwnd)):
                if type(message[name]) is not int or message[name] != expected:
                    raise ValueError('ready identity does not match the application window')
            self._handshake_timer.stop()
            self._set_ready(True)
            self._send_latest()
        elif event == 'applied':
            if (not self.ready or set(message) != {'event', 'seq'} or
                    type(message['seq']) is not int or message['seq'] != self._inflight):
                raise ValueError('unexpected apply acknowledgement')
            self._apply_timer.stop()
            self._inflight = None
            self._send_latest()
        elif event == 'error':
            required = {'event', 'code', 'message'}
            if not required <= set(message) or set(message) - required - {'seq'}:
                raise ValueError('unexpected error fields')
            if not isinstance(message['code'], str) or not isinstance(message['message'], str):
                raise ValueError('error code and message must be strings')
            if 'seq' in message and (type(message['seq']) is not int or message['seq'] < 0):
                raise ValueError('invalid error sequence')
            self._fail(f'{message["code"]}: {message["message"]}')
        else:
            raise ValueError('unknown helper event')

    def _send_latest(self):
        if not self.ready or self._inflight is not None or self._desired is None:
            return
        seq, state = self._desired
        self._desired = None
        self._inflight = seq
        data = (json.dumps(dict(asdict(state), seq=seq), separators=(',', ':'), allow_nan=False) + '\n').encode('utf8')
        self._apply_timer.start()
        if self._process.write(data) != len(data):
            self._fail('Backdrop helper input channel closed')
