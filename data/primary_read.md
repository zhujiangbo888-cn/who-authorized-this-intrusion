# Primary documents retrieved at origin

The block on these documents is on the machine's direct route, not on the documents themselves.
Both were retrieved through a local proxy after the first coding pass and used to re-verify every
relay-carried claim (Appendix E of the report). Hashes are given so a reader can confirm they are
looking at the same text.

| Document | URL | Retrieved (UTC) | SHA-256 |
|---|---|---|---|
| `HF_技术时间线_原文_2026.md` | https://huggingface.co/blog/agent-intrusion-technical-timeline | 2026-09-13 01:30 UTC | `94fb14df8c97104de79fa113f0fc7ea9a31ce5d6fe1fca2d11cb25d29de6bd74` |
| `HF_事件披露_原文_2026-07.md` | https://huggingface.co/blog/security-incident-july-2026 | 2026-09-13 01:30 UTC | `b8518d8fbee7f49a7b2f77395201c173b2e7a83059381add73a651d3a7388389` |

## What the re-verification changed

15 claim rows first coded through Vectra's relay of the Hugging Face timeline, or from Vectra's own
commentary, were checked line by line against the primary text.

- **13 confirmed exactly as coded.**
- **2 adjusted:** T4-08 (the relay's "~1 hour" reconstruction figure is not in the primary, which says
  "in hours") and T8-02 (the primary states the customer-data assessment was still open at disclosure;
  the later timeline records five customer datasets read).
- **0 conflict codes changed**, so no divergence rate, table or figure in the report moved.
- The verifiability mix improved: verifiable 32 (64.0%) / partially verifiable 5 (10.0%) / unverifiable 13 (26.0%).

The relay itself was faithful on every substantive technical claim it carried.
