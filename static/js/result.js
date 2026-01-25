document.addEventListener("DOMContentLoaded", function() {
    
    var username = $("#user_id").text();
    
    // Click event for completed jobs
    $(".table").on("click", ".result_row", function () {
        var state = $(this).data('state');
        var jobId = $(this).data('job-id');
        if (state == "complete") {
            location.href = ("/result/" + username + "/" + jobId);
        }
    });
    
    // Delete button click event
    $(".table").on("click", ".del_job", function (event) {
        event.stopPropagation(); // Prevent parent click event
        var jobId = $(this).closest('.result_row').data('job-id');
        location.href = ("/result/" + username + "/" + jobId + "/delete");
    });
})