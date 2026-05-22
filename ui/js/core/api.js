(function () {
  window.api = {
    get:  url         => fetch(url).then(r => r.json()),
    post: (url, body) => fetch(url, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    }).then(r => r.json()),
  };
})();
