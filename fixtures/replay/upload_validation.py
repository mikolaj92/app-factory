from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
ENV = Environment(loader=FileSystemLoader(ROOT / 'app_factory' / 'templates'))
FORM = ENV.from_string('''{% from 'app_factory/components/file_upload.html' import file_upload %}
{{ file_upload(id='upload', action='/upload', accept='.txt', max_bytes=4, multiple=true) }}
{{ file_upload(id='other', action='/upload', accept='.txt', max_bytes=4) }}''').render()
PAGE = ('<script src="/htmx.js"></script>' + FORM
        + ENV.get_template('app_factory/file_upload_boot.html').render()).encode()
POSTS = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = (ROOT / 'app_factory/assets/htmx.min.js').read_bytes() if self.path == '/htmx.js' else PAGE
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript' if self.path == '/htmx.js' else 'text/html')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers['Content-Length']))
        parsed = BytesParser(policy=default).parsebytes(
            f'Content-Type: {self.headers["Content-Type"]}\r\n\r\n'.encode() + raw
        )
        POSTS.append([(part.get_param('name', header='content-disposition'),
                       part.get_filename(), part.get_payload(decode=True))
                      for part in parsed.iter_parts()])
        self.send_response(204)
        self.end_headers()

    def log_message(self, *_args):
        pass


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_function('window.__appFileUploadBooted && document.querySelector("form")._htmx')
            page.evaluate('''() => {
              window.dialogs = 0; window.approve = true;
              window.confirm = () => { dialogs++; return approve; };
              window.select = (names, selector = '#upload-input') => {
                const transfer = new DataTransfer();
                names.forEach(([name, text]) => transfer.items.add(new File([text], name, {type: 'text/plain'})));
                const input = document.querySelector(selector);
                input.files = transfer.files;
                input.dispatchEvent(new Event('change'));
              };
              window.issue = () => htmx.ajax('POST', '/upload', {
                source: document.querySelector('#upload'), event: window.original || {}, swap: 'none'
              });
            }''')
            for files, expected in [([], 0), ([['bad.bin', 'a']], 0),
                                    ([['large.txt', '12345']], 0),
                                    ([['good.txt', 'a']], 1), ([['limit.txt', '1234']], 1)]:
                before = len(POSTS)
                page.evaluate('(files) => select(files)', files)
                page.evaluate('issue()')
                page.wait_for_timeout(100)
                assert len(POSTS) - before == expected, (files, POSTS)
                assert page.locator('[aria-busy]').count() == 0
            page.evaluate("select([['a.txt', 'a'], ['b.txt', 'b']]); approve = false; original = new Event('submit')")
            before = len(POSTS)
            page.evaluate("document.querySelector('#upload').dispatchEvent(original)")
            page.wait_for_timeout(100)
            assert len(POSTS) == before
            assert page.evaluate('dialogs') == 1
            page.evaluate('approve = true; issue()')
            assert len(POSTS) == before + 1
            assert page.evaluate('dialogs') == 2
            page.evaluate("select([['c.txt', 'c'], ['d.txt', 'd']])")
            dialogs = page.evaluate('dialogs')
            before = len(POSTS)
            page.evaluate("document.querySelector('#upload').dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}))")
            page.wait_for_timeout(100)
            assert len(POSTS) == before + 1
            assert page.evaluate('dialogs') == dialogs + 1
            page.evaluate('''() => {
              document.addEventListener('htmx:before:request', event => {
                event.detail.ctx.fetch = () => Promise.reject(new Error('synthetic failure'));
              }, {once: true});
            }''')
            before = len(POSTS)
            page.evaluate('issue()')
            assert len(POSTS) == before
            assert page.locator('[aria-busy]').count() == 0
            page.evaluate('''() => {
              document.addEventListener('htmx:before:request', event => { 
                select([['fresh.txt', 'new']]);
                event.detail.ctx.request.body.append('host', 'retained');
              }, {capture: true, once: true});
              select([['old.txt', 'old']]);
            }''')
            page.evaluate('issue()')
            assert ('files', 'fresh.txt', b'new') in POSTS[-1]
            assert ('host', None, b'retained') in POSTS[-1]
            for capture in (True, False):
                before = len(POSTS)
                page.evaluate('''capture => document.addEventListener('htmx:before:request',
                  event => event.preventDefault(), {capture, once: true})''', capture)
                page.evaluate('issue()')
                assert len(POSTS) == before
                assert page.locator('[aria-busy]').count() == 0
                page.evaluate("select([['retry.txt', 'next']]); issue()")
                assert len(POSTS) == before + 1
                assert ('files', 'retry.txt', b'next') in POSTS[-1]
            page.evaluate('''async () => {
              const form = document.querySelector('#upload');
              const field = document.querySelector('#other [data-app-file-upload-field]').cloneNode(true);
              field.querySelector('input').id = 'sibling';
              form.append(field);
              select([['sibling.txt', 'side']], '#sibling');
              await htmx.swap({sourceElement: form, target: document.querySelector('#other'),
                swap: 'innerHTML', text: document.querySelector('#other').innerHTML});
              select([['wrong.bin', 'bad']], '#sibling');
            }''')
            before = len(POSTS)
            page.evaluate('issue()')
            assert len(POSTS) == before
            page.evaluate("select([['sibling.txt', 'side']], '#sibling'); issue()")
            assert len(POSTS) == before + 1
            assert ('files', 'sibling.txt', b'side') in POSTS[-1]
            page.evaluate("select([['other.txt', 'a']], '#other-input')")
            page.evaluate("htmx.ajax('POST', '/upload', {source: document.querySelector('#other'), swap: 'none'})")
            assert len(POSTS) == before + 2
            page.evaluate('''() => {
              const form = document.querySelector('#other');
              form.removeAttribute('hx-post');
              htmx.process(form, true);
              select([['native.bin', 'a']], '#other-input');
              form.requestSubmit();
            }''')
            page.wait_for_timeout(100)
            assert len(POSTS) == before + 2
            page.evaluate("select([['native.txt', 'a']], '#other-input'); document.querySelector('#other').requestSubmit()")
            page.wait_for_timeout(200)
            assert len(POSTS) == before + 3
            browser.close()
            print('Upload replay passed: validation, consent, retry, payload, cancellation, failure, siblings, forms, swap, native')
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
