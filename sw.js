/* Owl Hours offline support: always try the network first, fall back to the last copy saved on this phone. */
var CACHE="owl-hours-v1";
var SHELL=["./","index.html","manifest.webmanifest","icon-180.png","icon-192.png","icon-512.png"];
self.addEventListener("install",function(e){e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(SHELL)}).then(function(){return self.skipWaiting()}))});
self.addEventListener("activate",function(e){e.waitUntil(caches.keys().then(function(k){return Promise.all(k.filter(function(n){return n!==CACHE}).map(function(n){return caches.delete(n)}))}).then(function(){return self.clients.claim()}))});
self.addEventListener("fetch",function(e){
  var req=e.request;if(req.method!=="GET")return;
  var url=new URL(req.url);if(url.origin!==location.origin)return;
  var key=url.origin+url.pathname;
  e.respondWith(fetch(req).then(function(res){
    if(res&&res.ok){var copy=res.clone();caches.open(CACHE).then(function(c){c.put(key,copy)})}
    return res;
  }).catch(function(){return caches.match(key).then(function(r){return r||caches.match(url.origin+url.pathname.replace(/[^/]*$/,"")+"index.html")})}));
});
