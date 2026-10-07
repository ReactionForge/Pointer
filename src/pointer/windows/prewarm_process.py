"""Run an isolated resource worker with a bounded, owned Windows process tree."""
import ctypes
from ctypes import wintypes
import math
import subprocess
import time
from .api import KERNEL32, _signature


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class _Limits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _Startup(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('reserved', wintypes.LPWSTR),
                ('desktop', wintypes.LPWSTR), ('title', wintypes.LPWSTR),
                ('x', wintypes.DWORD), ('y', wintypes.DWORD),
                ('width', wintypes.DWORD), ('height', wintypes.DWORD),
                ('chars_x', wintypes.DWORD), ('chars_y', wintypes.DWORD),
                ('fill', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('show', wintypes.WORD), ('reserved_size', wintypes.WORD),
                ('reserved_bytes', ctypes.c_void_p), ('stdin', wintypes.HANDLE),
                ('stdout', wintypes.HANDLE), ('stderr', wintypes.HANDLE)]


class _Process(ctypes.Structure):
    _fields_ = [('process', wintypes.HANDLE), ('thread', wintypes.HANDLE),
                ('pid', wintypes.DWORD), ('thread_id', wintypes.DWORD)]


class _Accounting(ctypes.Structure):
    _fields_ = [('times', ctypes.c_int64 * 4), ('page_faults', wintypes.DWORD),
                ('total_processes', wintypes.DWORD), ('active_processes', wintypes.DWORD),
                ('terminated_processes', wintypes.DWORD)]


_signature(KERNEL32, 'CreateJobObjectW', [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE)
_signature(KERNEL32, 'SetInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL)
_signature(KERNEL32, 'AssignProcessToJobObject', [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL)
_signature(KERNEL32, 'TerminateJobObject', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL)
_signature(KERNEL32, 'QueryInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
           wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL)
_signature(KERNEL32, 'CreateProcessW', [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
           wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
           ctypes.POINTER(_Startup), ctypes.POINTER(_Process)], wintypes.BOOL)
_signature(KERNEL32, 'ResumeThread', [wintypes.HANDLE], wintypes.DWORD)
_signature(KERNEL32, 'GetExitCodeProcess', [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL)
_signature(KERNEL32, 'TerminateProcess', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL)
_signature(KERNEL32, 'OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)
_signature(KERNEL32, 'IsProcessInJob', [wintypes.HANDLE, wintypes.HANDLE,
           ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL)


def _member_handles(job):
    """Hold only verified job members so termination can await their real exit."""
    capacity = 64
    while capacity <= 65536:
        class ProcessIds(ctypes.Structure):
            _fields_ = [('assigned', wintypes.DWORD), ('count', wintypes.DWORD),
                        ('pids', ctypes.c_size_t * capacity)]
        members = ProcessIds()
        if KERNEL32.QueryInformationJobObject(job, 3, ctypes.byref(members), ctypes.sizeof(members), None):
            break
        error = ctypes.get_last_error()
        if error != 234:  # ERROR_MORE_DATA: a process was added or the buffer was too small.
            raise ctypes.WinError(error)
        capacity = max(capacity * 2, members.assigned)
    else:
        raise RuntimeError('Resource worker process tree exceeded the cleanup limit')
    handles = []
    try:
        for pid in members.pids[:members.count]:
            handle = KERNEL32.OpenProcess(0x100000 | 0x1000, False, pid)
            if not handle:
                if ctypes.get_last_error() == 87:  # The member exited before OpenProcess.
                    continue
                raise ctypes.WinError(ctypes.get_last_error())
            belongs = wintypes.BOOL()
            try:
                if not KERNEL32.IsProcessInJob(handle, job, ctypes.byref(belongs)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if belongs.value:
                    handles.append(handle)
                    handle = None
            finally:
                if handle:
                    KERNEL32.CloseHandle(handle)
        return handles
    except BaseException:
        for handle in handles:
            KERNEL32.CloseHandle(handle)
        raise


def run_hidden(command, *, cwd, env, timeout):
    """Suspend before job assignment so a frozen bootloader cannot escape cleanup."""
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError('Resource preparation timeout must be within 0–300 seconds')
    job = KERNEL32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    process = _Process()
    assigned = False
    try:
        limits = _Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; only this unnamed job.
        if not KERNEL32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        startup = _Startup(size=ctypes.sizeof(_Startup), flags=1, show=0)
        block = None if env is None else ctypes.create_unicode_buffer(
            '\0'.join(f'{key}={value}' for key, value in sorted(env.items(), key=lambda item: item[0].casefold())) + '\0\0')
        line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(item) for item in command]))
        # CREATE_SUSPENDED | CREATE_NO_WINDOW | CREATE_UNICODE_ENVIRONMENT.
        if not KERNEL32.CreateProcessW(None, line, None, None, False, 0x08000404,
                                      block, str(cwd), ctypes.byref(startup), ctypes.byref(process)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not KERNEL32.AssignProcessToJobObject(job, process.process):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned = True
        if KERNEL32.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        result = KERNEL32.WaitForSingleObject(process.process, math.ceil(timeout * 1000))
        if result == 0x102:
            raise subprocess.TimeoutExpired(command, timeout)
        if result != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = wintypes.DWORD()
        if not KERNEL32.GetExitCodeProcess(process.process, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        return code.value
    finally:
        members = []
        try:
            if assigned:
                deadline = time.monotonic() + 2
                members = _member_handles(job)
                if not KERNEL32.TerminateJobObject(job, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
                # Accounting can reach zero before process handles become signaled.
                # Await the real member handles within one shared deadline, off the GUI.
                for handle in members:
                    remaining = max(0, math.ceil((deadline - time.monotonic()) * 1000))
                    result = KERNEL32.WaitForSingleObject(handle, remaining)
                    if result == 0x102:
                        raise RuntimeError('Resource worker process tree did not exit within two seconds')
                    if result != 0:
                        raise ctypes.WinError(ctypes.get_last_error())
                while True:
                    accounting = _Accounting()
                    if not KERNEL32.QueryInformationJobObject(job, 1, ctypes.byref(accounting),
                                                              ctypes.sizeof(accounting), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    if not accounting.active_processes:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Resource worker process tree did not exit within two seconds')
                    time.sleep(.01)
        finally:
            KERNEL32.CloseHandle(job)
            for handle in members:
                KERNEL32.CloseHandle(handle)
            if process.process:
                if not assigned:
                    KERNEL32.TerminateProcess(process.process, 1)
                remaining = max(0, math.ceil((deadline - time.monotonic()) * 1000)) if assigned else 2000
                KERNEL32.WaitForSingleObject(process.process, remaining)
                KERNEL32.CloseHandle(process.process)
            if process.thread:
                KERNEL32.CloseHandle(process.thread)
