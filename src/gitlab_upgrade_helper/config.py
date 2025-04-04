# In a file like gitlab_helper/config.py

import io
import logging
import re
from datetime import datetime
from fabric import Connection
from invoke.exceptions import UnexpectedExit

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

GITLAB_RB_PATH = "/etc/gitlab/gitlab.rb"

def modify_gitlab_rb_setting(
    host: str,
    key_filename: str,
    setting_key: str,
    setting_value: str, # Keep it simple for now: assumes string/numeric values
    ssh_user: str = "root", # Common for config changes, adjust if needed
    ssh_port: int = 22,
    create_backup: bool = True,
    run_reconfigure: bool = False,
) -> bool:
    """
    Connects to a GitLab server via SSH and modifies a specific setting
    in /etc/gitlab/gitlab.rb.

    Args:
        host: The IP address or hostname of the GitLab server.
        key_filename: Path to the SSH private key file (PEM).
        setting_key: The configuration key to modify (e.g., 'external_url').
        setting_value: The new value for the setting (e.g., "'http://new.gitlab.example.com'").
                       Note: Value should include necessary quotes for Ruby syntax.
        ssh_user: The username for the SSH connection.
        ssh_port: The port number for the SSH connection.
        create_backup: If True, creates a timestamped backup before modifying.
        run_reconfigure: If True, runs 'gitlab-ctl reconfigure' after modification.

    Returns:
        True if the modification (and optional reconfigure) was successful, False otherwise.
    """
    connect_kwargs = {"key_filename": key_filename}
    conn = Connection(
        host=host,
        user=ssh_user,
        port=ssh_port,
        connect_kwargs=connect_kwargs
    )

    try:
        log.info(f"Connecting to {ssh_user}@{host}:{ssh_port}...")
        # Test connection with a simple command
        conn.run("uname -a", hide=True) 
        log.info("Connection successful.")

        # --- 1. Backup (Optional) ---
        if create_backup:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = f"{GITLAB_RB_PATH}.bak.{timestamp}"
            log.info(f"Creating backup: {backup_path}")
            try:
                # Use sudo as gitlab.rb is typically owned by root
                conn.sudo(f"cp {GITLAB_RB_PATH} {backup_path}", hide=True)
                log.info("Backup created successfully.")
            except UnexpectedExit as e:
                log.error(f"Failed to create backup: {e}")
                return False

        # --- 2. Download current gitlab.rb ---
        log.info(f"Downloading current {GITLAB_RB_PATH}...")
        local_stream = io.StringIO()
        try:
            # Use sudo to ensure read permissions
            with conn.sftp() as sftp:
                 # Fabric/Paramiko SFTP might not directly support sudo reads.
                 # Workaround: sudo copy to tmp, download, then sudo rm tmp file.
                 tmp_path = f"/tmp/gitlab.rb.download.{timestamp}"
                 conn.sudo(f"cp {GITLAB_RB_PATH} {tmp_path}", hide=True)
                 conn.sudo(f"chown {ssh_user} {tmp_path}", hide=True) # Ensure user can read
                 conn.get(tmp_path, local_stream)
                 conn.sudo(f"rm {tmp_path}", hide=True) # Clean up
            
            original_content = local_stream.getvalue()
            log.info(f"{GITLAB_RB_PATH} downloaded successfully.")
            
        except Exception as e: # Broad exception for download/sudo issues
            log.error(f"Failed to download {GITLAB_RB_PATH}: {e}")
            return False
        finally:
             local_stream.close()


        # --- 3. Modify the setting ---
        log.info(f"Modifying setting: {setting_key} = {setting_value}")
        modified_lines = []
        found = False
        # Regex to find the setting, potentially commented out, at the start of a line
        # Handles whitespace variations and '=' or space separation
        # Example: `external_url '...'` or `# external_url = '...'`
        pattern = re.compile(rf"^\s*(#\s*)?{re.escape(setting_key)}\s*=?\s*.*")
        
        new_line = f"{setting_key} = {setting_value}" # Basic assignment format

        for line in original_content.splitlines():
            if pattern.match(line):
                if not found:
                    modified_lines.append(new_line)
                    log.info(f"  Replaced line: '{line.strip()}' with '{new_line}'")
                    found = True
                else:
                    # Found another match, comment it out to avoid duplicates
                    commented_line = f"# {line.strip()}"
                    modified_lines.append(commented_line)
                    log.warning(f"  Found duplicate line for '{setting_key}', commenting out: '{line.strip()}'")
            else:
                modified_lines.append(line)

        # If the setting was not found, append it to the end
        if not found:
            modified_lines.append(f"\n# Added by gitlab-upgrade-helper {datetime.now().isoformat()}")
            modified_lines.append(new_line)
            log.info(f"  Setting '{setting_key}' not found, appending to the end.")
            
        modified_content = "\n".join(modified_lines) + "\n" # Ensure trailing newline


        # --- 4. Upload modified gitlab.rb ---
        log.info(f"Uploading modified {GITLAB_RB_PATH}...")
        remote_stream = io.StringIO(modified_content)
        try:
             # Workaround for sudo write: upload to tmp, then sudo mv
             tmp_upload_path = f"/tmp/gitlab.rb.upload.{timestamp}"
             conn.put(remote_stream, tmp_upload_path)
             # Set correct permissions and ownership before moving
             conn.sudo(f"chown root:root {tmp_upload_path}", hide=True)
             conn.sudo(f"chmod 600 {tmp_upload_path}", hide=True)
             conn.sudo(f"mv {tmp_upload_path} {GITLAB_RB_PATH}", hide=True)
             log.info("Modified configuration uploaded successfully.")
        except Exception as e: # Broad exception for upload/sudo issues
            log.error(f"Failed to upload modified configuration: {e}")
            # Attempt to restore backup if created
            if create_backup:
                log.warning(f"Attempting to restore backup {backup_path}...")
                try:
                    conn.sudo(f"mv {backup_path} {GITLAB_RB_PATH}", hide=True)
                    log.info("Backup restored.")
                except Exception as restore_e:
                    log.error(f"!!! CRITICAL: Failed to restore backup: {restore_e}. Manual intervention required on {host} !!!")
            return False
        finally:
            remote_stream.close()


        # --- 5. Run Reconfigure (Optional) ---
        if run_reconfigure:
            log.info("Running 'gitlab-ctl reconfigure'...")
            try:
                # Capture=True might be useful for detailed logging/debugging
                result = conn.sudo("gitlab-ctl reconfigure", hide=False, warn=True, pty=True) 
                if result.ok:
                    log.info("'gitlab-ctl reconfigure' completed successfully.")
                else:
                    log.error(f"'gitlab-ctl reconfigure' failed with exit code {result.exited}.")
                    # Consider the operation failed even if the file was uploaded
                    return False 
            except UnexpectedExit as e:
                log.error(f"Failed to run 'gitlab-ctl reconfigure': {e}")
                return False

        log.info(f"Successfully modified '{setting_key}' on {host}.")
        return True

    except Exception as e:
        log.error(f"An error occurred during the operation on {host}: {e}")
        return False
    finally:
        if conn.is_connected:
            log.info("Closing connection.")
            conn.close()