# In your main CLI file, e.g., cli.py or gitlab_helper_cli.py
import os
import click
from src.gitlab_upgrade_helper.config import modify_gitlab_rb_setting, apply_gitlab_rb_template, render_template_locally

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
@click.option('--host', help='IP address or hostname of the GitLab server (Required unless --render-only).')
@click.option('--key-file', type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the SSH private key (PEM) file (Required unless --render-only).')
@click.option('--template', required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the Jinja2 template file for gitlab.rb.')
@click.option('--vars', required=True, type=click.Path(exists=True, dir_okay=False, resolve_path=True), help='Path to the YAML file with variables for the template.')
@click.option('--render-only', is_flag=True, default=False, help='Render template locally and print to stdout; skip remote connection.')
@click.option('--result-file', type=click.Path(dir_okay=False, resolve_path=True), help='Path to save the rendered output (only used with --render-only).')
@click.option('--user', default='root', show_default=True, help='SSH username (Ignored if --render-only).')
@click.option('--port', default=22, show_default=True, help='SSH port (Ignored if --render-only).')
@click.option('--backup/--no-backup', default=True, show_default=True, help='Create backup before replacing gitlab.rb (Ignored if --render-only).')
@click.option('--reconfigure/--no-reconfigure', default=False, show_default=True, help="Run 'gitlab-ctl reconfigure' after applying template (Ignored if --render-only).")
@click.pass_context # Needed to exit contextually
def apply_template_cmd(ctx, host, key_file, template, vars, render_only, result_file, user, port, backup, reconfigure):
    """
    Applies a Jinja2 template to generate/replace /etc/gitlab/gitlab.rb.
    Can also render the template locally to stdout using --render-only.
    
    Example:

    poetry run gitlab-helper apply-template \
        --host gitlab.prod.internal \
        --key-file ~/.ssh/id_rsa_prod \
        --template templates/base_gitlab.rb.j2 \
        --vars config/prod_vars.yaml \
        --backup \
        --reconfigure
    """
    
    if render_only:
        # --- Render Only Mode ---
        if host or key_file:
             click.echo("Warning: --host and --key-file are not needed and ignored with --render-only.", err=True)
        # Optional: Warn about other ignored flags if they differ from defaults
        if user != 'root' or port != 22 or not backup or reconfigure:
             click.echo("Warning: --user, --port, --backup, --reconfigure flags are ignored with --render-only.", err=True)
             
        click.echo(f"Rendering template '{template}' with vars '{vars}' locally...")
        rendered_output = render_template_locally(template_file=template, vars_file=vars)
        # Indicate success for render-only explicitly if needed, or just exit 0
        click.secho("Local rendering successful.", fg='green') 
        if rendered_output:
            # Check if result_file is provided and save the rendered output
            if result_file:
                try:
                    with open(result_file, 'w') as f:
                        f.write(rendered_output)
                    click.secho(f"Rendered output saved to {result_file}.", fg='green')
                except IOError as e:
                    click.secho(f"Error saving rendered output: {e}", fg='red', err=True)
                    ctx.exit(1)
            else:
                click.echo("\n--- Rendered gitlab.rb Content ---")
                click.echo(rendered_output)
                click.echo("--- End Rendered Content ---")
        else:
            click.secho("Failed to render template locally. Check logs above.", fg='red', err=True)
            ctx.exit(1) # Exit with error code

    else:
        # --- Apply Remotely Mode ---
        # Validate required options for remote mode
        if not host:
            raise click.UsageError("Missing option '--host'. Required unless --render-only is used.")
        if not key_file:
            # Check existence again here, as Click's check might be bypassed if initially None
            if not os.path.exists(key_file):
                 raise click.BadParameter(f"Path '{key_file}' for --key-file does not exist.", param_hint='--key-file')
            # raise click.UsageError("Missing option '--key-file'. Required unless --render-only is used.") # Redundant if BadParameter works
        
        click.echo(f"Attempting to apply template '{template}' with vars '{vars}' to remote host {host}...")
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
            click.secho("Remote operation completed successfully.", fg='green')
        else:
            click.secho("Remote operation failed. Check logs for details.", fg='red', err=True)
            ctx.exit(1) # Exit with error code

if __name__ == '__main__':
    cli()