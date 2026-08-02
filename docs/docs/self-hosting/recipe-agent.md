# Recipe Agent

KitchenOwl can connect to a Large Language Model (LLM) so users can chat about
ideas and let the agent create complete recipes (name, description, yields,
prep/cook time, ingredients, tags) directly in their household.

The feature is **opt-in per household**: an admin configures the provider and
API key, then any chat the user starts can call KitchenOwl's existing
recipe / item / tag tools.

## Supported providers

The agent talks to any **OpenAI-compatible chat completions** endpoint, so it
supports out of the box:

| Provider | Base URL | Notes |
|----------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | Default. Use models like `gpt-4o-mini`. |
| Google Gemini | _(empty — uses the native `gemini/` route)_ | Pick `Gemini` as provider and a model name like `gemini-1.5-flash`. |
| Ollama (self-hosted) | `http://localhost:11434/v1` | Pick `Custom`, set the URL, model = your pulled model (e.g. `llama3.1`). |
| OpenRouter / vLLM / LM Studio | as documented by the service | Pick `Custom`. |

## Configuration

Open **More → Recipe Agent → Settings** (admin only) and enter:

- **Provider**: `OpenAI`, `Google Gemini` or `Custom`.
- **Base URL**: optional; leave blank to use the provider default.
- **Model**: required. Examples: `gpt-4o-mini`, `gemini-1.5-flash`, `llama3.1`.
- **API key**: stored encrypted at rest.
- **System prompt**: optional. Use this to tell the agent about diets,
  allergies, preferred cuisines, etc.
- **Enable agent**: turns the menu entry on.

Use **Test connection** to verify the credentials before going live.

## Server-side environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_ENCRYPTION_KEY` | _(derived from `JWT_SECRET_KEY`)_ | Fernet key (url-safe base64, 32 bytes) used to encrypt stored API keys. **Set this explicitly in production**, otherwise rotating `JWT_SECRET_KEY` will make stored keys unreadable. |
| `LLM_ALLOWED_HOSTS` | _(unset)_ | Optional comma-separated allowlist of hostnames the server may contact for LLM calls (e.g. `api.openai.com,generativelanguage.googleapis.com`). When unset, no allowlist is enforced. |

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Security notes

- API keys are encrypted at rest with `cryptography.fernet` and **never**
  returned to the client. The settings page shows only whether a key is set.
- Only household **admins** can read or change the configuration. Members
  can use the agent.
- Each agent chat is private to the user that started it.
- Every tool call runs as the calling user; it cannot reach data outside the
  household, because all KitchenOwl tools enforce household membership.
- Set `LLM_ALLOWED_HOSTS` if you want to prevent the server from being used as
  an outbound proxy to arbitrary HTTP endpoints.
