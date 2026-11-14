import asyncio
import subprocess
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from typing import AsyncGenerator
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()

async def stream_logs() -> AsyncGenerator[str, None]:
    """Stream logs from journalctl"""
    try:
        # Start journalctl process
        process = await asyncio.create_subprocess_exec(
            'sudo', 'journalctl', '-u', 'ioflow', '-f', '--no-pager', '-n', '100',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Stream output line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            
            # Format as Server-Sent Events
            yield f"data: {line.decode('utf-8', errors='ignore')}\n\n"
            
    except Exception as e:
        logger.error(f"Error streaming logs: {e}")
        yield f"data: Error: {str(e)}\n\n"
    finally:
        if process and process.returncode is None:
            process.terminate()
            await process.wait()

@router.get("/api/logs/stream")
async def get_logs_stream():
    """Stream IOFlow service logs"""
    try:
        return StreamingResponse(
            stream_logs(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
    except Exception as e:
        logger.error(f"Failed to stream logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/logs/recent")
async def get_recent_logs(lines: int = 100):
    """Get recent logs from IOFlow service"""
    try:
        result = subprocess.run(
            ['sudo', 'journalctl', '-u', 'ioflow', '--no-pager', '-n', str(lines)],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get logs: {result.stderr}"
            )
        
        return {
            "logs": result.stdout.split('\n'),
            "lines": lines
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout getting logs")
    except Exception as e:
        logger.error(f"Failed to get recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def serve_logs_page():
    """Serve the logs HTML page"""
    file_path = Path(__file__).parent.parent / "static" / "logs.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Logs page not found")
    return FileResponse(file_path)