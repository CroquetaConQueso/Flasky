document.addEventListener('DOMContentLoaded', function() {
    // 1. Capturar elementos del DOM
    var latInput = document.getElementById('latitud');
    var lngInput = document.getElementById('longitud');
    var radInput = document.getElementById('radio');

    // 2. Definir valores iniciales (o defecto: Madrid Puerta del Sol)
    var currentLat = parseFloat(latInput.value) || 40.4167; 
    var currentLng = parseFloat(lngInput.value) || -3.7032;
    var currentRad = parseFloat(radInput.value) || 100;

    // 3. Inicializar el mapa
    var map = L.map('map').setView([currentLat, currentLng], 16);

    // 4. Cargar capa de OpenStreetMap
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    var marker;
    var circle;

    // 5. Función principal para dibujar/actualizar elementos
    // 'shouldFly' es un booleano: si es true, la cámara viaja suavemente al punto
    function updateMapElements(lat, lng, rad, shouldFly) {
        // Limpiar capas anteriores si existen
        if (marker) map.removeLayer(marker);
        if (circle) map.removeLayer(circle);

        // Crear marcador arrastrable
        marker = L.marker([lat, lng], {draggable: true}).addTo(map);
        
        // Popup estilo Pop
        marker.bindPopup("<b>SEDE CENTRAL</b><br>Arrastra el pin para ajustar.").openPopup();

        // Crear círculo de radio (Estilo POP: Borde Negro + Relleno Rosa)
        circle = L.circle([lat, lng], {
            color: '#000000',      // Borde Negro Puro (Neo-Brutalism)
            fillColor: '#ff4d6d',  // Rosa Pop (Relleno)
            fillOpacity: 0.3,
            weight: 3,             // Borde grueso
            radius: rad
        }).addTo(map);

        // Animación suave (flyTo) - Recuperada del JS antiguo
        if (shouldFly) {
            map.flyTo([lat, lng], 16, {
                animate: true,
                duration: 1.5 // Duración del vuelo en segundos
            });
        }

        // Evento: Al arrastrar el marcador manualmente
        marker.on('dragend', function(event) {
            var position = marker.getLatLng();
            updateInputs(position.lat, position.lng);
            circle.setLatLng(position);
            marker.openPopup(); // Reabrir popup para confirmar
        });
    }

    // 6. Función para actualizar los inputs con EFECTO VISUAL
    function updateInputs(lat, lng) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);

        // Efecto visual: Parpadeo Amarillo Suave (Estilo Pop)
        // Esto sustituye al parpadeo rojo oscuro del código antiguo
        latInput.style.backgroundColor = "#fff9c4"; 
        lngInput.style.backgroundColor = "#fff9c4";
        
        setTimeout(() => {
            // Restaurar al color original definido en el CSS
            latInput.style.backgroundColor = ""; 
            lngInput.style.backgroundColor = "";
        }, 300);
    }

    // 7. Dibujar estado inicial (sin animación de vuelo al cargar)
    updateMapElements(currentLat, currentLng, currentRad, false);

    // 8. Evento: CLIC EN EL MAPA
    map.on('click', function(e) {
        updateInputs(e.latlng.lat, e.latlng.lng);
        // Aquí SÍ activamos la animación 'shouldFly = true'
        updateMapElements(e.latlng.lat, e.latlng.lng, parseFloat(radInput.value) || 100, true);
    });

    // 9. Evento: CAMBIO MANUAL EN EL RADIO
    if(radInput){
        radInput.addEventListener('input', function() {
            var newRad = parseFloat(this.value) || 0;
            if (circle) {
                circle.setRadius(newRad);
            }
        });
    }
});