(function () {
  var KEY = 'loil-view';
  var PC_WIDTH = 1100;
  var shortSide = Math.min(screen.width, screen.height);
  var phone = shortSide > 0 && shortSide <= 640;
  var mode = '';
  try { mode = localStorage.getItem(KEY) || ''; } catch (e) {}

  var meta = document.querySelector('meta[name="viewport"]');
  if (!meta) {
    meta = document.createElement('meta');
    meta.name = 'viewport';
    document.head.appendChild(meta);
  }
  var pc = phone && mode === 'pc';
  if (pc) meta.setAttribute('content', 'width=' + PC_WIDTH);

  function build() {
    if (!phone || document.getElementById('loil-view-bar')) return;
    var k = pc ? PC_WIDTH / Math.max(screen.width, 1) : 1;
    var bar = document.createElement('div');
    bar.id = 'loil-view-bar';
    bar.style.cssText = 'box-sizing:border-box;width:100%;text-align:right;padding:' + (6 * k) + 'px ' + (12 * k) +
      'px;font:' + (13 * k) + 'px/1.4 sans-serif;background:rgba(127,127,127,.14);color:inherit;';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = pc ? '모바일 버전으로 보기' : 'PC 버전으로 보기';
    btn.style.cssText = 'font:inherit;color:inherit;background:transparent;border:1px solid rgba(127,127,127,.55);' +
      'border-radius:999px;padding:' + (4 * k) + 'px ' + (12 * k) + 'px;cursor:pointer;min-height:0;width:auto;margin:0;';
    btn.addEventListener('click', function () {
      try { localStorage.setItem(KEY, pc ? 'mobile' : 'pc'); } catch (e) {}
      location.reload();
    });
    bar.appendChild(btn);
    document.body.insertBefore(bar, document.body.firstChild);
    var d = getComputedStyle(document.body).display;
    if (d === 'flex' || d === 'grid') {
      bar.style.position = 'absolute';
      bar.style.top = '0';
      bar.style.left = '0';
      bar.style.right = '0';
      bar.style.zIndex = '9999';
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
