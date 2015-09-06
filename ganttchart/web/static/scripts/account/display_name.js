$(function() {
  $('#display-name-input').change(function(e) {
    $.ajax({
      url: '/api/account',
      method: 'PATCH',
      data: JSON.stringify({'display_name': $(this).val()}),
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
  });
});
