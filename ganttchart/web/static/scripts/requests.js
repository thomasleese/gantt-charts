window.requests = (function(requests) {
  'use strict';

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

          if (sendData) {
            xhr.setRequestHeader('Content-Type', 'application/json');
          }

          xhr.send(sendData);
        }
      };
    };
  };

  request.get = request('GET');
  request.post = request('POST');
  request.put = request('PUT');
  request.delete = request('DELETE');

  return request;
}(window.requests || {}));
