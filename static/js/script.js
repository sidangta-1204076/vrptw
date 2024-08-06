let map;
let markers = [];
let polylines = [];

function initMap() {
    map = L.map('map').setView([-6.877339723542112, 107.57650073777269], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
    }).addTo(map);

    map.on('click', function (event) {
        addMarker(event.latlng);
        const latLngStr = event.latlng.lat + ", " + event.latlng.lng + "\n";
        document.getElementById("locations").value += latLngStr;
    });
}

function addMarker(location) {
    const marker = L.marker(location).addTo(map);
    marker.bindPopup(String.fromCharCode(65 + markers.length)).openPopup();
    markers.push(marker);
}

document.getElementById("vrp-form").addEventListener("submit", function (event) {
    event.preventDefault();
    const form = event.target;
    const locations = form.locations.value.trim().split("\n").map((line) => line.split(",").map(Number));
    const demands = form.demands.value.trim().split("\n").map(Number);
    const vehicle_count = 1;
    const vehicle_type = parseFloat(form.vehicle_type.value);

    // Clear any previous error messages
    document.getElementById("error-message").textContent = "";

    fetch("/solve", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            locations,
            demands,
            vehicle_count,
            vehicle_type,
        }),
    })
    .then((response) => response.json())
    .then((data) => {
        if (data.error) {
            displayError(data.error);
        } else {
            displayRoutes(data.routes, locations);
            displayDetails(data.route_details);
            displayEfficientRoute(data.routes);
        }
    })
    .catch((error) => {
        displayError("An error occurred: " + error);
    });
});

function displayRoutes(routes, locations) {
    markers.forEach(marker => map.removeLayer(marker)); // Clear existing markers
    markers = [];
    polylines.forEach(polyline => map.removeLayer(polyline)); // Clear existing polylines
    polylines = [];

    routes.forEach((route) => {
        const latlngs = route.map(point => [point.latitude, point.longitude]);
        const polyline = L.polyline(latlngs, {color: 'blue'}).addTo(map);
        polylines.push(polyline);

        // Add markers based on the route
        route.forEach((point, i) => {
            addMarkerWithLabel([point.latitude, point.longitude], i);
        });
    });
}

function addMarkerWithLabel(location, labelIndex) {
    const marker = L.marker(location).addTo(map);
    marker.bindPopup(String.fromCharCode(65 + labelIndex)).openPopup();
    markers.push(marker);
}

function displayDetails(details) {
    const detailsDiv = document.getElementById("details");
    let html = "<h2>Route Details</h2>";
    html += "<table>";
    html += "<tr><th>From</th><th>To</th><th>Distance (km)</th><th>Duration (minutes)</th><th>Fuel Consumption (liters)</th></tr>";
    let totalDuration = 0;
    let totalFuel = 0;
    let totalDistance = 0;
    details.forEach((detail) => {
        html += `<tr>
                 <td>${detail.from}</td>
                 <td>${detail.to}</td>
                 <td>${detail.distance.toFixed(2)}</td>
                 <td>${detail.duration.toFixed(2)}</td>
                 <td>${detail.fuel_consumption.toFixed(2)}</td>
               </tr>`;
        totalDuration += detail.duration;
        totalFuel += detail.fuel_consumption;
        totalDistance += detail.distance;
    });
    html += "</table>";
    html += `<h3><strong>Total Distance (km):</strong> ${totalDistance.toFixed(2)} KM</h3>`;
    html += `<h3><strong>Total Duration (minutes):</strong> ${totalDuration.toFixed(2)}</h3>`;
    html += `<h3><strong>Total Fuel Consumption (liters):</strong> ${totalFuel.toFixed(2)} L</h3>`;
    detailsDiv.innerHTML = html;
}

function displayEfficientRoute(routes) {
    const detailsDiv = document.getElementById("details");
    let html = "<h2>Efficient Route Sequence</h2>";
    routes.forEach((route, index) => {
        let routeStr = route.map((point, i) => String.fromCharCode(65 + i)).join(" -> ");
        html += `<p>Vehicle ${index + 1}: ${routeStr}</p>`;
    });
    detailsDiv.innerHTML = html + detailsDiv.innerHTML;
}

function displayError(error) {
    const errorMessageDiv = document.getElementById("error-message");
    errorMessageDiv.textContent = error;
}

// Load the OpenStreetMap (Leaflet.js) script and initialize the map
document.addEventListener("DOMContentLoaded", initMap);
