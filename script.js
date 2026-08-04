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

// --- Language translation (globe button + panel) --------------------------
// Shared across index.html, author.html, resources.html. Each of those pages
// includes the #btn-globe / #translate-panel markup and a hidden Google
// Website Translator widget (#google_translate_element, initialised inline
// on that page). This drives that widget through our own searchable panel
// instead of Google's default dropdown/banner.
(function () {
    var LANGS = [
        ['af', 'Afrikaans'], ['sq', 'Albanian'], ['am', 'Amharic'], ['ar', 'Arabic'], ['hy', 'Armenian'],
        ['as', 'Assamese'], ['ay', 'Aymara'], ['az', 'Azerbaijani'], ['bm', 'Bambara'], ['eu', 'Basque'],
        ['be', 'Belarusian'], ['bn', 'Bengali'], ['bho', 'Bhojpuri'], ['bs', 'Bosnian'], ['bg', 'Bulgarian'],
        ['ca', 'Catalan'], ['ceb', 'Cebuano'], ['ny', 'Chichewa'], ['zh-CN', 'Chinese (Simplified)'],
        ['zh-TW', 'Chinese (Traditional)'], ['co', 'Corsican'], ['hr', 'Croatian'], ['cs', 'Czech'],
        ['da', 'Danish'], ['dv', 'Dhivehi'], ['doi', 'Dogri'], ['nl', 'Dutch'], ['en', 'English'],
        ['eo', 'Esperanto'], ['et', 'Estonian'], ['ee', 'Ewe'], ['fil', 'Filipino'], ['fi', 'Finnish'],
        ['fr', 'French'], ['fy', 'Frisian'], ['gl', 'Galician'], ['ka', 'Georgian'], ['de', 'German'],
        ['el', 'Greek'], ['gn', 'Guarani'], ['gu', 'Gujarati'], ['ht', 'Haitian Creole'], ['ha', 'Hausa'],
        ['haw', 'Hawaiian'], ['he', 'Hebrew'], ['hi', 'Hindi'], ['hmn', 'Hmong'], ['hu', 'Hungarian'],
        ['is', 'Icelandic'], ['ig', 'Igbo'], ['ilo', 'Ilocano'], ['id', 'Indonesian'], ['ga', 'Irish'],
        ['it', 'Italian'], ['ja', 'Japanese'], ['jv', 'Javanese'], ['kn', 'Kannada'], ['kk', 'Kazakh'],
        ['km', 'Khmer'], ['rw', 'Kinyarwanda'], ['gom', 'Konkani'], ['ko', 'Korean'], ['kri', 'Krio'],
        ['ku', 'Kurdish'], ['ckb', 'Kurdish (Sorani)'], ['ky', 'Kyrgyz'], ['lo', 'Lao'], ['la', 'Latin'],
        ['lv', 'Latvian'], ['ln', 'Lingala'], ['lt', 'Lithuanian'], ['lg', 'Luganda'], ['lb', 'Luxembourgish'],
        ['mk', 'Macedonian'], ['mai', 'Maithili'], ['mg', 'Malagasy'], ['ms', 'Malay'], ['ml', 'Malayalam'],
        ['mt', 'Maltese'], ['mi', 'Maori'], ['mr', 'Marathi'], ['mni-Mtei', 'Meiteilon (Manipuri)'],
        ['lus', 'Mizo'], ['mn', 'Mongolian'], ['my', 'Myanmar (Burmese)'], ['ne', 'Nepali'],
        ['no', 'Norwegian'], ['or', 'Odia (Oriya)'], ['om', 'Oromo'], ['ps', 'Pashto'], ['fa', 'Persian'],
        ['pl', 'Polish'], ['pt', 'Portuguese'], ['pa', 'Punjabi'], ['qu', 'Quechua'], ['ro', 'Romanian'],
        ['ru', 'Russian'], ['sm', 'Samoan'], ['sa', 'Sanskrit'], ['gd', 'Scots Gaelic'],
        ['nso', 'Sepedi'], ['sr', 'Serbian'], ['st', 'Sesotho'], ['sn', 'Shona'], ['sd', 'Sindhi'],
        ['si', 'Sinhala'], ['sk', 'Slovak'], ['sl', 'Slovenian'], ['so', 'Somali'], ['es', 'Spanish'],
        ['su', 'Sundanese'], ['sw', 'Swahili'], ['sv', 'Swedish'], ['tg', 'Tajik'], ['ta', 'Tamil'],
        ['tt', 'Tatar'], ['te', 'Telugu'], ['th', 'Thai'], ['ti', 'Tigrinya'], ['ts', 'Tsonga'],
        ['tr', 'Turkish'], ['tk', 'Turkmen'], ['ak', 'Twi'], ['uk', 'Ukrainian'], ['ur', 'Urdu'],
        ['ug', 'Uyghur'], ['uz', 'Uzbek'], ['vi', 'Vietnamese'], ['cy', 'Welsh'], ['xh', 'Xhosa'],
        ['yi', 'Yiddish'], ['yo', 'Yoruba'], ['zu', 'Zulu']
    ];

    var STORAGE_KEY = 'wikiTranslateLang';
    var btn = document.getElementById('btn-globe');
    var panel = document.getElementById('translate-panel');
    var search = document.getElementById('tp-search');
    var list = document.getElementById('tp-list');
    if (!btn || !panel || !list || !search) return;

    function currentLang() {
        try { return localStorage.getItem(STORAGE_KEY) || 'en'; } catch (e) { return 'en'; }
    }

    function renderList(filter) {
        var f = (filter || '').trim().toLowerCase();
        var active = currentLang();
        list.innerHTML = '';
        LANGS.forEach(function (pair) {
            var code = pair[0], name = pair[1];
            if (f && name.toLowerCase().indexOf(f) === -1) return;
            var b = document.createElement('button');
            b.type = 'button';
            b.className = 'tp-lang' + (code === active ? ' active' : '');
            b.textContent = name;
            b.addEventListener('click', function () { setLanguage(code); });
            list.appendChild(b);
        });
    }

    function setLanguage(code) {
        try { localStorage.setItem(STORAGE_KEY, code); } catch (e) {}
        panel.classList.remove('open');
        applyLanguage(code);
    }

    function applyLanguage(code) {
        if (code === 'en') {
            // Reset to the original English text.
            document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
            document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=' + location.hostname + ';';
            if (document.querySelector('select.goog-te-combo')) location.reload();
            return;
        }
        // The Google widget loads its <select> asynchronously, so poll
        // briefly until it exists (covers both the click case and the
        // "re-apply on new page load" case below).
        var tries = 0;
        (function tryApply() {
            var combo = document.querySelector('select.goog-te-combo');
            if (combo) {
                if (combo.value !== code) {
                    combo.value = code;
                    combo.dispatchEvent(new Event('change'));
                }
            } else if (tries < 40) {
                tries++;
                setTimeout(tryApply, 250);
            }
        })();
    }

    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var opening = !panel.classList.contains('open');
        panel.classList.toggle('open', opening);
        if (opening) {
            search.value = '';
            renderList('');
            search.focus();
        }
    });
    document.addEventListener('click', function (e) {
        if (panel.classList.contains('open') && !panel.contains(e.target) && e.target !== btn) {
            panel.classList.remove('open');
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') panel.classList.remove('open');
    });
    search.addEventListener('input', function () { renderList(search.value); });

    renderList('');

    // Keep the site translated as the visitor moves between pages.
    var saved = currentLang();
    if (saved && saved !== 'en') applyLanguage(saved);
})();
