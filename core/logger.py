# core/logger.py
"""
Centralized logging for Abeyance II.

Writes to:
  1. A persistent log file (abeyance.log) with timestamps and severity
  2. The GUI event log (when available)
  3. stdout as fallback

Usage:
    from core.logger import log
    log.info('System started')
    log.warn('Low energy', element='a')
    log.error('Failed to connect', exc=True)  # exc=True appends traceback
"""
import os
import time
import traceback
import threading

_LOG_FILE = 'abeyance.log'
_LEVELS = {'DEBUG': 0, 'INFO': 1, 'WARN': 2, 'ERROR': 3}


class AbeyanceLogger:
    def __init__(self, log_file=_LOG_FILE, min_level='DEBUG'):
        self.log_file = log_file
        self.min_level = _LEVELS.get(min_level, 0)
        self._gui_callback = None
        self._lock = threading.Lock()
        self._start_time = time.perf_counter()

        # Rotate: truncate if over 1MB
        if os.path.exists(self.log_file):
            try:
                if os.path.getsize(self.log_file) > 1_000_000:
                    with open(self.log_file, 'w'):
                        pass
            except OSError:
                pass

        self._write_raw(f'\n{"="*60}')
        self._write_raw(f'Abeyance II session started at {time.strftime("%Y-%m-%d %H:%M:%S")}')
        self._write_raw(f'{"="*60}\n')

    def set_gui_callback(self, callback):
        """Set a function(msg) that routes log messages to the GUI event log."""
        self._gui_callback = callback

    def debug(self, msg, **ctx):
        self._log('DEBUG', msg, **ctx)

    def info(self, msg, **ctx):
        self._log('INFO', msg, **ctx)

    def warn(self, msg, **ctx):
        self._log('WARN', msg, **ctx)

    def error(self, msg, exc=False, **ctx):
        self._log('ERROR', msg, exc=exc, **ctx)

    def _log(self, level, msg, exc=False, **ctx):
        if _LEVELS.get(level, 0) < self.min_level:
            return

        elapsed = time.perf_counter() - self._start_time
        timestamp = f'{elapsed:>8.2f}s'

        # Build context suffix: key=value pairs
        ctx_str = ''
        if ctx:
            ctx_str = '  ' + '  '.join(f'{k}={v}' for k, v in ctx.items())

        # Traceback for errors
        tb_str = ''
        if exc:
            tb_str = '\n' + traceback.format_exc()

        file_line = f'[{timestamp}] [{level:<5}] {msg}{ctx_str}{tb_str}'
        gui_line = f'[{level}] {msg}{ctx_str}'

        self._write_raw(file_line)

        if self._gui_callback:
            try:
                self._gui_callback(gui_line)
            except Exception:
                pass  # GUI may be shutting down

        if level in ('WARN', 'ERROR') or not self._gui_callback:
            print(file_line)

    def _write_raw(self, line):
        with self._lock:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(line + '\n')
            except OSError:
                pass


# Module-level singleton
log = AbeyanceLogger()
