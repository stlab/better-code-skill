"""Native Windows storage for the doing ledger."""

from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import msvcrt
import os
import uuid


GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ_WRITE = 0x00000003
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
OPEN_ALWAYS = 4
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_ATTRIBUTE_TAG_INFO = 9
LOCKFILE_EXCLUSIVE_LOCK = 2
MOVEFILE_REPLACE_EXISTING = 1
MOVEFILE_WRITE_THROUGH = 8
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)


class AttributeTagInfo(ctypes.Structure):
    """File attributes and reparse tag returned by Windows."""

    _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]


class Overlapped(ctypes.Structure):
    """Windows I/O state for the lock's byte offset and completion event."""

    _fields_ = [
        ("internal", ctypes.c_size_t),
        ("internal_high", ctypes.c_size_t),
        ("offset", wintypes.DWORD),
        ("offset_high", wintypes.DWORD),
        ("event", wintypes.HANDLE),
    ]


def bind(name, result, arguments):
    """Return a Windows function with its native calling signature."""
    function = getattr(KERNEL32, name)
    function.restype = result
    function.argtypes = arguments
    return function


create_file = bind("CreateFileW", wintypes.HANDLE, [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
])
close_handle_native = bind("CloseHandle", wintypes.BOOL, [wintypes.HANDLE])
file_information = bind("GetFileInformationByHandleEx", wintypes.BOOL, [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
])
lock_file = bind("LockFileEx", wintypes.BOOL, [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    wintypes.DWORD, ctypes.POINTER(Overlapped),
])
unlock_file = bind("UnlockFileEx", wintypes.BOOL, [
    wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
    ctypes.POINTER(Overlapped),
])
move_file = bind("MoveFileExW", wintypes.BOOL, [
    wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
])


def native_path(path):
    """Return an absolute Unicode Windows path without the MAX_PATH limit."""
    value = os.path.abspath(path)
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def close_handle(handle):
    """Close an owned Windows handle."""
    if not close_handle_native(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def open_checked(path, directory=False, create=False, writable=False,
                 share_delete=False):
    """Open a non-redirected disk path, preventing deletion unless shared."""
    access = GENERIC_READ | (GENERIC_WRITE if writable else 0)
    sharing = FILE_SHARE_READ_WRITE | (FILE_SHARE_DELETE if share_delete else 0)
    handle = create_file(
        native_path(path), access, sharing, None,
        OPEN_ALWAYS if create else OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    with ExitStack() as cleanup:
        cleanup.callback(close_handle, handle)
        info = AttributeTagInfo()
        if not file_information(handle, FILE_ATTRIBUTE_TAG_INFO,
                                ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise OSError(f"Storage path is a reparse point: {path}")
        if bool(info.attributes & FILE_ATTRIBUTE_DIRECTORY) != directory:
            raise OSError(f"Storage path has the wrong file type: {path}")
        cleanup.pop_all()
    return handle


class WindowsStore:
    """A pinned storage directory with a persistent lock for writable access."""

    def __init__(self, path, directory, lock):
        """Take ownership of the directory and optional writer-lock handles."""
        self.path = path
        self.directory = directory
        self.lock_handle = lock
        self.overlapped = Overlapped()

    @classmethod
    def open(cls, path, create, writable=True):
        """Open storage, returning None when absent and creation is disabled.

        Read-only access does not provision a writer lock.
        """
        if create:
            try:
                path.mkdir(mode=0o700)
            except FileExistsError:
                pass
        try:
            directory = open_checked(path, directory=True)
        except FileNotFoundError:
            if not create:
                return None
            raise
        with ExitStack() as cleanup:
            cleanup.callback(close_handle, directory)
            lock = None
            if writable:
                lock = open_checked(path / ".doing.lock", create=True, writable=True)
                cleanup.callback(close_handle, lock)
            store = cls(path, directory, lock)
            cleanup.pop_all()
        return store

    def lock(self):
        """Wait for exclusive writer access; read-only stores need no lock."""
        if self.lock_handle is None:
            return
        if not lock_file(self.lock_handle, LOCKFILE_EXCLUSIVE_LOCK, 0, 1, 0,
                         ctypes.byref(self.overlapped)):
            raise ctypes.WinError(ctypes.get_last_error())

    def unlock(self):
        """Release the writer lock, if this store has one."""
        if self.lock_handle is None:
            return
        if not unlock_file(self.lock_handle, 0, 1, 0,
                           ctypes.byref(self.overlapped)):
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self):
        """Read a UTF-8 ledger snapshot, or return None if the file is absent.

        Concurrent replacement does not change the opened snapshot.
        Time and additional space: O(n), where n is the file size.
        """
        try:
            handle = open_checked(self.path / "doing.md", share_delete=True)
        except FileNotFoundError:
            return None
        with ExitStack() as cleanup:
            cleanup.callback(close_handle, handle)
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            cleanup.pop_all()
        with os.fdopen(descriptor, encoding="utf-8") as file:
            return file.read()

    def replace(self, text, task_id):
        """Replace the ledger with flushed UTF-8 text and request write-through.

        Requires this store's writer lock to be held.
        A replacement error reports task_id and an uncertain save status.
        Time and additional space: O(n), where n is the text size.
        """
        temporary = self.path / f".doing-{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY, 0o600,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                file.write(text)
                file.flush()
                os.fsync(file.fileno())
            if not move_file(
                native_path(temporary), native_path(self.path / "doing.md"),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
            ):
                error = ctypes.WinError(ctypes.get_last_error())
                raise OSError(
                    f"Task {task_id} update may have been saved; "
                    f"verify with show all --json before retrying: {error}"
                ) from error
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def close(self):
        """Close the lock and directory handles, releasing any remaining lock."""
        try:
            if self.lock_handle is not None:
                close_handle(self.lock_handle)
        finally:
            close_handle(self.directory)
