document.addEventListener("DOMContentLoaded", () => {
  const tooltips = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltips.forEach((triggerEl) => {
    new bootstrap.Tooltip(triggerEl);
  });

  const popovers = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  popovers.forEach((triggerEl) => {
    new bootstrap.Popover(triggerEl);
  });

  if (window.lucide) {
    window.lucide.createIcons();
  }

  document.querySelectorAll('[data-toggle-password]').forEach((button) => {
    const targetSelector = button.getAttribute('data-toggle-password');
    const target = document.querySelector(targetSelector);

    if (!target) {
      return;
    }

    button.addEventListener('click', () => {
      const isPassword = target.getAttribute('type') === 'password';
      target.setAttribute('type', isPassword ? 'text' : 'password');
      button.classList.toggle('is-visible', isPassword);
    });
  });

  document.querySelectorAll('[data-progress-width]').forEach((bar) => {
    const widthValue = bar.getAttribute('data-progress-width');
    if (widthValue) {
      bar.style.width = `${widthValue}%`;
    }
  });

  const solutionInput = document.getElementById('solutionInput');
  const charCounter = document.querySelector('[data-char-count]');
  const submitBtn = document.querySelector('.submit-btn');
  const aiButton = document.querySelector('[data-ai-generate]');
  const aiOutput = document.querySelector('[data-ai-output]');

  const updateSolutionState = () => {
    if (!solutionInput) {
      return;
    }
    const count = solutionInput.value.length;
    if (charCounter) {
      charCounter.textContent = `${count} characters`;
    }
    if (submitBtn) {
      submitBtn.disabled = count === 0;
    }
    if (aiButton) {
      aiButton.disabled = count === 0;
    }
  };

  if (solutionInput) {
    solutionInput.addEventListener('input', updateSolutionState);
    updateSolutionState();
  }

  if (aiButton && solutionInput && aiOutput) {
    aiButton.addEventListener('click', () => {
      const text = solutionInput.value.trim();
      if (!text) {
        return;
      }
      const summary = `${text.slice(0, 140)}${text.length > 140 ? '…' : ''}`;
      aiOutput.innerHTML = `<p class="mb-0 text-gray-700">${summary}</p>`;
    });
  }


  const toggleButtonLoading = (button, isLoading) => {
    if (!button) {
      return;
    }
    button.classList.toggle('is-loading', Boolean(isLoading));
  };

  const generateSummaryHTML = (value) => {
    const trimmed = value.slice(0, 300);
    return [
      '<p class="mb-0 text-muted-soft">',
      '📝 <strong>Solution Snapshot</strong><br><br>',
      '• Key Focus: ',
      trimmed,
      value.length > 300 ? '…' : '',
      '<br>',
      '• Methodology: highlighted main strategy, supporting steps, and validation.<br>',
      '• Skills: reasoning, explanation clarity, subject mastery.',
      '</p>'
    ].join('');
  };

  document.querySelectorAll('[data-ai-generate]').forEach((button) => {
    button.addEventListener('click', () => {
      const targetKey = button.getAttribute('data-ai-generate');
      if (!targetKey) {
        return;
      }

      const input = document.querySelector(`[data-ai-input="${targetKey}"]`);
      const outputWrapper = document.querySelector(`[data-ai-output="${targetKey}"]`);
      const outputContent = document.querySelector(`[data-ai-content="${targetKey}"]`);

      if (!input || !outputWrapper || !outputContent) {
        return;
      }

      const value = input.value.trim();
      if (!value) {
        input.focus();
        return;
      }

      toggleButtonLoading(button, true);
      outputWrapper.classList.remove('d-none');

      setTimeout(() => {
        outputContent.innerHTML = generateSummaryHTML(value);
        toggleButtonLoading(button, false);
      }, 900);
    });
  });

  document.querySelectorAll('[data-rating-control]').forEach((ratingControl) => {
    const hostContainer = ratingControl.closest('[data-rating-host]') || ratingControl.parentElement;
    const ratingValueInput = hostContainer ? hostContainer.querySelector('[data-rating-value]') : null;

    if (!ratingValueInput) {
      return;
    }

    const starButtons = ratingControl.querySelectorAll('[data-rating-star]');
    let currentRating = Number(ratingValueInput.value) || 0;

    const applyRating = (value, persist = true) => {
      starButtons.forEach((button) => {
        const starValue = Number(button.getAttribute('data-rating-star'));
        button.classList.toggle('active', starValue <= value && value !== 0);
      });

      if (persist) {
        currentRating = value;
        ratingValueInput.value = value || '';
      }
    };

    starButtons.forEach((button) => {
      const starValue = Number(button.getAttribute('data-rating-star'));

      button.addEventListener('mouseenter', () => applyRating(starValue, false));
      button.addEventListener('focus', () => applyRating(starValue, false));
      button.addEventListener('mouseleave', () => applyRating(currentRating, false));
      button.addEventListener('blur', () => applyRating(currentRating, false));
      button.addEventListener('click', () => applyRating(starValue));
      button.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          applyRating(starValue);
        }
      });
    });

    ratingControl.addEventListener('mouseleave', () => applyRating(currentRating, false));
    applyRating(currentRating, false);
  });

  const markerButtons = document.querySelectorAll('[data-marker-id]');
  const requestCards = document.querySelectorAll('[data-request-card]');

  if (markerButtons.length && requestCards.length) {
    let activeMarkerId = null;

    const setActiveMarker = (markerId) => {
      if (!markerId || markerId === activeMarkerId) {
        return;
      }

      activeMarkerId = markerId;

      markerButtons.forEach((marker) => {
        marker.classList.toggle('active', marker.getAttribute('data-marker-id') === markerId);
      });

      requestCards.forEach((card) => {
        card.classList.toggle('active', card.getAttribute('data-marker-target') === markerId);
      });
    };

    markerButtons.forEach((marker) => {
      marker.addEventListener('mouseenter', () => setActiveMarker(marker.getAttribute('data-marker-id')));
      marker.addEventListener('click', () => setActiveMarker(marker.getAttribute('data-marker-id')));
    });

    requestCards.forEach((card) => {
      card.addEventListener('mouseenter', () => setActiveMarker(card.getAttribute('data-marker-target')));
      card.addEventListener('click', () => setActiveMarker(card.getAttribute('data-marker-target')));
    });

    const initialCard = document.querySelector('[data-request-card].active') || requestCards[0];
    if (initialCard) {
      setActiveMarker(initialCard.getAttribute('data-marker-target'));
    }
  }

  const confirmModalElement = document.getElementById('mentoraConfirmModal');
  if (confirmModalElement && window.bootstrap) {
    const confirmModal = new bootstrap.Modal(confirmModalElement);
    const confirmMessage = confirmModalElement.querySelector('[data-confirm-message]');
    const confirmAcceptButton = confirmModalElement.querySelector('[data-confirm-accept]');
    let pendingForm = null;

    confirmModalElement.addEventListener('hidden.bs.modal', () => {
      pendingForm = null;
    });

    document.querySelectorAll('form[data-confirm]').forEach((form) => {
      form.addEventListener('submit', (event) => {
        if (form.dataset.confirmed === 'true') {
          form.dataset.confirmed = '';
          return;
        }
        event.preventDefault();
        pendingForm = form;
        if (confirmMessage) {
          confirmMessage.textContent = form.getAttribute('data-confirm') || 'Are you sure?';
        }
        confirmModal.show();
      });
    });

    if (confirmAcceptButton) {
      confirmAcceptButton.addEventListener('click', () => {
        if (!pendingForm) {
          return;
        }
        pendingForm.dataset.confirmed = 'true';
        confirmModal.hide();
        pendingForm.submit();
      });
    }
  }

  // Ensure mobile nav links close the drawer before navigating
  const mobileSidebarElement = document.getElementById('mobileSidebar');
  if (mobileSidebarElement && window.bootstrap) {
    const mobileNavLinks = mobileSidebarElement.querySelectorAll('[data-mobile-nav-link]');
    if (mobileNavLinks.length) {
      const getOffcanvasInstance = () => bootstrap.Offcanvas.getOrCreateInstance(mobileSidebarElement);
      mobileNavLinks.forEach((link) => {
        link.addEventListener('click', (event) => {
          const destination = link.getAttribute('href');
          if (!destination || destination.startsWith('#')) {
            return;
          }
          event.preventDefault();
          const offcanvasInstance = getOffcanvasInstance();
          if (offcanvasInstance) {
            offcanvasInstance.hide();
          }
          setTimeout(() => {
            window.location.assign(destination);
          }, 120);
        });
      });
    }
  }
});
