// Initialize Socket.IO connection
const socket = io();

// Handle successful connection
socket.on("connect", function () {
  console.log("WebSocket connected");
});

// Handle disconnection
socket.on("disconnect", function () {
  console.log("WebSocket disconnected");
});

// Handle joining a room confirmation
socket.on("joined", function (data) {
  console.log("Joined room:", data.room);
});

// IMPORTANT HOOK:  !!!!
// The server will emit "prediction_ready" event
// when the prediction is done
// Handle prediction results from WebSocket
socket.on("prediction_ready", function (payload) {
  console.log("Prediction received:", payload);
  renderPage(payload);
});

// Attach a submit handler to the form
$("#flight_delay_classification").submit(function (event) {
  // Stop form from submitting normally
  event.preventDefault();

  // Get some values from elements on the page
  var $form = $(this);
  var url = $form.attr("action");

  // Send the data using post
  $.post(url, $form.serialize(), function (data) {
    var response = JSON.parse(data);

    // If the response is ok, print a message to wait and join the room
    if (response.status === "OK") {
      $("#result").empty().append("Processing...");

      // Join the room for this specific request_id
      socket.emit("join", {
        request_id: response.id,
      });

      console.log("Waiting for prediction with ID:", response.id);
    } else {
      $("#result")
        .empty()
        .append("Error: " + (response.message || "Unknown error"));
    }
  }).fail(function (error) {
    console.error("Error submitting form:", error);
    $("#result").empty().append("Error submitting request");
  });
});

// Render the response on the page for splits:
// [-float("inf"), -15.0, 0, 30.0, float("inf")]
function renderPage(response) {
  console.log("Rendering prediction:", response);

  var displayMessage;

  if (response.Prediction == 0 || response.Prediction == "0") {
    displayMessage = "Early (15+ Minutes Early)";
  } else if (response.Prediction == 1 || response.Prediction == "1") {
    displayMessage = "Slightly Early (0-15 Minute Early)";
  } else if (response.Prediction == 2 || response.Prediction == "2") {
    displayMessage = "Slightly Late (0-30 Minute Delay)";
  } else if (response.Prediction == 3 || response.Prediction == "3") {
    displayMessage = "Very Late (30+ Minutes Late)";
  } else {
    displayMessage = "Unknown prediction value: " + response.Prediction;
  }

  console.log("Display message:", displayMessage);
  $("#result").empty().append(displayMessage);
}
