# Security policy

## Supported versions

Security fixes go into `main` and into the next release. Older releases are not patched, so
please update to the latest release before you report a problem.

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Report it privately through GitHub instead: open the repository's **Security** tab and
choose **Report a vulnerability**. Only the maintainers can read the report.

Please include:

- what the problem is and what an attacker could do with it;
- the steps or a proof of concept that reproduces it;
- the commit or release you tested.

We will confirm that we received your report within five working days, and tell you what we
plan to do. When the fix is released, we credit you in the security advisory, unless you
would rather not be named.

## Scope

Styx is a single-user application. By default its web server listens only on `127.0.0.1`.
The launcher's `--host` option can make it reachable from a network, but the app is not
built for that. These are in scope, for example:

- a way for a project file, an imported mesh, or a Python script opened with `run` to do
  something the user did not ask for. This does not cover a script the user wrote and
  chose to run;
- a way for a web page in the same browser to reach the local server;
- a vulnerable dependency that the app actually uses.

A problem in Kratos Multiphysics or Gmsh themselves belongs to those projects. If you are
not sure whether it is ours, report it here and we will forward it.
