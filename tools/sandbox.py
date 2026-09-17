import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import get_settings


_AIRGAP_PRELUDE = """# Sovereign Sandbox Air-gap Prelude
import socket as _sb_socket
def _sb_blocked_connect(*args, **kwargs):
    raise PermissionError("Air-gap violation: Network access is strictly blocked inside the sandbox")
_sb_socket.socket.connect = _sb_blocked_connect
_sb_socket.create_connection = _sb_blocked_connect
"""


class Sandbox:
    """Dual-Mode Sandboxed Execution Engine (Docker + Subprocess Isolation)."""

    def __init__(self):
        self.settings = get_settings()
        self.docker_available = self._check_docker()

    def _check_docker(self) -> bool:
        """Check if docker daemon is running and available."""
        try:
            import docker
            client = docker.from_env()
            client.ping()
            return True
        except Exception:
            return False

    def _parse_memory_limit_bytes(self, mem_str: str) -> int:
        """Parse memory limit string (e.g. '512m', '1g', '64k') to bytes."""
        if not mem_str:
            return 512 * 1024 * 1024
        s = mem_str.strip().lower()
        try:
            if s.endswith("g"):
                return int(float(s[:-1]) * 1024 * 1024 * 1024)
            elif s.endswith("m"):
                return int(float(s[:-1]) * 1024 * 1024)
            elif s.endswith("k"):
                return int(float(s[:-1]) * 1024)
            return int(s)
        except (ValueError, TypeError):
            return 512 * 1024 * 1024

    def execute_code(self, code: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Execute python code in the most secure available sandbox mode."""
        if code is None:
            code = ""

        timeout_val = timeout if timeout is not None else self.settings.SANDBOX_TIMEOUT_SECONDS

        if not code.strip():
            return {
                "mode": "docker" if self.docker_available else "subprocess",
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "success": True,
            }

        # Wrap code with airgap prelude for subprocess mode
        full_code = _AIRGAP_PRELUDE + "\n" + code

        # Write code to an ephemeral temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".py", prefix="sandbox_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(full_code)

            if self.docker_available:
                return self._execute_docker(temp_path, timeout_val)
            else:
                return self._execute_subprocess(temp_path, timeout_val)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _execute_docker(self, filepath: str, timeout: int) -> Dict[str, Any]:
        """Execute code using Docker container isolation."""
        try:
            import docker
            client = docker.from_env()

            code_dir = os.path.dirname(filepath)
            filename = os.path.basename(filepath)

            container = client.containers.run(
                self.settings.SANDBOX_DOCKER_IMAGE,
                command=f"python /sandbox/{filename}",
                volumes={code_dir: {"bind": "/sandbox", "mode": "ro"}},
                network_mode="none",
                mem_limit=self.settings.SANDBOX_MEMORY_LIMIT,
                detach=True,
                read_only=True,
            )

            try:
                result = container.wait(timeout=timeout)
                logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                exit_code = result.get("StatusCode", -1)

                return {
                    "mode": "docker",
                    "stdout": logs if exit_code == 0 else "",
                    "stderr": logs if exit_code != 0 else "",
                    "exit_code": exit_code,
                    "success": exit_code == 0,
                }
            except Exception as e:
                return {
                    "mode": "docker",
                    "stdout": "",
                    "stderr": f"Execution error or timeout: {str(e)}",
                    "exit_code": -1,
                    "success": False,
                }
            finally:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

        except Exception as e:
            return {
                "mode": "docker",
                "stdout": "",
                "stderr": f"Docker error: {str(e)}",
                "exit_code": -1,
                "success": False,
            }

    def _execute_subprocess(self, filepath: str, timeout: int) -> Dict[str, Any]:
        """Execute code using restricted subprocess sandbox (Fallback)."""
        # Strip all credentials and sensitive env vars
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
        }

        mem_bytes = self._parse_memory_limit_bytes(self.settings.SANDBOX_MEMORY_LIMIT)

        def preexec_fn():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
            except Exception:
                pass

        try:
            process = subprocess.Popen(
                [sys.executable, filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=preexec_fn if sys.platform != "win32" else None,
                text=True,
            )

            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode

            return {
                "mode": "subprocess",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": exit_code == 0,
            }

        except subprocess.TimeoutExpired:
            process.kill()
            try:
                stdout, stderr = process.communicate(timeout=2)
            except Exception:
                pass
            return {
                "mode": "subprocess",
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds",
                "exit_code": -1,
                "success": False,
            }
        except Exception as e:
            return {
                "mode": "subprocess",
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1,
                "success": False,
            }
