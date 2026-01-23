// static/js/empresa.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Capturar elementos
    var latInput = document.getElementById('latitud');
    var lngInput = document.getElementById('longitud');
    var radInput = document.getElementById('radio');

    // 2. Valores iniciales
    var currentLat = parseFloat(latInput.value) || 40.4167; // Madrid por defecto
    var currentLng = parseFloat(lngInput.value) || -3.7032;
    var currentRad = parseFloat(radInput.value) || 100;

    // 3. Inicializar mapa (Vista un poco más alejada al principio)
    var map = L.map('map').setView([currentLat, currentLng], 15);

    // 4. Capa de mapa (Usamos una versión más limpia si es posible, o la estándar)
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    }).addTo(map);

    var marker;
    var circle;

    // 5. Función principal
    function updateMapElements(lat, lng, rad, shouldFly) {
        // Limpiar anteriores
        if (marker) map.removeLayer(marker);
        if (circle) map.removeLayer(circle);

        // Crear Marcador
        marker = L.marker([lat, lng], {draggable: true}).addTo(map);
        
        // Añadir popup informativo
        marker.bindPopup("<b>Sede Central</b><br>Arrastrame para ajustar.").openPopup();

        // Crear Círculo (Zona de fichaje)
        circle = L.circle([lat, lng], {
            color: '#4e54c8',      // Color del borde (a juego con el CSS)
            fillColor: '#8f94fb',  // Color de relleno (a juego con el CSS)
            fillOpacity: 0.3,
            radius: rad
        }).addTo(map);

        // Animación suave al centrar (solo si se pide explícitamente)
        if (shouldFly) {
            map.flyTo([lat, lng], 16, {
                animate: true,
                duration: 1.5
            });
        }

        // Listener: Al arrastrar el pin
        marker.on('dragend', function(event) {
            var position = marker.getLatLng();
            updateInputs(position.lat, position.lng);
            circle.setLatLng(position);
            // Reabrir popup tras arrastrar
            marker.openPopup();
        });
    }

    // 6. Actualizar inputs
    function updateInputs(lat, lng) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);
        // Efecto visual: parpadeo amarillo suave en los inputs para indicar cambio
        latInput.style.backgroundColor = "#fffce6";
        lngInput.style.backgroundColor = "#fffce6";
        setTimeout(() => {
            latInput.style.backgroundColor = "#edf2f7"; // Vuelta al gris readonly
            lngInput.style.backgroundColor = "#edf2f7";
        }, 300);
    }

    // 7. Dibujar estado inicial (sin animación flyTo para no marear al cargar)
    updateMapElements(currentLat, currentLng, currentRad, false);

    // 8. Evento: Clic en mapa
    map.on('click', function(e) {
        updateInputs(e.latlng.lat, e.latlng.lng);
        // Aquí sí animamos suavemente hacia donde has hecho clic
        updateMapElements(e.latlng.lat, e.latlng.lng, parseFloat(radInput.value) || 100, true);
    });

    // 9. Evento: Cambio de radio
    if(radInput){
        radInput.addEventListener('input', function() {
            var newRad = parseFloat(this.value) || 0;
            if (circle) {
                circle.setRadius(newRad);
            }
        });
    }
});