# GitLab Helper CLI

A command-line utility built with Python, Click, and Poetry to assist with managing GitLab self-managed installations, particularly around configuration changes often needed during upgrades.

**Note:** This tool modifies configuration files and executes commands remotely via SSH. Use with caution and ensure you understand the changes being made. Always have backups and test in a non-production environment first.

## Features

* **Remote Configuration Editing:** Modify specific settings in `/etc/gitlab/gitlab.rb` remotely.
* **Template-Based Configuration:** Apply a full `/etc/gitlab/gitlab.rb` configuration generated from a Jinja2 template and a YAML variables file.
* **SSH Key Authentication:** Uses PEM keys for secure SSH connections.
* **Optional Backups:** Automatically create timestamped backups of `/etc/gitlab/gitlab.rb` before making changes.
* **Optional Reconfigure:** Automatically trigger `gitlab-ctl reconfigure` after applying changes.

## Prerequisites

* Python 3.8+
* Poetry (for installation and dependency management)
* SSH access to the target GitLab server(s).
* An SSH private key (PEM format) authorized to access the server as the specified user (often `root` or a user with passwordless `sudo` privileges).
* Network connectivity between the machine running the CLI and the GitLab server(s) on the SSH port (default 22).

## Installation

1.  Clone this repository (or create the project structure).
2.  Navigate to the project directory in your terminal.
3.  Install dependencies using Poetry:
    ```bash
    poetry install
    ```
    This creates a virtual environment and installs `click`, `fabric`, `pyyaml`, and `jinja2`.

## Configuration

### SSH Access

* Ensure the user specified via the `--user` option (defaults to `root`) can log in to the target GitLab server using the provided `--key-file`.
* The tool uses `sudo` to modify `/etc/gitlab/gitlab.rb`, create backups in `/etc/gitlab/`, move temporary files, and run `gitlab-ctl reconfigure`. The specified SSH user **must** have passwordless `sudo` privileges for these actions to work seamlessly. Configure `/etc/sudoers` on the target server accordingly if needed.

## Usage

### General

All commands are run through the Poetry environment:

```bash
poetry run gitlab-helper [COMMAND] [OPTIONS]
poetry run gitlab-helper --help
poetry run gitlab-helper set-config --help
poetry run gitlab-helper apply-template --help
```


set-config Command
Modifies a single, simple setting in the remote /etc/gitlab/gitlab.rb file. It searches for the setting key (commented or uncommented) and replaces the line, or appends the setting if not found.

Note: This command is best suited for simple key-value pairs (like external_url, unicorn['worker_processes']). It is not reliable for modifying complex Ruby structures like Hashes or Arrays within the file. Use apply-template for comprehensive changes.

