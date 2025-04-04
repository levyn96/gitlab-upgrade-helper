# In your main CLI file, e.g., cli.py or gitlab_helper_cli.py

import click
from src.gitlab_upgrade_helper.config import modify_gitlab_rb_setting # Assuming the function is in this path

@click.group()
def cli():
    """GitLab Self-Managed Helper CLI."""
    pass

@cli.command("set-config")
@click.option('--host', required=True, help='IP address or hostname of the GitLab server.')
@click.option('--key-file', required=True, type=click.Path(exists=True, dir_okay=False), help='Path to the SSH private key (PEM) file.')
@click.option('--setting', required=True, help="The gitlab.rb setting key (e.g., 'external_url').")
@click.option('--value', required=True, help="The new value for the setting. IMPORTANT: Use Ruby syntax (e.g., \"'http://new.url'\", \"123\", \"true\").")
@click.option('--user', default='root', show_default=True, help='SSH username.')
@click.option('--port', default=22, show_default=True, help='SSH port.')
@click.option('--backup/--no-backup', default=True, show_default=True, help='Create a backup before modifying.')
@click.option('--reconfigure/--no-reconfigure', default=False, show_default=True, help="Run 'gitlab-ctl reconfigure' after modification.")
def set_config(host, key_file, setting, value, user, port, backup, reconfigure):
    """
    Modifies a single setting in the remote /etc/gitlab/gitlab.rb file.
    
    Example:
    
    poetry run python cli.py set-config --host 1.2.3.4 --key-file ~/.ssh/id_rsa --setting external_url --value "'http://gitlab.mynewdomain.com'" --reconfigure
    """
    click.echo(f"Attempting to set '{setting}' to '{value}' on {host}...")

    success = modify_gitlab_rb_setting(
        host=host,
        key_filename=key_file,
        setting_key=setting,
        setting_value=value,
        ssh_user=user,
        ssh_port=port,
        create_backup=backup,
        run_reconfigure=reconfigure,
    )

    if success:
        click.secho("Operation completed successfully.", fg='green')
    else:
        click.secho("Operation failed. Check logs for details.", fg='red')
        # Exit with a non-zero code to indicate failure in scripts
        ctx = click.get_current_context()
        ctx.exit(1)


if __name__ == '__main__':
    cli()