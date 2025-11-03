# Security Policy

[English](SECURITY.md) | [Русский](SECURITY.ru.md)

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Best Practices

### API Keys
- Store API keys only in the `.env` file
- `.env` is included in `.gitignore` and not committed to the repo
- Use `.env.example` as a template
- Never commit real API keys

### Docker Security
- Container runs as a non-root user
- Minimal privileges (cap_drop: ALL)
- Read-only filesystem
- Resource limits (CPU/Memory)
- Regular vulnerability scanning via CI/CD

### Runtime Security
- Only HTTPS/WSS is used to connect to Bybit
- Basic input validation (safe_float functions)
- Exception handling
- Logging for auditability

## Reporting a Vulnerability

If you discover a security vulnerability:

1. Do NOT open a public issue
2. Send an email to: [your email] or create a GitHub Security Advisory
3. Provide a detailed description of the vulnerability
4. Include reproduction steps if possible

We will respond within 48 hours and provide updates until the issue is resolved.

## Automated Security Checks

This project uses the following tools for automated security checks:

- Bandit: static security analysis for Python code
- Safety: dependency vulnerability checks
- pip-audit: audit of Python packages
- Trivy: container image vulnerability scanning
- Docker Scout: Docker image security analysis
- Hadolint: Dockerfile best practices linter

All checks are run automatically via GitHub Actions on each push.


