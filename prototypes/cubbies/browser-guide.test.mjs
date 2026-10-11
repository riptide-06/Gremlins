// Exercise the canonical documentation, not a second client implementation.
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {runInNewContext} from 'node:vm';

const guide = readFileSync(new URL('./SKILL.md', import.meta.url), 'utf8');
const snippets = [...guide.matchAll(/```javascript\n([\s\S]*?)\n```/g)].map(m => m[1]);
const origin = 'https://cubby.bayleaf.dev';
const deviceSecret = 'PRIVATE_DEVICE', token = 'PRIVATE_BEARER';

function runtime(replies = []) {
  let clock = 100000, calls = [];
  const context = {
    window: {}, location: {origin}, URL, URLSearchParams,
    Date: {now: () => clock}, AbortSignal,
    crypto: {randomUUID: () => 'fresh-' + calls.length},
    setTimeout: (resolve, delay) => { clock += delay; resolve(); },
    fetch: async (url, options) => {
      calls.push({url, options, clock});
      assert.equal(options.credentials, 'omit');
      assert.equal(options.redirect, 'error');
      assert.equal(options.cache, 'no-store');
      assert.ok(options.signal);
      let status = 200, body;
      if (url.endsWith('/agent-card.json')) body = {supportedInterfaces: [
        {url: origin + '/a2a', protocolBinding: 'JSONRPC', protocolVersion: '1.0'}]};
      else if (url.endsWith('/auth/device')) body = {device_code: deviceSecret,
        user_code: 'PUBLIC_CODE', verification_uri: origin + '/connect',
        verification_uri_complete: origin + '/connect?code=PUBLIC_CODE', interval: 5, expires_in: 600};
      else if (url.endsWith('/auth/token')) {
        assert.equal(options.headers['Content-Type'], 'application/x-www-form-urlencoded');
        assert.equal(options.body.get('device_code'), deviceSecret);
        assert.equal(options.body.get('user_code'), 'PUBLIC_CODE');
        const reply = replies.shift() || [400, {error: 'authorization_pending'}];
        if (reply instanceof Error) throw reply;
        [status, body] = reply;
      } else {
        assert.equal(url, origin + '/a2a');
        assert.equal(options.headers['A2A-Version'], '1.0');
        assert.equal(options.headers.Authorization, 'Bearer ' + token);
        const envelope = JSON.parse(options.body);
        assert.equal(envelope.method, 'SendMessage');
        assert.equal(envelope.jsonrpc, '2.0');
        assert.equal(envelope.params.message.role, 'ROLE_USER');
        body = {result: {message: {parts: [{text: JSON.stringify({ok: true,
          tool: JSON.parse(envelope.params.message.parts[0].text)})}]}}};
      }
      return {status, json: async () => body};
    }
  };
  const evaluate = async code => {
    const result = await runInNewContext(code, context);
    assert.doesNotMatch(JSON.stringify(result), /PRIVATE_DEVICE|PRIVATE_BEARER/);
    return result;
  };
  return {context, calls, evaluate, advance: n => { clock += n; }};
}

test('served guide browser sequence discovers, pairs, polls once, then uses canonical A2A', async () => {
  assert.equal(snippets.length, 3);
  const r = runtime([[400, {error: 'authorization_pending'}], [400, {error: 'slow_down'}],
    [503, {}], [200, {token_type: 'Bearer', access_token: token, expires_in: 172800}]]);
  const start = await r.evaluate(snippets[0]);
  assert.equal(start.approvalURL, origin + '/connect?code=PUBLIC_CODE');
  assert.equal((await r.evaluate(snippets[1])).status, 'Awaiting human approval');
  assert.equal(r.calls.at(-1).clock, 105000);
  await r.evaluate(snippets[1]);
  assert.equal(r.calls.at(-1).clock, 110000);
  await r.evaluate(snippets[1]);
  assert.equal(r.calls.at(-1).clock, 120000);
  assert.equal((await r.evaluate(snippets[1])).status, 'Connected');
  assert.equal(r.calls.at(-1).clock, 135000);
  const count = r.calls.length;
  await r.evaluate(snippets[1]);
  assert.equal(r.calls.length, count); // No second exchange after success.
  assert.equal((await r.evaluate(snippets[2])).tool.action, 'hello');
  assert.equal((await r.evaluate('window.cubby.call({action: "schema_discovered_tool", value: 3})')).tool.value, 3);
  assert.deepEqual(Object.keys(r.context.window.cubby), ['poll', 'call', 'disconnect']);
  r.advance(172800000);
  assert.match((await r.evaluate(snippets[2])).status, /expired/);
});

test('wrong origin rejects before HTTP; deadline and single poll concurrency are bounded', async () => {
  const r = runtime();
  r.context.location.origin = 'https://other.example';
  await assert.rejects(r.evaluate(snippets[0]), /Wrong browser origin/);
  assert.equal(r.calls.length, 0);
  r.context.location.origin = origin;
  await r.evaluate(snippets[0]);
  const first = r.evaluate(snippets[1]);
  assert.equal((await r.evaluate(snippets[1])).status, 'Poll already running');
  await first;
  r.advance(600000);
  const count = r.calls.length;
  assert.match((await r.evaluate(snippets[1])).status, /Stopped/);
  assert.equal(r.calls.length, count);
});

test('terminal and uncertain exchanges never expose or retry credentials', async () => {
  for (const reply of [[400, {error: 'expired_token'}], [400, {error: 'invalid_request'}],
    new Error(deviceSecret), [200, {token_type: 'unexpected', access_token: token}]]) {
    const r = runtime([reply]);
    await r.evaluate(snippets[0]);
    await r.evaluate(snippets[1]);
    const count = r.calls.length;
    assert.match((await r.evaluate(snippets[1])).status, /Stopped/);
    assert.equal(r.calls.length, count);
  }
});
