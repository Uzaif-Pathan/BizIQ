import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Guards against old placeholder wording coming back after the pages were connected to the server.
const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');

for (const text of [
  'Analysis is not connected yet',
  'Schema checks not connected',
  'Uploaded — validation needed',
  'Good morning',
  'Awaiting validated data',
]) {
  test(`App.jsx does not contain stale text: "${text}"`, () => {
    assert.equal(app.includes(text), false);
  });
}

test('every analysis page is routed to a component that reads the server', () => {
  assert.match(app, /return <SeriesPage key=\{business\.id\} kind=\{kind\}/);
  assert.match(app, /return <MarketPage key=\{business\.id\}/);
});
