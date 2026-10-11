# Claude.ai integration findings

Research date: October 10, 2026. **Status, later that day:** `mcp_server.py`
implements the advocate over MCP (stdio, and `/mcp` streamable HTTP in
`cloud_app.py` behind the UCSC login or a student bearer). It exposes the
advocate's tools (`ask`, `my_box`, `approve_share`, `open_items`), not the raw
memory tools below; the OAuth-for-connectors flow described here is still open.
The cloud app also exposes A2A. Claude.ai does not automatically speak A2A
to an arbitrary service, and its code sandbox may block a Cloud Run hostname.

## Supported route

Expose the same permissioned memory tools through a thin **remote MCP** adapter
at `/mcp`, using the official Python MCP SDK and stateless Streamable HTTP.
Claude's connector infrastructure makes these requests independently of the
code-execution sandbox's egress settings. Do not relay private data through
public proxy services or attempt to evade sandbox controls.

Custom connectors are documented for Free, Pro, Max, Team, and Enterprise.
Free permits one. Team/Enterprise setup may require owner/admin approval.
Verify the particular account's controls rather than promise availability.

## Authentication choices

- Some organizations have beta support for static request headers. If exposed
  in the account, a per-user `Authorization: Bearer ...` connector can reuse the
  existing 48-hour capability. Never make a student's token an organization-wide
  shared header.
- General users need an MCP OAuth authorization-code flow with S256 PKCE.
  Google's website login is upstream authentication, not the MCP OAuth server.
  Reuse scoped identity/permissions behind an explicit connector authorization
  step. Outside advisors should retain their contribution-only capability.
- MCP-derived credentials must expire no later than the underlying capability
  and stop working immediately when the student rotates or revokes access.
- Persist authorization codes/token mappings in Firestore, not process memory.
  Codes must be short-lived and single-use, with exact redirect validation,
  resource/audience binding, CSRF protection, and form-urlencoded token exchange.

## Minimal adapter contract

Use the same `run_tool()` permission checks, not a second security policy or an
HTTP loop back through A2A. Authenticate every call and use request-local identity.

- Student: `hello`, `read`, `remember(text)`.
- Advisor: `hello`, `contribute(text)`.
- Role-filter tool discovery, but also enforce permissions during invocation.
- Explain Gremlin through MCP server instructions, tool descriptions, and hello.
- Treat stored text as data, never instructions. No implicit outbound disclosure.
- Bound/paginate read results: the current maximum notebook could exceed Claude's
  roughly 150,000-character hosted tool-result limit.
- Implement SDK lifecycle and initialization notifications correctly. Keep the
  transport stateless so Cloud Run restarts/multiple instances work.

## Acceptance test

From an actual Claude.ai conversation: hello, remember synthetic information,
read it in a second conversation, deny advisor reading, revoke the credential,
then verify access fails. A connected badge alone is not a sufficient test.

## Sources

- [Add custom connectors](https://claude.com/docs/connectors/custom/add-unlisted)
- [Plans and admin rules](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Connector server support and limits](https://claude.com/docs/connectors/building)
- [Connector OAuth requirements](https://claude.com/docs/connectors/building/authentication)
- [Sandbox network controls and MCP exception](https://support.claude.com/en/articles/12111783-creating-and-editing-files-with-claude)
- [Cloud Run MCP hosting](https://docs.cloud.google.com/run/docs/host-mcp-servers)
