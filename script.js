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
    photo.addEventListener('touchstart', (e) => {
        e.preventDefault();
        photo.classList.toggle('is-visible');
    });
}
