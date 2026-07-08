# Security Policy

## Security Warning - Unauthenticated Control Plane

> [!WARNING]
> **Development only**: This repository contains an unauthenticated crawl control plane interface. Do not expose the user interface or its API endpoints to an untrusted local area network (LAN) or the public internet.

The management interface and APIs (`/api/control/*`) do not perform authentication or authorization. They are designed for local development and execution on a trusted machine only. 

If you must access the control plane or UI remotely, secure it using a reverse proxy (e.g. Nginx, Caddy) with basic auth/OAuth or via an SSH tunnel / VPN.