Arguments
--host TEXT: (Required) IP address or hostname of the GitLab server.
--key-file PATH: (Required) Path to the SSH private key (PEM) file.
--setting TEXT: (Required) The gitlab.rb setting key (e.g., 'external_url', "gitlab_rails['some_setting']").
--value TEXT: (Required) The new value for the setting. IMPORTANT: Use valid Ruby syntax (e.g., strings require quotes: 'http://new.url', numbers don't: 123, booleans are true/false).
--user TEXT: SSH username (Default: root).
--port INTEGER: SSH port (Default: 22).
--backup / --no-backup: Create a backup before modifying (Default: --backup).
--reconfigure / --no-reconfigure: Run 'gitlab-ctl reconfigure' after modification (Default: --no-reconfigure).

# Examples

## Change the external URL and run reconfigure

```bash
poetry run gitlab-helper set-config \
    --host gitlab.example.com \
    --key-file ~/.ssh/gitlab_admin_id_rsa \
    --setting external_url \
    --value "'[https://gitlab.newdomain.com](https://gitlab.newdomain.com)'" \
    --user admin \
    --backup \
    --reconfigure
```

## Change the number of Unicorn workers, no reconfigure yet

``` bash
poetry run gitlab-helper set-config \
    --host 10.0.1.5 \
    --key-file /etc/ssh/keys/gitlab_prod.pem \
    --setting unicorn['worker_processes'] \
    --value "4" \
    --no-reconfigure
```
apply-template Command
Applies a Jinja2 template to generate the entire /etc/gitlab/gitlab.rb content and replaces the remote file. This is the recommended method for managing the full configuration robustly.

Arguments
--host TEXT: (Required) IP address or hostname of the GitLab server.
--key-file PATH: (Required) Path to the SSH private key (PEM) file.
--template PATH: (Required) Path to the Jinja2 template file (e.g., templates/gitlab.rb.j2).
--vars PATH: (Required) Path to the YAML file with variables for the template (e.g., config/production.yaml).
--user TEXT: SSH username (Default: root).
--port INTEGER: SSH port (Default: 22).
--backup / --no-backup: Create a backup before replacing gitlab.rb (Default: --backup).
--reconfigure / --no-reconfigure: Run 'gitlab-ctl reconfigure' after applying the template (Default: --no-reconfigure).
Template and Variables Files
This command relies on two input files:

Template (--template): A standard Jinja2 template file (conventionally ending in .j2). You define your desired gitlab.rb structure here, using Jinja2 variables, loops, conditionals, etc.

Example (templates/gitlab.rb.j2 snippet):

Django

```Jinja2
# Generated on {{ ansible_date_time.iso8601 }} by gitlab-helper apply-template
external_url '{{ gitlab_external_url }}'

{% if ldap_enabled %}
gitlab_rails['ldap_enabled'] = true
gitlab_rails['ldap_servers'] = {{ ldap_servers | to_nice_yaml | indent(2) }}
{% else %}
gitlab_rails['ldap_enabled'] = false
{% endif %}

unicorn['worker_processes'] = {{ unicorn_workers | default(2) }}
(Note: to_nice_yaml is a filter you might need to define or import if using complex structures)
```

Variables (--vars): A YAML file containing key-value pairs that correspond to the variables used in your Jinja2 template. This allows you to separate environment-specific settings from the main configuration structure.

Example (config/production.yaml snippet):


``` yaml
gitlab_external_url: '[https://gitlab.mycompany.com](https://www.google.com/search?q=https://gitlab.mycompany.com)'
unicorn_workers: 4
ldap_enabled: true
ldap_servers:
  main: # This key should match expected structure in gitlab.rb
    label: 'My LDAP'
    host: '[ldap.mycompany.com](https://www.google.com/search?q=ldap.mycompany.com)'
    port: 636
    uid: 'sAMAccountName'
    bind_dn: 'cn=gitlab-binder,ou=Service Accounts,dc=mycompany,dc=com'
    password: 'very_secret_password' # Consider using secrets management!
    encryption: 'simple_tls' # 'start_tls', 'simple_tls' or 'plain'
    verify_certificates: true
    base: 'ou=Users,dc=mycompany,dc=com'
```

# Examples

## Apply production configuration from template and vars files, then reconfigure
poetry run gitlab-helper apply-template \
    --host gitlab.prod.internal \
    --key-file ~/.ssh/id_rsa_prod \
    --template templates/base_gitlab.rb.j2 \
    --vars config/prod_vars.yaml \
    --user deployer \
    --backup \
    --reconfigure

## Apply staging configuration without running reconfigure immediately
poetry run gitlab-helper apply-template \
    --host gitlab.staging.internal \
    --key-file ~/.ssh/id_rsa_staging \
    --template templates/base_gitlab.rb.j2 \
    --vars config/staging_vars.yaml \
    --no-reconfigure

## Important Considerations
Security: Protect your SSH private keys. Ensure they have strict file permissions (e.g., chmod 400 or 600). Avoid storing sensitive data like passwords directly in YAML variables files if possible; consider environment variables or dedicated secrets management tools.
Sudo: Passwordless sudo is generally required for the SSH user on the target machine for modifying /etc/gitlab/gitlab.rb, moving temporary files, creating backups in standard locations, and running gitlab-ctl reconfigure.
Backups: While the tool offers a backup option (--backup), this only creates a single timestamped copy of /etc/gitlab/gitlab.rb just before modification. Maintain your own independent GitLab instance backup strategy (application data, database, config files, secrets).
Idempotency:
The apply-template command is generally idempotent (running it multiple times with the same inputs yields the same gitlab.rb content).
The set-config command attempts to be idempotent for simple settings found in the file but may not be fully idempotent, especially if the setting is not found initially (it will be appended on each run).
Error Handling: If an operation fails (especially during file upload or gitlab-ctl reconfigure), the GitLab instance might be left in an inconsistent state. Check the tool's output/logs and the relevant GitLab server logs (e.g., sudo gitlab-ctl status, /var/log/gitlab/...). Manual intervention may be required. If backups were enabled (--backup), the tool attempts to restore the previous gitlab.rb if the upload step fails.
Testing: Test configuration changes thoroughly in a non-production (staging) environment before applying them to production systems. Verify GitLab functionality after running gitlab-ctl reconfigure.
gitlab.rb Complexity: The gitlab.rb file is Ruby code. Ensure values provided via set-config or generated by templates are valid Ruby syntax. Incorrect syntax will cause gitlab-ctl reconfigure to fail.

# Development
(Example commands for development tasks)

## Format code with Black
poetry run black .

## Lint code with Ruff
poetry run ruff check .
poetry run ruff format . # If using Ruff for formatting

## Run tests (assuming pytest is configured)
poetry run pytest -v tests/
License
(Specify your project's license here, e.g., MIT License, Apache 2.0)