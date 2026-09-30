"""Advisory Unix locks for durable transactions and whole remote operations."""

import fcntl
import os
import threading


class FileMutex:
    """Transferable operation ownership: a worker may release its caller's lock."""

    def __init__(self, path):
        self.path = path
        self.local = threading.Lock()
        self.fd = None

    def acquire(self, blocking=True):
        if not self.local.acquire(blocking=blocking):
            return False
        fd = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            self.fd = fd
            return True
        except BlockingIOError:
            if fd is not None:
                os.close(fd)
            self.local.release()
            return False
        except BaseException:
            if fd is not None:
                os.close(fd)
            self.local.release()
            raise

    def release(self):
        fd, self.fd = self.fd, None
        try:
            if fd is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            if fd is not None:
                os.close(fd)
            self.local.release()


class FileRLock:
    """Reentrant within one thread; serialize read/modify/write across processes."""

    def __init__(self, path):
        self.local = threading.RLock()
        self.file = FileMutex(path)
        self.depth = 0

    def __enter__(self):
        self.local.acquire()
        try:
            if self.depth == 0:
                self.file.acquire()
            self.depth += 1
        except BaseException:
            self.local.release()
            raise
        return self

    def __exit__(self, *args):
        self.depth -= 1
        try:
            if self.depth == 0:
                self.file.release()
        finally:
            self.local.release()
