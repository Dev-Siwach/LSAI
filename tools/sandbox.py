import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple
import json

from config.settings import get_settings

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

    def execute_code(self, code: str, timeout: int = None) -> Dict[str, Any]:
        """Execute python code in the most secure available sandbox mode."""
        timeout_val = timeout or self.settings.SANDBOX_TIMEOUT_SECONDS
        
        # Write code to a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            if self.docker_available:
                return self._execute_docker(temp_path, timeout_val)
            else:
                return self._execute_subprocess(temp_path, timeout_val)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _execute_docker(self, filepath: str, timeout: int) -> Dict[str, Any]:
        """Execute code using Docker container isolation."""
        import docker
        client = docker.from_env()
        
        code_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        
        try:
            container = client.containers.run(
                self.settings.SANDBOX_DOCKER_IMAGE,
                command=f"python /sandbox/{filename}",
                volumes={code_dir: {'bind': '/sandbox', 'mode': 'ro'}},
                network_mode="none",
                mem_limit=self.settings.SANDBOX_MEMORY_LIMIT,
                # cpu_quota logic if needed, but omitted for simplicity unless specified
                detach=True,
                read_only=True
            )
            
            try:
                result = container.wait(timeout=timeout)
                logs = container.logs(stdout=True, stderr=True).decode('utf-8')
                exit_code = result['StatusCode']
                
                return {
                    "mode": "docker",
                    "stdout": logs if exit_code == 0 else "",
                    "stderr": logs if exit_code != 0 else "",
                    "exit_code": exit_code,
                    "success": exit_code == 0
                }
            except Exception as e:
                return {
                    "mode": "docker",
                    "stdout": "",
                    "stderr": f"Execution error or timeout: {str(e)}",
                    "exit_code": -1,
                    "success": False
                }
            finally:
                container.remove(force=True)
                
        except Exception as e:
            return {
                "mode": "docker",
                "stdout": "",
                "stderr": f"Docker error: {str(e)}",
                "exit_code": -1,
                "success": False
            }

    def _execute_subprocess(self, filepath: str, timeout: int) -> Dict[str, Any]:
        """Execute code using restricted subprocess sandbox (Fallback)."""
        # Strip credentials from env
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": os.environ.get("PYTHONPATH", "")
        }
        
        try:
            # We use resource limits on linux systems
            def preexec_fn():
                try:
                    import resource
                    # Set memory limit to SANDBOX_MEMORY_LIMIT (e.g. '512m')
                    mem_str = self.settings.SANDBOX_MEMORY_LIMIT
                    if mem_str.lower().endswith('m'):
                        mem_bytes = int(mem_str[:-1]) * 1024 * 1024
                    else:
                        mem_bytes = 512 * 1024 * 1024 # default
                        
                    resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                except Exception:
                    pass
                    
            process = subprocess.Popen(
                [sys.executable, filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                preexec_fn=preexec_fn if sys.platform != "win32" else None,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            
            return {
                "mode": "subprocess",
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "success": exit_code == 0
            }
            
        except subprocess.TimeoutExpired:
            process.kill()
            return {
                "mode": "subprocess",
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds",
                "exit_code": -1,
                "success": False
            }
        except Exception as e:
            return {
                "mode": "subprocess",
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1,
                "success": False
            }
