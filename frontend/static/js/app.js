<<<<<<< HEAD
// FarmLink frontend script: welcome pop-up, OTP sign-up, search location, order page, location picker.
(function () {
  "use strict";

  // ---------------------------------------------------------------- location helpers
  function getPosition() {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) {
        reject(new Error("Your browser does not support location."));
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        },
        function (err) {
          var message =
            err && err.code === 1
              ? "Location permission was denied. Type your address instead."
              : "Could not get your location. Type your address instead.";
          if (!window.isSecureContext) message += " (Location only works on https or localhost.)";
          reject(new Error(message));
        },
        { enableHighAccuracy: true, timeout: 10000 }
      );
    });
  }

  // Free OpenStreetMap geocoder. It is called only when the user presses a button or submits.
  // For a busy production site use a paid geocoding service instead (see README).
  var NOMINATIM = "https://nominatim.openstreetmap.org";

  function nominatim(path, params) {
    var query = new URLSearchParams(Object.assign({ format: "jsonv2", addressdetails: "1" }, params));
    return fetch(NOMINATIM + path + "?" + query.toString(), { headers: { Accept: "application/json" } }).then(
      function (res) {
        if (!res.ok) throw new Error("The address service is busy. Try again in a moment.");
        return res.json();
      }
    );
  }

  function cleanName(value) {
    return (value || "").replace(/\s+(District|Division|Tehsil)$/i, "");
  }

  function partsFrom(address) {
    address = address || {};
    var city = address.city || address.town || address.village || address.municipality || address.suburb || "";
    var district = address.state_district || address.county || address.city_district || address.district || city;
    return { city: cleanName(city), district: cleanName(district), province: address.state || address.region || "" };
  }

  function reverseGeocode(lat, lon) {
    return nominatim("/reverse", { lat: lat, lon: lon, zoom: 18 }).then(function (data) {
      if (!data || data.error) return null;
      return { text: data.display_name || "", parts: partsFrom(data.address) };
    });
  }

  function forwardGeocode(text, country) {
    var params = { q: text, limit: 1 };
    if (country) params.countrycodes = country;
    return nominatim("/search", params).then(function (data) {
      if (!data || !data.length) return null;
      return {
        lat: parseFloat(data[0].lat),
        lon: parseFloat(data[0].lon),
        text: data[0].display_name || "",
        parts: partsFrom(data[0].address),
      };
    });
  }

  // ---------------------------------------------------------------- location picker
  // Markup: templates/_location_picker.html
  function initPicker(el) {
    function field(name) {
      return el.querySelector('[data-loc="' + name + '"]');
    }
    var address = field("address");
    var latInput = field("lat");
    var lonInput = field("lon");
    var status = field("status");
    var mapEl = field("map");
    var parts = { city: field("city"), district: field("district"), province: field("province") };
    var country = el.dataset.country || "";
    var map = null;
    var marker = null;
    var dirty = false; // the address text was edited after the pin was set

    function setStatus(message) {
      status.textContent = message;
    }

    function hasCoords() {
      return latInput.value !== "" && lonInput.value !== "";
    }

    function fillParts(found) {
      ["city", "district", "province"].forEach(function (key) {
        if (parts[key] && found[key]) parts[key].value = found[key];
      });
    }

    function ensureMap(lat, lon) {
      if (!window.L || !mapEl) return; // map library not loaded (offline): the buttons still work
      mapEl.hidden = false;
      if (!map) {
        map = window.L.map(mapEl).setView([lat, lon], 15);
        window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map);
        marker = window.L.marker([lat, lon], { draggable: true }).addTo(map);
        marker.on("dragend", function () {
          var p = marker.getLatLng();
          choose(p.lat, p.lng, true);
        });
        map.on("click", function (event) {
          choose(event.latlng.lat, event.latlng.lng, true);
        });
      } else {
        map.setView([lat, lon], Math.max(map.getZoom(), 15));
        marker.setLatLng([lat, lon]);
      }
      setTimeout(function () {
        map.invalidateSize();
      }, 50);
    }

    function coordsText() {
      return "(" + latInput.value + ", " + lonInput.value + ")";
    }

    // The user picked a point (GPS, map click or pin drag): store it and, optionally, name the address.
    function choose(lat, lon, lookupAddress) {
      latInput.value = lat.toFixed(6);
      lonInput.value = lon.toFixed(6);
      dirty = false;
      ensureMap(lat, lon);
      setStatus("Location set " + coordsText() + ".");
      if (!lookupAddress) return Promise.resolve();
      setStatus("Location set " + coordsText() + ". Looking up the address…");
      return reverseGeocode(lat, lon)
        .then(function (found) {
          if (found) {
            address.value = found.text;
            fillParts(found.parts);
            setStatus("Location set " + coordsText() + ". Check the address and edit it if needed.");
          } else {
            setStatus("Location set " + coordsText() + ". We could not name this place, please type the address.");
          }
        })
        .catch(function (error) {
          setStatus("Location set " + coordsText() + ". " + error.message + " Please type the address.");
        });
    }

    function detect() {
      setStatus("Detecting your location…");
      return getPosition()
        .then(function (pos) {
          return choose(pos.lat, pos.lon, true);
        })
        .catch(function (error) {
          setStatus(error.message);
        });
    }

    // Turn the typed address into a pin. Resolves to true when the pin was set.
    function findFromAddress() {
      var text = address.value.trim();
      if (!text) {
        setStatus("Type an address first.");
        return Promise.resolve(false);
      }
      setStatus("Searching for the address…");
      return forwardGeocode(text, country)
        .then(function (found) {
          if (!found) {
            setStatus("We could not find that address. Add the area and city, click the map, or use Detect my location.");
            return false;
          }
          latInput.value = found.lat.toFixed(6);
          lonInput.value = found.lon.toFixed(6);
          dirty = false;
          fillParts(found.parts);
          ensureMap(found.lat, found.lon);
          setStatus("Address found " + coordsText() + ". Drag the pin if it is not exact.");
          return true;
        })
        .catch(function (error) {
          setStatus(error.message);
          return false;
        });
    }

    function refresh() {
      if (hasCoords()) ensureMap(parseFloat(latInput.value), parseFloat(lonInput.value));
    }

    el.querySelectorAll("[data-loc-action]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (button.dataset.locAction === "detect") detect();
        else findFromAddress();
      });
    });

    address.addEventListener("input", function () {
      if (hasCoords() && !dirty) {
        dirty = true;
        setStatus('Address changed. Press "Find this address on the map" to move the pin.');
      }
    });

    el.__loc = {
      hasCoords: hasCoords,
      isDirty: function () {
        return dirty;
      },
      findFromAddress: findFromAddress,
      refresh: refresh,
    };

    // Before the form is sent, make sure there are coordinates (needed for pickup maps and delivery radius).
    var form = el.closest("form");
    if (form && !form.__locGuard) {
      form.__locGuard = true;
      form.addEventListener("submit", function (event) {
        var pending = Array.prototype.filter.call(
          form.querySelectorAll("[data-loc-picker][data-require-coords]"),
          function (picker) {
            return picker.__loc && !picker.closest("[hidden]") && (!picker.__loc.hasCoords() || picker.__loc.isDirty());
          }
        );
        if (!pending.length) return;
        event.preventDefault();
        var chain = Promise.resolve(true);
        pending.forEach(function (picker) {
          chain = chain.then(function (ok) {
            if (!ok) return false;
            return picker.__loc.findFromAddress().then(function (found) {
              if (!found && !picker.__loc.hasCoords()) {
                picker.scrollIntoView({ block: "center" });
                return false;
              }
              return true; // keep the earlier pin if the edited text could not be found
            });
          });
        });
        chain.then(function (ok) {
          if (ok) form.submit();
        });
      });
    }

    // Start-up: show the map for a known location; name it if only coordinates were given.
    refresh();
    if (el.hasAttribute("data-autofill-address") && hasCoords() && !address.value.trim()) {
      reverseGeocode(parseFloat(latInput.value), parseFloat(lonInput.value))
        .then(function (found) {
          if (found && !address.value.trim()) {
            address.value = found.text;
            fillParts(found.parts);
            setStatus("Using your search location " + coordsText() + ". Edit the address if it is not right.");
          }
        })
        .catch(function () {});
    }
  }

  document.querySelectorAll("[data-loc-picker]").forEach(initPicker);

  // ---------------------------------------------------------------- search page: "Use my location"
  var searchButton = document.getElementById("use-location");
  if (searchButton) {
    searchButton.addEventListener("click", function () {
      var status = document.getElementById("location-status");
      status.textContent = "Detecting your location…";
      getPosition()
        .then(function (pos) {
          document.getElementById("lat").value = pos.lat.toFixed(6);
          document.getElementById("lon").value = pos.lon.toFixed(6);
          status.textContent = "Location set. Press Search.";
        })
        .catch(function (error) {
          status.textContent = error.message;
        });
    });
  }

  // ---------------------------------------------------------------- order page: pickup or delivery
  var fulfilment = document.getElementById("fulfilment_type");
  var deliveryFields = document.getElementById("delivery-fields");
  var pickupInfo = document.getElementById("pickup-info");
  if (fulfilment && deliveryFields) {
    var toggle = function () {
      var delivery = fulfilment.value === "delivery";
      deliveryFields.hidden = !delivery;
      if (pickupInfo) pickupInfo.hidden = delivery;
      var addressInput = deliveryFields.querySelector('[data-loc="address"]');
      if (addressInput) addressInput.required = delivery;
      if (delivery) {
        deliveryFields.querySelectorAll("[data-loc-picker]").forEach(function (picker) {
          if (picker.__loc) picker.__loc.refresh();
        });
      }
    };
    fulfilment.addEventListener("change", toggle);
    toggle();
  }

  // ---------------------------------------------------------------- welcome pop-up
  var modal = document.getElementById("welcome-modal");
  if (modal) {
    var closeModal = function () {
      modal.hidden = true;
      document.body.classList.remove("modal-open");
    };
    ["welcome-close", "welcome-skip"].forEach(function (id) {
      var button = document.getElementById(id);
      if (button) {
        button.addEventListener("click", function (event) {
          event.preventDefault();
          closeModal();
        });
      }
    });
    modal.addEventListener("click", function (event) {
      if (event.target === modal) closeModal();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeModal();
    });
    document.body.classList.add("modal-open");
  }

  // ---------------------------------------------------------------- registration: send OTP
  var sendOtp = document.getElementById("send-otp");
  if (sendOtp) {
    var phone = document.getElementById("reg-phone");
    var otp = document.getElementById("reg-otp");
    var otpStatus = document.getElementById("otp-status");

    var cooldown = function (seconds) {
      var left = seconds;
      sendOtp.disabled = true;
      var timer = setInterval(function () {
        left -= 1;
        if (left <= 0) {
          clearInterval(timer);
          sendOtp.disabled = false;
          sendOtp.textContent = "Send OTP again";
        } else {
          sendOtp.textContent = "Resend in " + left + "s";
        }
      }, 1000);
      sendOtp.textContent = "Resend in " + left + "s";
    };

    sendOtp.addEventListener("click", function () {
      var value = phone.value.trim();
      if (value.length < 10) {
        otpStatus.textContent = "Enter your phone number first.";
        phone.focus();
        return;
      }
      sendOtp.disabled = true;
      otpStatus.textContent = "Sending the code…";
      fetch("/register/otp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: value }),
      })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.ok) {
            var message = data.message + ". It expires in " + data.expires_in_minutes + " minutes.";
            if (data.dev_otp) message += " (Demo mode, no SMS provider connected yet: your code is " + data.dev_otp + ")";
            otpStatus.textContent = message;
            otp.focus();
            cooldown(30);
          } else {
            otpStatus.textContent = data.error || "Could not send the code.";
            sendOtp.disabled = false;
          }
        })
        .catch(function () {
          otpStatus.textContent = "Could not reach the server. Please try again.";
          sendOtp.disabled = false;
        });
    });
  }
})();
=======
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
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
