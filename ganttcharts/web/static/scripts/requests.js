window.requests = (function(requests) {
  'use strict';

  var readCookie = function(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i];
      while (c.charAt(0) === ' ') {
        c = c.substring(1, c.length);
      }
      if (c.indexOf(nameEQ) === 0) {
        return c.substring(nameEQ.length, c.length);
      }
    }

    return null;
  };

  var request = function(method) {
    return function(url) {
      var xhr = new XMLHttpRequest();

      var sendData;

      return {
        send: function(data) {
          sendData = JSON.stringify(data);
          return this;
        },
        go: function(callback) {
          xhr.onload = function() {
            var contentType = xhr.getResponseHeader('Content-Type');
            var response = xhr.response;
            if (contentType === 'application/json') {
              response = JSON.parse(response);
            }

            callback(xhr.status, response);
          };

          xhr.open(method, url);

          xhr.setRequestHeader('X-CSRF-Token', readCookie('CSRF-Token'));

          if (sendData) {
            xhr.setRequestHeader('Content-Type', 'application/json');
          }

          xhr.send(sendData);
        }
      };
    };
  };

  request.get = request('GET');
  request.patch = request('PATCH');
  request.post = request('POST');
  request.put = request('PUT');
  request.delete = request('DELETE');

  return request;
}(window.requests || {}));
