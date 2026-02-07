document.addEventListener('DOMContentLoaded', function() {
    // Inputs de configuración (lat/lon/radio)
    var latInput = document.getElementById('latitud');
    var lngInput = document.getElementById('longitud');
    var radInput = document.getElementById('radio');

    // Valores iniciales (fallback: Puerta del Sol)
    var currentLat = parseFloat(latInput.value) || 40.4167; 
    var currentLng = parseFloat(lngInput.value) || -3.7032;
    var currentRad = parseFloat(radInput.value) || 100;

    // Mapa base
    var map = L.map('map').setView([currentLat, currentLng], 16);

    // Capa OSM
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    var marker;
    var circle;

    // Render de marcador + círculo
    function updateMapElements(lat, lng, rad, shouldFly) {
        if (marker) map.removeLayer(marker);
        if (circle) map.removeLayer(circle);

        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.bindPopup("<b>SEDE CENTRAL</b><br>Arrastra el pin para ajustar.").openPopup();

        circle = L.circle([lat, lng], {
            color: '#000000',
            fillColor: '#ff4d6d',
            fillOpacity: 0.3,
            weight: 3,
            radius: rad
        }).addTo(map);

        if (shouldFly) {
            map.flyTo([lat, lng], 16, {
                animate: true,
                duration: 1.5
            });
        }

        marker.on('dragend', function() {
            var position = marker.getLatLng();
            updateInputs(position.lat, position.lng);
            circle.setLatLng(position);
            marker.openPopup();
        });
    }

    // Sync inputs desde el mapa
    function updateInputs(lat, lng) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);

        latInput.style.backgroundColor = "#fff9c4"; 
        lngInput.style.backgroundColor = "#fff9c4";
        
        setTimeout(() => {
            latInput.style.backgroundColor = ""; 
            lngInput.style.backgroundColor = "";
        }, 300);
    }

    // Estado inicial
    updateMapElements(currentLat, currentLng, currentRad, false);

    // Click en mapa => mover sede
    map.on('click', function(e) {
        updateInputs(e.latlng.lat, e.latlng.lng);
        updateMapElements(
            e.latlng.lat,
            e.latlng.lng,
            parseFloat(radInput.value) || 100,
            true
        );
    });

    // Radio en vivo => actualizar círculo
    if (radInput) {
        radInput.addEventListener('input', function() {
            var newRad = parseFloat(this.value) || 0;
            if (circle) circle.setRadius(newRad);
        });
    }
});
