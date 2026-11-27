// FarmBridge frontend script: welcome pop-up, OTP sign-up, search location, order page, location picker.
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
      var where = document.getElementById("where-text");
      if (status) status.textContent = "Detecting your location…";
      if (where) where.textContent = "Detecting your location…";
      getPosition()
        .then(function (pos) {
          document.getElementById("lat").value = pos.lat.toFixed(6);
          document.getElementById("lon").value = pos.lon.toFixed(6);
          if (where) where.textContent = "Your current location";
          var form = document.getElementById("search-form");
          if (form) form.submit();
        })
        .catch(function (error) {
          if (status) status.textContent = error.message;
          if (where) where.textContent = "Tap to set your location";
        });
    });
  }

  // ---------------------------------------------------------------- checkout: pickup or delivery
  var fulfilmentRadios = document.querySelectorAll('input[name="fulfilment_type"]');
  var deliveryFields = document.getElementById("delivery-fields");
  var pickupInfo = document.getElementById("pickup-info");
  if (fulfilmentRadios.length && deliveryFields) {
    var checkoutForm = document.getElementById("checkout-form");
    var toggle = function () {
      var chosen = document.querySelector('input[name="fulfilment_type"]:checked');
      var delivery = !!chosen && chosen.value === "delivery";
      deliveryFields.hidden = !delivery;
      if (pickupInfo) pickupInfo.hidden = delivery;
      var addressInput = deliveryFields.querySelector('[data-loc="address"]');
      if (addressInput) addressInput.required = delivery;
      if (delivery) {
        deliveryFields.querySelectorAll("[data-loc-picker]").forEach(function (picker) {
          if (picker.__loc) picker.__loc.refresh();
        });
      }
      // update the total
      if (checkoutForm) {
        var subtotal = parseFloat(checkoutForm.dataset.subtotal || "0");
        var fee = delivery ? parseFloat(checkoutForm.dataset.fee || "0") : 0;
        var feeRow = document.getElementById("fee-row");
        if (feeRow) feeRow.hidden = !delivery;
        var money = "Rs " + (subtotal + fee).toLocaleString("en-US", { maximumFractionDigits: 2 });
        var total = document.getElementById("total-amount");
        var placeTotal = document.getElementById("place-total");
        if (total) total.textContent = money;
        if (placeTotal) placeTotal.textContent = money;
      }
    };
    fulfilmentRadios.forEach(function (r) { r.addEventListener("change", toggle); });
    toggle();

    // saved addresses: one tap fills the address and its location
    document.querySelectorAll("[data-saved-addresses] [data-address]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var picker = deliveryFields.querySelector("[data-loc-picker]");
        if (!picker) return;
        picker.querySelector('[data-loc="address"]').value = chip.dataset.address;
        picker.querySelector('[data-loc="lat"]').value = chip.dataset.lat;
        picker.querySelector('[data-loc="lon"]').value = chip.dataset.lon;
        if (picker.__loc) picker.__loc.refresh();
      });
    });
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


// ====================================================================== UI behaviour (FarmBridge design)
(function () {
  // Show / hide password
  document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = button.parentElement.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      button.textContent = show ? "Hide" : "Show";
    });
  });

  // Quantity stepper on the product page, and the live total on the button
  document.querySelectorAll("[data-stepper]").forEach(function (box) {
    var input = box.querySelector("input");
    var step = parseFloat(box.dataset.step || "1");
    var min = parseFloat(box.dataset.min || "1");
    var max = parseFloat(box.dataset.max || "9999");
    var form = box.closest("form");
    var label = form ? form.querySelector("[data-total-label]") : null;
    var render = function () {
      var qty = parseFloat(input.value) || min;
      if (label) {
        var price = parseFloat(label.dataset.price || "0");
        label.textContent = "Add to cart · Rs " + (qty * price).toLocaleString("en-US", { maximumFractionDigits: 2 });
      }
    };
    var change = function (delta) {
      var value = (parseFloat(input.value) || min) + delta;
      value = Math.min(max, Math.max(min, value));
      input.value = Math.round(value * 100) / 100;
      render();
    };
    box.querySelector("[data-dec]").addEventListener("click", function () { change(-step); });
    box.querySelector("[data-inc]").addEventListener("click", function () { change(step); });
    input.addEventListener("input", render);
    render();
  });

  // Loading states: a thin progress bar at the top, a skeleton if a page is slow,
  // and a spinner on the button so nobody presses it twice.
  var topload = document.getElementById("topload");
  var skeleton = document.getElementById("page-skeleton");
  var slowTimer = null;
  var startLoading = function (showSkeleton) {
    if (topload) { topload.classList.add("run"); }
    if (showSkeleton && skeleton) {
      slowTimer = setTimeout(function () { skeleton.hidden = false; }, 350);
    }
  };
  window.addEventListener("pageshow", function () {
    if (topload) topload.classList.remove("run");
    if (skeleton) skeleton.hidden = true;
    clearTimeout(slowTimer);
    document.querySelectorAll(".btn.loading").forEach(function (b) { b.classList.remove("loading"); });
  });
  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey) return;
    var href = link.getAttribute("href");
    if (!href || href.charAt(0) === "#" || link.target === "_blank" || href.indexOf("mailto:") === 0 || href.indexOf("tel:") === 0) return;
    if (link.origin !== window.location.origin) return;
    startLoading(true);
  });
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (event.defaultPrevented) return;
      var button = form.querySelector('button[type="submit"].btn:not(.small), button:not([type]).btn:not(.small)');
      if (button) button.classList.add("loading");
      startLoading(form.method.toLowerCase() === "get");
    });
  });
})();

