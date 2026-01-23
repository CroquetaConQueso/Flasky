// static/js/empresa.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Capturar elementos del DOM
    var latInput = document.getElementById('latitud');
    var lngInput = document.getElementById('longitud');
    var radInput = document.getElementById('radio');

    // 2. Definir valores iniciales (o por defecto: Puerta del Sol, Madrid)
    var currentLat = parseFloat(latInput.value) || 40.4167; 
    var currentLng = parseFloat(lngInput.value) || -3.7032;
    var currentRad = parseFloat(radInput.value) || 100;

    // 3. Inicializar el mapa
    // Usamos '15' de zoom para ver bien la zona
    var map = L.map('map').setView([currentLat, currentLng], 15);

    // 4. Cargar capa de OpenStreetMap
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    var marker;
    var circle;

    // 5. Función principal para dibujar/actualizar elementos
    function updateMapElements(lat, lng, rad, shouldFly) {
        // Si ya existen, los quitamos para poner los nuevos
        if (marker) map.removeLayer(marker);
        if (circle) map.removeLayer(circle);

        // Crear marcador
        marker = L.marker([lat, lng], {draggable: true}).addTo(map);
        
        // Añadir popup informativo
        marker.bindPopup("<b>Sede Central</b><br>Arrastra para ajustar.").openPopup();

        // Crear círculo de radio (ZONA DE FICHAJE)
        // COLORES ACTUALIZADOS: Tema Dark Red/Orange
        circle = L.circle([lat, lng], {
            color: '#FF4B2B',      // Naranja Fuerte (Borde)
            fillColor: '#FF416C',  // Rojo Rosado (Relleno)
            fillOpacity: 0.25,
            radius: rad
        }).addTo(map);

        // Animación suave al centrar (solo si se pide explícitamente, ej: al hacer clic)
        if (shouldFly) {
            map.flyTo([lat, lng], 16, {
                animate: true,
                duration: 1.5
            });
        }

        // Evento: Si arrastran el marcador, actualizamos inputs y círculo
        marker.on('dragend', function(event) {
            var position = marker.getLatLng();
            updateInputs(position.lat, position.lng);
            circle.setLatLng(position);
            marker.openPopup(); // Reabrir popup para confirmar
        });
    }

    // 6. Función para actualizar las cajas de texto
    function updateInputs(lat, lng) {
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);

        // Efecto visual: parpadeo suave para indicar cambio
        // Usamos un color oscuro rojizo suave para el parpadeo
        latInput.style.backgroundColor = "#3d2b2b"; 
        lngInput.style.backgroundColor = "#3d2b2b";
        
        setTimeout(() => {
            // RESTAURAR AL COLOR DEL CSS (Importante para Dark Mode)
            // Al poner "", el navegador vuelve a usar el color definido en tu archivo .css
            latInput.style.backgroundColor = ""; 
            lngInput.style.backgroundColor = "";
        }, 300);
    }

    // 7. Dibujar estado inicial (sin animación de vuelo)
    updateMapElements(currentLat, currentLng, currentRad, false);

    // 8. Evento: CLIC EN EL MAPA
    map.on('click', function(e) {
        updateInputs(e.latlng.lat, e.latlng.lng);
        // Al hacer clic lejos, sí queremos animación (flyTo)
        updateMapElements(e.latlng.lat, e.latlng.lng, parseFloat(radInput.value) || 100, true);
    });

    // 9. Evento: CAMBIO EN EL RADIO (input manual)
    if(radInput){
        radInput.addEventListener('input', function() {
            var newRad = parseFloat(this.value) || 0;
            if (circle) {
                circle.setRadius(newRad);
            }
        });
    }
});