const CONFIRM_TASKS = new Set([
  "poll_force",
  "rebuild_index",
  "codex_update",
  "codex_restart",
]);
// eslint-disable-next-line no-undef
django.jQuery(function ($) {
  const radios = $("input[name=task]");

  radios.on("change", () => {
    const numChecked = radios.filter(":checked").length;
    $("#queueJobButton").prop("disabled", numChecked < 1);
  });

  $("#queueJobButton").on("click", (event) => {
    event.preventDefault();

    // Extract the data & task from the form.
    const formData = $("#queueJobForm").serializeArray();
    const data = {};
    $(formData).each((index, obj) => {
      data[obj.name] = obj.value;
    });
    const task = data.task;

    // Confirm
    if (
      CONFIRM_TASKS.has(task) &&
      !confirm("This could take a while. Are you sure?")
    ) {
      return;
    }

    // Do the call
    const url = `${window.rootPath}api/v2/admin/queue_job`;
    const headers = { "X-CSRFToken": window.csrfToken };
    $.ajax({
      url: url,
      method: "POST",
      headers: headers,
      data: data,
      dataType: "json",
    })
      .done(() => {
        alert(`queued ${task}`);
      })
      .fail((error) => {
        console.error(error);
        alert(`failed to queue ${task}`);
      });
  });
});
