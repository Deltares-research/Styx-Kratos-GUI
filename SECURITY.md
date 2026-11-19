# Security policy

This page tells you how to report a security problem in Styx, and which problems are in
scope.

> [!IMPORTANT]
> Do not open a public issue for a security problem. Report it privately, as this page
> tells you.

## Report a vulnerability

1. On GitHub, open the **Security** tab of the repository.
2. Select **Report a vulnerability**.
3. In the form, give:
   - what the problem is, and what an attacker can do with it;
   - the steps or a proof of concept that make the problem occur;
   - the version that you tested: **Help > About** in the GUI, or `kratos-cli --version`.
4. Submit the report.

Only you and the maintainers of the repository can read the report.

## What happens after you report

The maintainers confirm that they received your report within five working days. They also
tell you what they plan to do. When the fix is released, the security advisory gives your
name, unless you ask them not to name you.

## Supported versions

Security fixes go into `main` and into the next release. Older releases do not get fixes.
Before you report, check that the problem also occurs on `main` or in the latest release.

## What Styx is built for

Styx is an application for one user on their own computer. Know these facts before you
decide if a problem is in scope:

- The server has no login. By default it listens only on `127.0.0.1`, so only your own
  computer can reach it.
- The server refuses a request with an unknown host name in its `Host` header. This stops
  DNS rebinding: a different site that makes its own name point to `127.0.0.1`.
- The server refuses a request from a page that it did not serve (a different `Origin`).
- The `run <file.py>` command of the GUI, and `kratos-cli` when it opens a model script,
  run that Python file with your user permissions. This is the purpose of a model script.

## In scope

- A file that Styx opens or imports, and that makes Styx do something that the user did not
  ask for: for example, run code or write a file outside the folders of Styx. Such files
  are project files, meshes (`.mdpa`), geometry files (`.step`, `.iges`, `.brep`, `.stl`,
  `.obj`) and Kratos decks.
- A way for a web page in the same browser to use the local server, past the `Host` or
  `Origin` check.
- A known vulnerability in a package that Styx uses, or in the copy of three.js in
  `frontend/vendor/`.

## Out of scope

- A model script that you wrote, or that you chose to run. Styx runs it like any other
  Python file.
- Access by other people when you start the server on a network address with `--host`.
  The server has no login, and [INSTALLATION.md](docs/INSTALLATION.md#launcher-options)
  warns about this.
- A problem in Kratos Multiphysics or in Gmsh. Report it to that project. If you do not know
  whether the problem is in Styx, report it here, and the maintainers send it on.

## For maintainers

The **Report a vulnerability** button shows only when private vulnerability reporting is
on. To switch it on, go to the **Settings** of the repository, open the security part of
the side bar, and select **Enable** for **Private vulnerability reporting**.
