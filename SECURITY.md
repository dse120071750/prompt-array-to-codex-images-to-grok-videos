# Security policy

Please report a suspected vulnerability privately to the repository owner
instead of opening a public issue with credentials, ACP transcripts, generated
media, or run artifacts.

Never commit:

- Grok cached tokens or `~/.grok/managed_config.toml`;
- cloud storage credentials;
- API keys, `.env` files, or browser session data;
- `flowsteps/runs/`, ACP transcripts, or generated media.

The workflow removes `XAI_API_KEY` from the Grok Build subprocess environment
and authenticates only through Grok Build's cached-login ACP method.
