"""
thread_manager.py
-----------------
Centralized thread-safe queue system for FrogPaper background operations.

This module provides a unified way to handle background work and thread-safe UI updates,
eliminating scattered threading patterns throughout the codebase.
"""

import queue
import threading
import logging
import tkinter as tk
from typing import Any, Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UITask:
    """Represents a task to be executed on the main UI thread."""
    callback: Callable[..., Any]
    args: tuple = ()
    kwargs: dict | None = None
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class ThreadManager:
    """
    Centralized manager for background threads and thread-safe UI updates.
    
    This ensures all UI operations happen on the main thread while background
    work can safely run in worker threads, communicating via a thread-safe queue.
    """
    
    def __init__(self, root: tk.Misc) -> None:
        """
        Initialize the thread manager.
        
        Args:
            root: The Tkinter root window for scheduling UI updates
        """
        self.root = root
        self.ui_queue = queue.Queue()
        self.background_threads = []
        self.running = True
        self._ui_poll_job = None
        
        # Start the UI queue polling
        self._start_ui_polling()
        
    def _start_ui_polling(self) -> None:
        """Start polling the UI queue for tasks to execute on the main thread."""
        if not self.running:
            return
            
        try:
            # Process all pending UI tasks
            while not self.ui_queue.empty():
                try:
                    task = self.ui_queue.get_nowait()
                    self._execute_ui_task(task)
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"Error executing UI task: {e}")
        except Exception as e:
            logger.error(f"Error in UI queue polling: {e}")
        
        # Schedule next poll (100ms to balance responsiveness and CPU usage)
        self._ui_poll_job = self.root.after(100, self._start_ui_polling)
    
    def _execute_ui_task(self, task: UITask) -> None:
        """Execute a UI task on the main thread."""
        try:
            task.callback(*task.args, **task.kwargs)
        except Exception as e:
            logger.error(f"Error in UI callback {task.callback.__name__}: {e}")
    
    def schedule_ui_update(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """
        Schedule a UI update to run on the main thread.
        
        This is thread-safe and can be called from any thread.
        
        Args:
            callback: The function to call on the main thread
            *args: Positional arguments for the callback
            **kwargs: Keyword arguments for the callback
        """
        task = UITask(callback=callback, args=args, kwargs=kwargs)
        self.ui_queue.put(task)
    
    def run_background(self, target: Callable[..., Any], *args: Any, daemon: bool = True, name: str | None = None, **kwargs: Any) -> threading.Thread:
        """
        Run a function in a background thread.
        
        Args:
            target: The function to run in the background
            *args: Positional arguments for the target function
            daemon: Whether the thread should be a daemon thread
            name: Optional name for the thread
            **kwargs: Keyword arguments for the target function
            
        Returns:
            The created Thread object
        """
        def wrapped_target():
            try:
                target(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in background thread {target.__name__}: {e}")
                # Schedule error display on main thread if possible
                self.schedule_ui_update(
                    logger.error, 
                    f"Background task failed: {e}"
                )
        
        thread = threading.Thread(target=wrapped_target, daemon=daemon, name=name)
        thread.start()
        self.background_threads.append(thread)
        
        # Clean up finished threads periodically
        self._cleanup_finished_threads()
        
        return thread
    
    def _cleanup_finished_threads(self) -> None:
        """Remove finished threads from the tracking list."""
        self.background_threads = [
            t for t in self.background_threads if t.is_alive()
        ]
    
    def shutdown(self) -> None:
        """Cleanly shutdown the thread manager."""
        self.running = False
        
        # Cancel UI polling
        if self._ui_poll_job:
            try:
                self.root.after_cancel(self._ui_poll_job)
            except Exception:
                pass
        
        # Process remaining UI tasks
        while not self.ui_queue.empty():
            try:
                task = self.ui_queue.get_nowait()
                self._execute_ui_task(task)
            except queue.Empty:
                break
        
        # Wait for background threads to finish (with timeout)
        for thread in self.background_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        logger.info("ThreadManager shutdown complete")


# Global instance (will be initialized by app.py)
_thread_manager: Optional[ThreadManager] = None


def initialize_thread_manager(root: tk.Misc) -> None:
    """Initialize the global thread manager instance."""
    global _thread_manager
    _thread_manager = ThreadManager(root)
    logger.info("ThreadManager initialized")


def get_thread_manager() -> Optional[ThreadManager]:
    """Get the global thread manager instance."""
    return _thread_manager


def schedule_ui_update(callback: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """
    Convenience function to schedule UI updates using the global thread manager.
    
    Args:
        callback: The function to call on the main thread
        *args: Positional arguments for the callback
        **kwargs: Keyword arguments for the callback
    """
    if _thread_manager is None:
        logger.warning("ThreadManager not initialized, UI update may not be thread-safe")
        # Fallback to direct call (not thread-safe, but prevents crashes)
        callback(*args, **kwargs)
    else:
        _thread_manager.schedule_ui_update(callback, *args, **kwargs)


def run_background(target: Callable[..., Any], *args: Any, daemon: bool = True, name: str | None = None, **kwargs: Any) -> threading.Thread:
    """
    Convenience function to run background work using the global thread manager.
    
    Args:
        target: The function to run in the background
        *args: Positional arguments for the target function
        daemon: Whether the thread should be a daemon thread
        name: Optional name for the thread
        **kwargs: Keyword arguments for the target function
        
    Returns:
        The created Thread object
    """
    if _thread_manager is None:
        logger.warning("ThreadManager not initialized, running thread directly")
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=daemon)
        thread.start()
        return thread
    else:
        return _thread_manager.run_background(target, *args, daemon=daemon, **kwargs)


def shutdown_thread_manager() -> None:
    """Shutdown the global thread manager."""
    global _thread_manager
    if _thread_manager is not None:
        _thread_manager.shutdown()
        _thread_manager = None
        logger.info("Global ThreadManager shutdown")
