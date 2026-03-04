# GCP Caddy Reverse Proxy Instructions

To expose the Dockerized Name Matcher service behind your domain (`evgenyk.dev/name_matcher`), you will need to add the following block to your GCP instance's `Caddyfile`.

```caddyfile
evgenyk.dev {
    # ... your existing configuration ...

    # -----------------------------------------
    # Name Matcher Engine Reverse Proxy
    # -----------------------------------------
    handle_path /name_matcher* {
        reverse_proxy localhost:8000
    }
}
```

### Explanation:
*   `handle_path /name_matcher*`: This directive intercepts any traffic heading to `evgenyk.dev/name_matcher`. Crucially, it **strips** the `/name_matcher` prefix before passing the request upstream.
*   `reverse_proxy localhost:8000`: This forwards the stripped request directly to the Docker container we bound to port 8000. 

Because we configured `app.py` to use `ROOT_PATH=/name_matcher` and changed all frontend assets to load from relative URIs (e.g., `src="static/main.js"` instead of `src="/static/main.js"`), the application will seamlessly boot in this sub-directory architecture while thinking it is running at the root.

### Deployment Steps:
1. Pull your code to the GCP VM.
2. Run `docker-compose up -d --build`.
3. Paste the Caddy configuration above into `/etc/caddy/Caddyfile` (or wherever your Caddyfile resides).
4. Reload Caddy: `caddy reload --config /etc/caddy/Caddyfile`.