// ====================================================================== Verify screen and CNIC field
(function () {
  // CNIC: show it as 12345-1234567-1 while typing
  var cnic = document.getElementById("reg-cnic");
  if (cnic) {
    cnic.addEventListener("input", function () {
      var d = cnic.value.replace(/\D/g, "").slice(0, 13);
      var out = d.slice(0, 5);
      if (d.length > 5) out += "-" + d.slice(5, 12);
      if (d.length > 12) out += "-" + d.slice(12);
      cnic.value = out;
    });
  }

  // Six separate boxes for the verification code
  var boxes = Array.prototype.slice.call(document.querySelectorAll(".otp-box"));
  if (boxes.length) {
    var hidden = document.getElementById("otp-value");
    var button = document.getElementById("verify-btn");
    var sync = function () {
      var code = boxes.map(function (b) { return b.value; }).join("");
      hidden.value = code;
      button.disabled = code.length !== boxes.length;
      boxes.forEach(function (b) { b.classList.toggle("filled", !!b.value); });
    };
    boxes.forEach(function (box, i) {
      box.addEventListener("input", function () {
        box.value = box.value.replace(/\D/g, "").slice(-1);
        if (box.value && boxes[i + 1]) boxes[i + 1].focus();
        sync();
      });
      box.addEventListener("keydown", function (event) {
        if (event.key === "Backspace" && !box.value && boxes[i - 1]) { boxes[i - 1].focus(); boxes[i - 1].value = ""; sync(); }
        if (event.key === "ArrowLeft" && boxes[i - 1]) boxes[i - 1].focus();
        if (event.key === "ArrowRight" && boxes[i + 1]) boxes[i + 1].focus();
      });
      box.addEventListener("paste", function (event) {
        var text = ((event.clipboardData || window.clipboardData).getData("text") || "").replace(/\D/g, "").slice(0, boxes.length);
        if (!text) return;
        event.preventDefault();
        text.split("").forEach(function (ch, k) { boxes[k].value = ch; });
        (boxes[Math.min(text.length, boxes.length - 1)]).focus();
        sync();
      });
      box.addEventListener("focus", function () { box.select(); });
    });
    sync();

    // Resend countdown
    var note = document.getElementById("resend-note");
    var counter = document.getElementById("resend-count");
    var resendForm = document.getElementById("resend-form");
    var left = parseInt(note.dataset.seconds || "30", 10);
    var tick = function () {
      if (left <= 0) { note.hidden = true; resendForm.hidden = false; return; }
      counter.textContent = "0:" + (left < 10 ? "0" : "") + left;
      left -= 1;
      setTimeout(tick, 1000);
    };
    tick();
  }
})();


