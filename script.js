// Rotate the background image, avoiding an immediate repeat
const numImages = 2;

const backgrounds = Array.from(
    { length: numImages },
    (_, i) => `images/image${i + 1}.jpeg`
);

const previous = localStorage.getItem("lastBackground");

const available = backgrounds.filter(
    bg => bg !== previous
);

const chosen =
    available[Math.floor(Math.random() * available.length)];

document.body.style.backgroundImage =
    `url('${chosen}')`;

localStorage.setItem("lastBackground", chosen);

// Tap-to-reveal the blurred profile photo (only present on index.html)
const photo = document.getElementById('profile-photo');

if (photo) {
    const reveal = () => photo.classList.add('is-visible');
    const hide = () => photo.classList.remove('is-visible');

    // Press-and-hold to reveal; re-blur as soon as the finger lifts,
    // mirroring the hover behaviour on desktop. preventDefault stops the
    // browser from firing the synthetic hover/focus that would otherwise
    // stick and keep the photo unblurred after the touch ends.
    photo.addEventListener('touchstart', (e) => { e.preventDefault(); reveal(); }, { passive: false });
    photo.addEventListener('touchend', hide);
    photo.addEventListener('touchcancel', hide);
}
