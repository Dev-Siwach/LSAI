import asyncio
import collections
import logging
import socket
import time
from typing import Any, Dict, Optional, Tuple, Union

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Store original socket methods to avoid infinite recursion and allow restoring
_original_socket_connect = socket.socket.connect
_original_create_connection = socket.create_connection

class SecurityException(Exception):
    """Exception raised when an air-gap violation is detected."""
    pass

class NetworkMonitor:
    """Monitors and intercepts network traffic to enforce air-gap constraints."""
    
    _instance: Optional['NetworkMonitor'] = None
    
    def __new__(cls) -> 'NetworkMonitor':
        if cls._instance is None:
            cls._instance = super(NetworkMonitor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
            
        self.settings = get_settings()
        self.enforce = self.settings.AIRGAP_ENFORCE
        self.allowed_hosts = set(self.settings.AIRGAP_ALLOWED_HOSTS)
        
        # Buffer for recent network events
        self.events: collections.deque = collections.deque(
            maxlen=self.settings.AIRGAP_LOG_BUFFER_SIZE
        )
        
        # Async queues for live streaming
        self.subscribers: set[asyncio.Queue] = set()
        
        # Stats
        self.stats = {
            "blocked_requests": 0,
            "allowed_requests": 0,
            "bytes_transferred": 0,  # A bit tricky to track without wrapping send/recv, but we can store a placeholder
        }
        
        self._patched = False
        self._initialized = True
        
    def start(self) -> None:
        """Start the network monitor by monkey-patching socket methods."""
        if self._patched:
            return
            
        logger.info("Initializing Sovereign Air-Gap Network Monitor...")
        
        def _patched_socket_connect(sock: socket.socket, address: Union[Tuple[Any, ...], str, bytes]) -> None:
            """Patched socket.connect method."""
            host = ""
            port = ""
            
            if isinstance(address, tuple):
                host = address[0]
                port = address[1] if len(address) > 1 else ""
            elif isinstance(address, (str, bytes)):
                # UNIX socket
                host = address.decode('utf-8') if isinstance(address, bytes) else address
                port = "UNIX"
                
            if self.is_allowed(host):
                self.record_event(host, port, "ALLOWED")
                return _original_socket_connect(sock, address)
            else:
                self.record_event(host, port, "BLOCKED")
                raise SecurityException(f"Air-gap violation: blocked connection to {host}:{port}")

        def _patched_create_connection(address: Tuple[str, int], timeout: Any = socket._GLOBAL_DEFAULT_TIMEOUT, source_address: Optional[Tuple[str, int]] = None, *args: Any, **kwargs: Any) -> socket.socket:
            """Patched socket.create_connection method."""
            host, port = address
            
            if self.is_allowed(host):
                self.record_event(host, port, "ALLOWED")
                return _original_create_connection(address, timeout, source_address, *args, **kwargs)
            else:
                self.record_event(host, port, "BLOCKED")
                raise SecurityException(f"Air-gap violation: blocked connection to {host}:{port}")
                
        socket.socket.connect = _patched_socket_connect
        socket.create_connection = _patched_create_connection
        self._patched = True
        
    def stop(self) -> None:
        """Stop the network monitor and restore original socket methods."""
        if not self._patched:
            return
            
        logger.info("Stopping Network Monitor...")
        socket.socket.connect = _original_socket_connect
        socket.create_connection = _original_create_connection
        self._patched = False

    def is_allowed(self, host: str) -> bool:
        """Check if a host is allowed based on whitelist."""
        if not self.enforce:
            return True
            
        # Allow UNIX domain sockets (filesystem paths or abstract namespace)
        if host.startswith("/") or host.startswith("\\") or host.startswith("\x00"):
            return True
            
        # Allow IPv4 loopback network (127.0.0.0/8)
        if host.startswith("127."):
            return True
            
        return host in self.allowed_hosts or host == "0.0.0.0"

    def record_event(self, destination: str, port: Union[int, str], status: str, bytes_transferred: int = 0) -> None:
        """Record a network event and broadcast to subscribers."""
        event = {
            "timestamp": time.time(),
            "destination": destination,
            "port": port,
            "status": status,
            "bytes_transferred": bytes_transferred
        }
        self.events.append(event)
        
        if status == "BLOCKED":
            self.stats["blocked_requests"] += 1
            logger.warning(f"AIR-GAP VIOLATION BLOCKED: Attempt to reach {destination}:{port}")
        else:
            self.stats["allowed_requests"] += 1
            
        self.stats["bytes_transferred"] += bytes_transferred
            
        self._broadcast(event)
        
    def _broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all connected SSE subscribers."""
        # Using a copy of subscribers to avoid issues if set changes during iteration
        for queue in list(self.subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.error("SSE Subscriber queue full, dropping event")
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to live network events. Returns an async queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from live network events."""
        if queue in self.subscribers:
            self.subscribers.remove(queue)


# Global instance for easy access
network_monitor = NetworkMonitor()
