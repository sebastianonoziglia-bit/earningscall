"""
Utility functions for managing local workflows.
"""

import os
import subprocess
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def restart_workflow(workflow_name):
    """
    Restart a workflow
    
    Args:
        workflow_name: Name of the workflow to restart
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # In a real implementation, this would use a provider-specific API
        # For now, we'll mock the behavior
        logger.info(f"Restarting workflow: {workflow_name}")
        
        if workflow_name == "API Server":
            # Kill any existing API server processes
            try:
                # Find processes running on port 5050 (API server port)
                cmd = "lsof -i :5050 -t"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout:
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        # Kill the process
                        subprocess.run(f"kill -9 {pid}", shell=True)
                        logger.info(f"Killed process {pid}")
            except Exception as e:
                logger.warning(f"Error killing existing processes: {e}")
            
            # Start the API server in background
            try:
                cmd = "nohup python api_server.py > api_server.log 2>&1 &"
                subprocess.Popen(cmd, shell=True)
                logger.info("Started API server")
                return True
            except Exception as e:
                logger.error(f"Error starting API server: {e}")
                return False
        else:
            logger.warning(f"Restart not implemented for workflow: {workflow_name}")
            return False
    except Exception as e:
        logger.error(f"Error restarting workflow: {e}")
        return False
