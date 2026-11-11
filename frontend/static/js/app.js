// Location helper: fills latitude/longitude fields from the browser's GPS.
function getPosition(onSuccess, onError) {
  if (!navigator.geolocation) {
    onError("Your browser does not support location.");
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => onSuccess(pos.coords.latitude.toFixed(6), pos.coords.longitude.toFixed(6)),
    () => onError("Could not get your location. You can type a city instead."),
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

// Search page: "Use my location" fills hidden lat/lon fields
const searchButton = document.getElementById("use-location");
if (searchButton) {
  searchButton.addEventListener("click", () => {
    const status = document.getElementById("location-status");
    getPosition(
      (lat, lon) => {
        document.getElementById("lat").value = lat;
        document.getElementById("lon").value = lon;
        status.textContent = "Location set. Press Search.";
      },
      (message) => (status.textContent = message)
    );
  });
}

// Forms with data-fill-location="idOfLatField,idOfLonField"
document.querySelectorAll("[data-fill-location]").forEach((button) => {
  button.addEventListener("click", () => {
    const [latId, lonId] = button.dataset.fillLocation.split(",");
    getPosition(
      (lat, lon) => {
        document.getElementById(latId).value = lat;
        document.getElementById(lonId).value = lon;
      },
      (message) => alert(message)
    );
  });
});

// Order page: show address fields only for delivery
const fulfilment = document.getElementById("fulfilment_type");
const deliveryFields = document.getElementById("delivery-fields");
if (fulfilment && deliveryFields) {
  const toggle = () => {
    deliveryFields.hidden = fulfilment.value !== "delivery";
    deliveryFields.querySelector("input[name=delivery_address]").required = fulfilment.value === "delivery";
  };
  fulfilment.addEventListener("change", toggle);
  toggle();
}
