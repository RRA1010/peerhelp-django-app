(function () {
  const campusPath = [
    { lat: 9.7762117, lng: 118.7353107 },
    { lat: 9.7756869, lng: 118.7351053 },
    { lat: 9.7755267, lng: 118.7350434 },
    { lat: 9.7754129, lng: 118.7349792 },
    { lat: 9.7753314, lng: 118.7348788 },
    { lat: 9.775233, lng: 118.7346905 },
    { lat: 9.7751744, lng: 118.7345307 },
    { lat: 9.7750621, lng: 118.7342383 },
    { lat: 9.7749722, lng: 118.7340344 },
    { lat: 9.7748863, lng: 118.733895 },
    { lat: 9.7747819, lng: 118.7337421 },
    { lat: 9.7743844, lng: 118.7333657 },
    { lat: 9.7743632, lng: 118.7332841 },
    { lat: 9.7743088, lng: 118.7330747 },
    { lat: 9.7743374, lng: 118.7329204 },
    { lat: 9.774421, lng: 118.7328204 },
    { lat: 9.7745368, lng: 118.7327538 },
    { lat: 9.7746647, lng: 118.732737 },
    { lat: 9.7747809, lng: 118.7327437 },
    { lat: 9.7748901, lng: 118.7327789 },
    { lat: 9.7749786, lng: 118.7327953 },
    { lat: 9.7752541, lng: 118.7327643 },
    { lat: 9.7757145, lng: 118.7327009 },
    { lat: 9.7762848, lng: 118.7325278 },
    { lat: 9.7763953, lng: 118.7324818 },
    { lat: 9.7764973, lng: 118.7324055 },
    { lat: 9.7771925, lng: 118.7314964 },
    { lat: 9.777369, lng: 118.7313831 },
    { lat: 9.7776282, lng: 118.7311357 },
    { lat: 9.7777383, lng: 118.7311482 },
    { lat: 9.7787977, lng: 118.7319042 },
    { lat: 9.7791008, lng: 118.7321328 },
    { lat: 9.7791167, lng: 118.7328123 },
    { lat: 9.7791189, lng: 118.7332795 },
    { lat: 9.7791498, lng: 118.7353796 },
    { lat: 9.7782808, lng: 118.7355861 },
    { lat: 9.7782313, lng: 118.7356567 },
    { lat: 9.7781663, lng: 118.7357769 },
    { lat: 9.7781756, lng: 118.7359191 },
    { lat: 9.7779324, lng: 118.7359157 },
    { lat: 9.7773934, lng: 118.7357672 },
    { lat: 9.7762117, lng: 118.7353107 }
  ];

  const initLocationPicker = () => {
    const mapContainer = document.getElementById('psuMap');
    if (!mapContainer) {
      return;
    }
    const mapsApiKey = mapContainer.dataset.googleMapsKey || '';
    const latInput = document.getElementById('meeting_lat');
    const lngInput = document.getElementById('meeting_lng');
    const statusLabel = document.querySelector('[data-location-status]');
    const initialLatAttr = mapContainer.dataset.initialLat;
    const initialLngAttr = mapContainer.dataset.initialLng;
    const initialLat = initialLatAttr ? parseFloat(initialLatAttr) : null;
    const initialLng = initialLngAttr ? parseFloat(initialLngAttr) : null;

    const setStatus = (message, isError = false) => {
      if (!statusLabel) {
        return;
      }
      statusLabel.textContent = message;
      statusLabel.classList.toggle('text-danger', isError);
    };

    const isPointInsideCampus = (latLng) => {
      const pointLat = latLng.lat();
      const pointLng = latLng.lng();
      let inside = false;
      for (let i = 0, j = campusPath.length - 1; i < campusPath.length; j = i++) {
        const xi = campusPath[i].lng;
        const yi = campusPath[i].lat;
        const xj = campusPath[j].lng;
        const yj = campusPath[j].lat;
        const denominator = (yj - yi) || Number.EPSILON;
        const intersects = ((yi > pointLat) !== (yj > pointLat)) &&
          (pointLng < ((xj - xi) * (pointLat - yi)) / denominator + xi);
        if (intersects) inside = !inside;
      }
      return inside;
    };

    const initMap = () => {
      const map = new google.maps.Map(mapContainer, {
        center: { lat: 9.7775, lng: 118.7335 },
        zoom: 18,
        mapTypeId: 'roadmap',
        streetViewControl: false,
        fullscreenControl: false,
        mapTypeControl: false,
        clickableIcons: false,
      });

      const campusPolygon = new google.maps.Polygon({
        paths: campusPath,
        strokeColor: '#ff6b00',
        strokeWeight: 2,
        strokeOpacity: 0.9,
        fillColor: '#ffedd5',
        fillOpacity: 0.45,
        clickable: false,
      });
      campusPolygon.setMap(map);

      const bounds = new google.maps.LatLngBounds();
      campusPath.forEach((coord) => bounds.extend(coord));
      map.fitBounds(bounds, { padding: 24 });

      let marker = null;

      const placeMarker = (latLng) => {
        if (!marker) {
          marker = new google.maps.Marker({
            position: latLng,
            map,
            animation: google.maps.Animation.DROP,
          });
        } else {
          marker.setPosition(latLng);
        }
        latInput.value = latLng.lat().toFixed(6);
        lngInput.value = latLng.lng().toFixed(6);
        setStatus(`Selected: ${latLng.lat().toFixed(6)}, ${latLng.lng().toFixed(6)}`);
      };

      const handleSelection = (event) => {
        const latLng = event.latLng || event;
        if (!isPointInsideCampus(latLng)) {
          setStatus('Please stay inside the PSU campus boundary.', true);
          return;
        }
        setStatus('');
        placeMarker(latLng);
      };

      map.addListener('click', handleSelection);
      campusPolygon.addListener('click', handleSelection);

      if (!latInput.value || !lngInput.value) {
        setStatus('Tap anywhere inside the campus outline to choose a meeting spot.');
      }

      if (initialLat !== null && initialLng !== null) {
        const preset = new google.maps.LatLng(initialLat, initialLng);
        placeMarker(preset);
        map.panTo(preset);
      }
    };

    const loadGoogleMaps = () => {
      if (!mapsApiKey) {
        console.warn('Google Maps API key missing. Location picker disabled.');
        return;
      }
      if (window.google && window.google.maps && window.google.maps.geometry) {
        initMap();
        return;
      }
      const existingScript = document.querySelector('script[data-google-maps]');
      if (existingScript) {
        existingScript.addEventListener('load', initMap, { once: true });
        return;
      }
      const script = document.createElement('script');
      script.src = `https://maps.googleapis.com/maps/api/js?key=${mapsApiKey}&libraries=geometry`;
      script.async = true;
      script.defer = true;
      script.dataset.googleMaps = 'true';
      script.addEventListener('load', initMap, { once: true });
      document.head.appendChild(script);
    };

    loadGoogleMaps();
  };

  document.addEventListener('DOMContentLoaded', initLocationPicker);
})();
