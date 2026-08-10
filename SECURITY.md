# Security policy

## Scope

The repository contains two different surfaces:

- the crawler/control plane, which is an operator tool intended for a trusted local machine; and
- the read-only Career Atlas API and frontend, which publish a deliberately limited projection of an approved snapshot.

Read [`work/geds-crawler/SECURITY.md`](work/geds-crawler/SECURITY.md) before running or exposing the control plane. Do not bind it to an untrusted LAN or the public internet. Do not treat Basic Auth, if configured, as a substitute for TLS.

## Reporting a vulnerability

Please do not open a public issue for an exploitable vulnerability. Use GitHub's private vulnerability reporting for [aselekoglu/geds-explorer](https://github.com/aselekoglu/geds-explorer/security/advisories/new), if available, or contact the repository maintainer through the private channel configured for the repository. Include:

- affected commit, package, route, or command;
- reproduction steps and impact;
- logs or requests with credentials and personal data removed; and
- a suggested mitigation, if known.

We will acknowledge receipt when possible, investigate within the repository's capacity, and coordinate disclosure after a fix or mitigation is available. This project follows responsible disclosure: test only systems/data you are authorized to test, minimize personal data, and allow triage time before public disclosure. Please avoid testing against live services or data you do not own.

Government of Canada reference guidance: [Online security and privacy](https://www.canada.ca/en/government/system/digital-government/online-security-privacy.html) and [Canadian Centre for Cyber Security guidance](https://www.cyber.gc.ca/en/guidance). This is not a compliance or certification claim.

## Data handling

Do not report or attach raw snapshots containing personal contact fields. The project intentionally excludes phone, email, fax, and address fields from stored person records and public projections.
