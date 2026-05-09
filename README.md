# adola

Python SDK for the Adola compression API.

```bash
pip install git+https://github.com/JBunga/adola-python.git
```

```python
from adola import Adola

client = Adola(api_key="adola_...")
result = client.compress(
    input="Adola compresses long prompts before they reach your model.",
    query="What does Adola do?",
    compression={"target_ratio": 0.4},
)

print(result["output"])
print(result["receipt"]["tokens_saved"])
```

The client defaults to `https://api.adola.app`. Set `ADOLA_API_KEY` for auth and `ADOLA_BASE_URL` for local testing.

The repository contains only the SDK client and does not include the Adola application codebase.
