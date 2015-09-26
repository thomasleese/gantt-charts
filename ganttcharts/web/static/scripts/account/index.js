(function() {
  'use strict';

  var updateDisplayName = function() {
    $.ajax({
      url: '/api/account',
      method: 'PATCH',
      data: JSON.stringify({'display_name': $('#display-name-input').val()}),
      contentType: 'application/json',
      success: function(response, textStatus, xhr) {
        $('#display-name-input')
          .addClass('form-control-success')
          .removeClass('form-control-error');

        $('#display-name-group')
          .addClass('has-success')
          .removeClass('has-error');
      },
      error: function(xhr, textStatus, errorThrown) {
        $('#display-name-input')
          .addClass('form-control-error')
          .removeClass('form-control-success');

        $('#display-name-group')
          .addClass('has-error')
          .removeClass('has-success');
      },
    });
  };

  $(function() {
    $('#display-name-input').change(updateDisplayName);
    $('#display-name-form').submit(function(e) {
      e.preventDefault();
      updateDisplayName();
      return false;
    });

    $('#summary-email').change(function(e) {
      var $check = $(this);

      $.ajax({
        url: '/api/account',
        method: 'PATCH',
        data: JSON.stringify({'receive_summary_email': $check.prop('checked')}),
        contentType: 'application/json',
        success: function(response, textStatus, xhr) {

        },
        error: function(xhr, textStatus, errorThrown) {
          $check.prop('checked', !$check.prop('checked'));
        },
      });
    });
  });
}());