// Stock photos: preview each picture, shrink big phone photos before upload, and switch pictures on the product page.
(function () {
  "use strict";
  var TYPES = ["image/jpeg", "image/png", "image/webp"];
  var LIMIT = 5 * 1024 * 1024;   // same limit as the server
  var MAX_SIDE = 1600;           // longest side after shrinking, in pixels

  // Returns a smaller JPEG when the picture is large; otherwise (or on any problem) the original file.
  function shrink(file, done) {
    var url = URL.createObjectURL(file);
    var img = new Image();
    img.onload = function () {
      URL.revokeObjectURL(url);
      var scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
      if (scale === 1 && file.size <= 1024 * 1024) { done(file); return; }
      var canvas = document.createElement("canvas");
      canvas.width = Math.round(img.naturalWidth * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      var ctx = canvas.getContext("2d");
      ctx.fillStyle = "#fff";    // PNG see-through areas become white, not black
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(function (blob) {
        if (!blob || blob.size >= file.size) { done(file); return; }
        done(new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" }));
      }, "image/jpeg", 0.85);
    };
    img.onerror = function () { URL.revokeObjectURL(url); done(file); };
    img.src = url;
  }

  function resetSlot(input) {
    var slot = input.closest(".photo-slot");
    if (!slot) return;
    slot.querySelector("img").hidden = true;
    slot.querySelector(".empty").hidden = false;
    slot.querySelector(".change").hidden = true;
  }

  function showSlot(input, file) {
    var slot = input.closest(".photo-slot");
    if (!slot) return;
    var img = slot.querySelector("img");
    img.src = URL.createObjectURL(file);
    img.hidden = false;
    slot.querySelector(".empty").hidden = true;
    slot.querySelector(".change").hidden = false;
  }

  document.querySelectorAll("input[type=file][name=photos]").forEach(function (input) {
    input.addEventListener("change", function () {
      var files = Array.prototype.slice.call(input.files || []);
      if (!files.length) { resetSlot(input); return; }
      for (var i = 0; i < files.length; i++) {
        if (TYPES.indexOf(files[i].type) < 0) {
          alert("Please choose JPG, PNG or WebP pictures.");
          input.value = ""; resetSlot(input); return;
        }
      }
      var out = [], left = files.length;
      files.forEach(function (file, index) {
        shrink(file, function (small) {
          out[index] = small;
          left -= 1;
          if (left) return;
          if (window.DataTransfer) {   // put the smaller pictures back into the form field
            try {
              var transfer = new DataTransfer();
              out.forEach(function (f) { transfer.items.add(f); });
              input.files = transfer.files;
            } catch (e) { /* keep the originals */ }
          }
          var current = Array.prototype.slice.call(input.files || []);
          for (var j = 0; j < current.length; j++) {
            if (current[j].size > LIMIT) {
              alert("Each photo must be 5 MB or smaller.");
              input.value = ""; resetSlot(input); return;
            }
          }
          if (current[0]) showSlot(input, current[0]);
        });
      });
    });
  });

  // Product page: tap a small picture to show it large
  document.querySelectorAll("[data-gallery]").forEach(function (gallery) {
    var main = gallery.querySelector("[data-gallery-main]");
    var buttons = gallery.querySelectorAll("[data-gallery-thumb]");
    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        main.src = button.dataset.src;
        buttons.forEach(function (b) { b.classList.toggle("active", b === button); });
      });
    });
  });
})();

// Look and feel: numbers count up, and success messages fade away by themselves.
(function () {
  "use strict";
  var calm = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Dashboard numbers (admin and farmer) count up from 0 to their value
  if (!calm) {
    document.querySelectorAll(".stat strong").forEach(function (el) {
      var target = parseInt(el.textContent, 10);
      if (!/^\d+$/.test(el.textContent.trim()) || target < 2) return;
      var start = null;
      function step(now) {
        if (start === null) start = now;
        var t = Math.min(1, (now - start) / 700);
        el.textContent = Math.round(target * (1 - Math.pow(1 - t, 3)));
        if (t < 1) requestAnimationFrame(step);
      }
      el.textContent = "0";
      requestAnimationFrame(step);
    });
  }

  // Messages: a close button on all, and success ones leave after 5 seconds. Errors stay until closed.
  document.querySelectorAll(".flash").forEach(function (flash) {
    var close = document.createElement("button");
    close.type = "button"; close.className = "toast-close"; close.setAttribute("aria-label", "Close message"); close.textContent = "×";
    function leave() { flash.classList.add("leaving"); setTimeout(function () { flash.remove(); }, calm ? 0 : 450); }
    close.addEventListener("click", leave);
    flash.appendChild(close);
    if (flash.classList.contains("success")) setTimeout(leave, 5000);
  });
})();

/* ---- Installable app: service worker and install hint ---- */
(function () {
  var meta = document.querySelector('meta[name="fb-pwa"]');
  if (!meta) return; // admin pages have no app
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(meta.content, { scope: "/" }).catch(function () {});
    });
  }
  var standalone = (window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone;
  if (standalone) return;
  var KEY = "fb-install-dismissed";
  function dismissed() { try { return localStorage.getItem(KEY) === "1"; } catch (e) { return false; } }
  function remember() { try { localStorage.setItem(KEY, "1"); } catch (e) {} }
  function bar(text, sub, withButton, onInstall) {
    if (dismissed() || document.querySelector(".install-bar")) return;
    var el = document.createElement("div");
    el.className = "install-bar";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", "Install FarmBridge");
    el.innerHTML = '<img alt="" width="40" height="40"><div class="txt"><strong></strong><span></span></div>' +
      (withButton ? '<button type="button" class="btn small">Install</button>' : "") +
      '<button type="button" class="x" aria-label="Close">&times;</button>';
    el.querySelector("img").src = "/static/img/icon-192.png";
    el.querySelector("strong").textContent = text;
    el.querySelector("span").textContent = sub;
    el.querySelector(".x").addEventListener("click", function () { remember(); el.remove(); });
    if (withButton) el.querySelector(".btn").addEventListener("click", function () { el.remove(); onInstall(); });
    document.body.appendChild(el);
    setTimeout(function () { el.classList.add("show"); }, 2500);
  }
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    bar("Install FarmBridge", "Open it like an app from your home screen.", true, function () {
      e.prompt();
      e.userChoice.then(remember);
    });
  });
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
  if (ios) bar("Install FarmBridge", "Tap Share, then Add to Home Screen.", false);
})();
