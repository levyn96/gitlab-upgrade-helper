# In your main CLI file, e.g., cli.py or gitlab_helper_cli.py

import click
from src.gitlab_upgrade_helper.config import modify_gitlab_rb_setting, apply_gitlab_rb_template # Assuming the function is in this path

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

@cli.command("apply-template")
@click.option('--host', required=True, help='IP address or hostname of the GitLab server.')
@click.option('--key-file', required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the SSH private key (PEM) file.')
@click.option('--template', required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the Jinja2 template file for gitlab.rb.')
@click.option('--vars', required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the YAML file with variables for the template.')
@click.option('--user', default='root', show_default=True, help='SSH username.')
@click.option('--port', default=22, show_default=True, help='SSH port.')
@click.option('--backup/--no-backup', default=True, show_default=True, help='Create a backup before replacing gitlab.rb.')
@click.option('--reconfigure/--no-reconfigure', default=False, show_default=True, help="Run 'gitlab-ctl reconfigure' after applying the template.")
def apply_template_cmd(host, key_file, template, vars, user, port, backup, reconfigure):
    """
    Applies a Jinja2 template to generate and replace /etc/gitlab/gitlab.rb.
    
    Example:

    poetry run gitlab-helper apply-template --host 1.2.3.4 \\
        --key-file ~/.ssh/id_rsa \\
        --template templates/gitlab.rb.j2 \\
        --vars config/production.yaml \\
        --reconfigure
    """
    click.echo(f"Attempting to apply template '{template}' with vars '{vars}' to {host}...")
    
    success = apply_gitlab_rb_template(
        host=host,
        key_filename=key_file,
        template_file=template,
        vars_file=vars,
        ssh_user=user,
        ssh_port=port,
        create_backup=backup,
        run_reconfigure=reconfigure,
    )

    if success:
        click.secho("Operation completed successfully.", fg='green')
    else:
        click.secho("Operation failed. Check logs for details.", fg='red')
        ctx = click.get_current_context()
        ctx.exit(1)

if __name__ == '__main__':
    cli()