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

  const escapeHtml = (value) => {
    if (typeof value !== 'string') {
      return '';
    }
    const htmlEscapes = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    };
    return value.replace(/[&<>"']/g, (char) => htmlEscapes[char] || char);
  };

  const formatRelativeTime = (isoDateString) => {
    if (!isoDateString) {
      return '';
    }
    const createdDate = new Date(isoDateString);
    if (Number.isNaN(createdDate.getTime())) {
      return '';
    }
    const now = Date.now();
    let diffMs = now - createdDate.getTime();
    if (diffMs < 0) {
      diffMs = 0;
    }
    const minuteMs = 60 * 1000;
    const hourMs = 60 * minuteMs;
    const dayMs = 24 * hourMs;
    if (diffMs < minuteMs) {
      return 'Posted just now';
    }
    const minutes = Math.floor(diffMs / minuteMs);
    if (minutes < 60) {
      return `Posted ${minutes} minute${minutes === 1 ? '' : 's'} ago`;
    }
    const hours = Math.floor(diffMs / hourMs);
    if (hours < 24) {
      return `Posted ${hours} hour${hours === 1 ? '' : 's'} ago`;
    }
    const days = Math.floor(diffMs / dayMs);
    const remainingHours = Math.floor((diffMs % dayMs) / hourMs);
    const remainingMinutes = Math.floor((diffMs % hourMs) / minuteMs);
    const paddedHours = String(remainingHours).padStart(2, '0');
    const paddedMinutes = String(remainingMinutes).padStart(2, '0');
    return `Posted ${days} day${days === 1 ? '' : 's'} and ${paddedHours}:${paddedMinutes} ago`;
  };

  const buildTagMarkup = (tags) => {
    if (!Array.isArray(tags) || !tags.length) {
      return '';
    }
    return tags
      .slice(0, 3)
      .map((tag) => `<span class="map-info-tag">${escapeHtml(String(tag))}</span>`)
      .join('');
  };

  const initMapPage = () => {
    const mapContainer = document.getElementById('inPersonMap');
    if (!mapContainer) {
      return;
    }
    const mapsApiKey = mapContainer.dataset.googleMapsKey || '';
    const requestsElement = document.getElementById('inPersonRequestsData');
    const requestData = requestsElement ? JSON.parse(requestsElement.textContent) : [];
    const cards = document.querySelectorAll('[data-request-card]');
    const searchInput = document.querySelector('[data-map-search]');
    const locateButton = document.querySelector('[data-locate-me]');
    const locationStatus = document.querySelector('[data-location-status]');

    const setLocationStatus = (message, isError) => {
      if (!locationStatus) {
        return;
      }
      locationStatus.textContent = message || '';
      locationStatus.classList.toggle('text-danger', Boolean(isError));
    };

    const applySearch = () => {
      if (!searchInput) {
        return;
      }
      const query = searchInput.value.toLowerCase();
      cards.forEach((card) => {
        const text = card.textContent.toLowerCase();
        const matches = !query || text.includes(query);
        card.classList.toggle('d-none', !matches);
      });
    };

    if (searchInput) {
      searchInput.addEventListener('input', applySearch);
    }

    const initMap = () => {
      const campusBounds = new google.maps.LatLngBounds();
      campusPath.forEach((coord) => campusBounds.extend(coord));

      const map = new google.maps.Map(mapContainer, {
        center: campusBounds.getCenter(),
        zoom: 16,
        minZoom: 15,
        maxZoom: 21,
        restriction: {
          latLngBounds: campusBounds,
          strictBounds: true,
        },
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
        fillOpacity: 0.35,
        clickable: false,
      });
      campusPolygon.setMap(map);
      map.fitBounds(campusBounds, { padding: 24 });

      const infoWindow = new google.maps.InfoWindow();
      const markers = new Map();
      let activeMarkerId = null;

      const focusCard = (targetId) => {
        cards.forEach((card) => {
          card.classList.toggle('active', card.getAttribute('data-marker-target') === targetId);
        });
      };

      const scrollCardIntoView = (targetId) => {
        const card = document.querySelector(`[data-request-card][data-marker-target="${targetId}"]`);
        if (card) {
          card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      };

      const setActiveMarker = (markerId, options = { pan: true, bounce: true, fromMarker: false }) => {
        if (!markerId) {
          return;
        }
        infoWindow.close();
        activeMarkerId = markerId;
        focusCard(markerId);
        if (!options.fromMarker) {
          scrollCardIntoView(markerId);
        }
        markers.forEach((marker, currentId) => {
          const shouldBounce = options.bounce && currentId === markerId;
          marker.setAnimation(shouldBounce ? google.maps.Animation.BOUNCE : null);
          if (currentId === markerId && options.pan) {
            map.panTo(marker.getPosition());
            if (map.getZoom() < 18) {
              map.setZoom(18);
            }
          }
        });
        if (options.bounce) {
          setTimeout(() => {
            const marker = markers.get(markerId);
            if (marker) {
              marker.setAnimation(null);
            }
          }, 1400);
        }
      };

      const openRequestPopup = (request, marker) => {
        if (!request || !marker) {
          return;
        }
        const ownerNameRaw = (request.owner && request.owner.name) || 'Student';
        const title = escapeHtml(request.title || 'Problem');
        const detailUrl = request.detail_url || '';
        const backendTime = typeof request.time === 'string' ? request.time : '';
        const relativeTime = backendTime || formatRelativeTime(request.created_at) || 'Posted recently';
        const readableTime = backendTime || relativeTime.replace(/^Posted\s+/i, '');
        const postedLabel = backendTime ? `Posted ${backendTime}` : relativeTime;
        const subject = escapeHtml(request.subject || 'General');
        const urgencyValue = (request.urgency || 'medium').toLowerCase();
        const urgencyText = urgencyValue ? urgencyValue.charAt(0).toUpperCase() + urgencyValue.slice(1) : 'Medium';
        const location = escapeHtml(request.location || 'On-campus location');
        const ownerInitialRaw = (request.owner && request.owner.initials) || ownerNameRaw.charAt(0) || 'S';
        const studentName = escapeHtml(ownerNameRaw);
        const ownerInitials = escapeHtml(ownerInitialRaw);
        const avatarMarkup = (request.owner && request.owner.avatar)
          ? `<img src="${escapeHtml(request.owner.avatar)}" alt="${studentName}" />`
          : `<span>${ownerInitials}</span>`;
        const tagsMarkup = buildTagMarkup(request.tags);
        const popupHtml = `
          <div class="map-info-window">
            <div class="map-info-title-row">
              <span class="map-info-title">${title}</span>
              <span class="map-info-time">${escapeHtml(readableTime)}</span>
            </div>
            <div class="map-info-meta">
              <span class="map-info-subject">${subject}</span>
              <span class="map-info-urgency">${escapeHtml(urgencyText)}</span>
            </div>
            <div class="map-info-location">
              <span>&#128205;</span>
              <span>${location}</span>
            </div>
            <div class="map-info-tags">${tagsMarkup}</div>
            <div class="map-info-owner">
              <span class="avatar-pill avatar-pill--sm">${avatarMarkup}</span>
              <div>
                <div class="text-gray-900 small fw-semibold">${studentName}</div>
                <div class="text-muted-soft small">${escapeHtml(postedLabel)}</div>
              </div>
            </div>
            <button class="btn btn-sm btn-orange w-100 mt-3" data-info-window-button="${request.id}" data-detail-url="${escapeHtml(detailUrl)}">Show Problem</button>
          </div>
        `;
        infoWindow.setContent(popupHtml);
        infoWindow.open({ map, anchor: marker });
        map.panTo(marker.getPosition());
        if (map.getZoom() < 18) {
          map.setZoom(18);
        }
        google.maps.event.addListenerOnce(infoWindow, 'domready', () => {
          const popupButton = document.querySelector(`[data-info-window-button="${request.id}"]`);
          if (popupButton) {
            popupButton.addEventListener('click', () => {
              const url = popupButton.getAttribute('data-detail-url');
              if (url) {
                window.location.href = url;
              }
            });
          }
        });
      };

      map.addListener('click', () => infoWindow.close());

      requestData.forEach((request) => {
        if (typeof request.meeting_lat !== 'number' || typeof request.meeting_lng !== 'number') {
          return;
        }
        const marker = new google.maps.Marker({
          position: { lat: request.meeting_lat, lng: request.meeting_lng },
          map,
          title: request.title,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 9,
            fillColor: '#ff6b00',
            fillOpacity: 0.95,
            strokeColor: '#ffffff',
            strokeWeight: 2,
          },
        });
        markers.set(String(request.id), marker);
        marker.addListener('click', () => openRequestPopup(request, marker));
      });

      cards.forEach((card) => {
        const targetId = card.getAttribute('data-marker-target');
        card.addEventListener('mouseenter', () => setActiveMarker(targetId, { pan: false, bounce: false }));
        card.addEventListener('click', () => {
          const alreadyActive = card.classList.contains('active');
          setActiveMarker(targetId);
          if (alreadyActive) {
            const detailUrl = card.dataset.detailUrl;
            if (detailUrl) {
              window.location.href = detailUrl;
            }
          }
        });
      });

      if (requestData.length) {
        setActiveMarker(String(requestData[0].id), { pan: true, bounce: false });
      }

      if (locateButton) {
        let userMarker = null;
        locateButton.addEventListener('click', () => {
          if (!navigator.geolocation) {
            setLocationStatus('Location services are not available in this browser.', true);
            return;
          }
          setLocationStatus('Locating…');
          navigator.geolocation.getCurrentPosition((position) => {
            const coords = {
              lat: position.coords.latitude,
              lng: position.coords.longitude,
            };
            if (!userMarker) {
              userMarker = new google.maps.Marker({
                position: coords,
                map,
                title: 'Your location',
                icon: {
                  path: google.maps.SymbolPath.CIRCLE,
                  scale: 6,
                  fillColor: '#2563eb',
                  fillOpacity: 0.95,
                  strokeColor: '#ffffff',
                  strokeWeight: 2,
                },
              });
            } else {
              userMarker.setPosition(coords);
            }
            map.panTo(coords);
            map.setZoom(17);
            setLocationStatus('Location locked.');
          }, (error) => {
            setLocationStatus(error.message || 'Unable to detect your location.', true);
          });
        });
      }
    };

    const loadGoogleMaps = () => {
      if (!mapsApiKey) {
        console.warn('Google Maps API key missing. Map view disabled.');
        return;
      }
      if (window.google && window.google.maps) {
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

  document.addEventListener('DOMContentLoaded', initMapPage);
})();
