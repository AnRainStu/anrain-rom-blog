(() => {
  const opening = document.getElementById('opening');
  const notice = document.getElementById('flash-notice');
  const donation = document.getElementById('donation-dialog');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let openingDone = !opening || !document.documentElement.classList.contains('opening-active');
  let donationShown = false;

  function closeDialog(dialog, afterClose) {
    if (!dialog.open || dialog.classList.contains('dialog-closing')) return;
    const finish = () => {
      dialog.close();
      dialog.classList.remove('dialog-closing');
      if (afterClose) afterClose();
    };
    if (reducedMotion.matches) { finish(); return; }
    dialog.classList.add('dialog-closing');
    setTimeout(finish, 180);
  }

  function showDonation() {
    if (!donation || donation.open || !openingDone || (notice && notice.open)) return;
    donationShown = true;
    donation.classList.remove('dialog-closing');
    donation.showModal();
  }
  function finishOpening() {
    if (openingDone) return;
    openingDone = true;
    document.documentElement.classList.remove('opening-active');
    opening.hidden = true;
    if (!donationShown) showDonation();
  }
  if (!openingDone) {
    opening.querySelector('.opening-skip').addEventListener('click', finishOpening);
    opening.addEventListener('animationend', event => {
      if (event.target === opening && event.animationName === 'splash-finish') finishOpening();
    });
    setTimeout(finishOpening, 3000);
  }

  if (donation) {
    document.querySelectorAll('.donation-open').forEach(button => button.addEventListener('click', showDonation));
    const closeDonation = () => closeDialog(donation);
    donation.querySelector('.dialog-close').addEventListener('click', closeDonation);
    donation.addEventListener('cancel', event => { event.preventDefault(); closeDonation(); });
  }

  if (notice) {
    let acknowledged = false;
    try { acknowledged = sessionStorage.getItem('flash-notice-ack') === '1'; } catch (_) {}
    if (!acknowledged) notice.showModal();
    notice.addEventListener('cancel', event => event.preventDefault());
    notice.querySelector('.notice-confirm').addEventListener('click', () => {
      try { sessionStorage.setItem('flash-notice-ack', '1'); } catch (_) {}
      closeDialog(notice, () => { if (!donationShown) showDonation(); });
    });
  }
  if (openingDone && (!notice || !notice.open)) showDonation();

  const clockTime = document.getElementById('clock-time');
  const clockDate = document.getElementById('clock-date');
  if (clockTime && clockDate) {
    const updateClock = () => {
      const now = new Date();
      clockTime.textContent = new Intl.DateTimeFormat('zh-CN', {hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}).format(now);
      clockDate.textContent = new Intl.DateTimeFormat('zh-CN', {year:'numeric', month:'long', day:'numeric', weekday:'long'}).format(now);
    };
    updateClock();
    setInterval(updateClock, 1000);
  }

  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || reducedMotion.matches) return;
    const link = event.target.closest('a[href]');
    if (!link || link.target || link.hasAttribute('download')) return;
    const destination = new URL(link.href, location.href);
    if (destination.origin !== location.origin || !['http:', 'https:'].includes(destination.protocol)) return;
    if (destination.pathname === location.pathname && destination.search === location.search) return;
    event.preventDefault();
    document.documentElement.classList.add('page-leaving');
    setTimeout(() => { location.href = destination.href; }, 180);
  });
  window.addEventListener('pageshow', () => document.documentElement.classList.remove('page-leaving'));
})();
