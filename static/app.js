const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const typingIndicator = document.getElementById('typingIndicator');
const themeToggle = document.getElementById('themeToggle');
const avatarScene = document.getElementById('avatarScene');
const profileDetails = document.querySelector('.profile-details');
const langButtons = Array.from(document.querySelectorAll('.lang-option'));
const avatarPoseSources = {
  greeting: '/static/avatar_frames/Greeting.png',
  thinking: '/static/avatar_frames/THINKING.png',
  talking: '/static/avatar_frames/TALKING.png',
  pointing: '/static/avatar_frames/POINTING.png',
  approval: '/static/avatar_frames/Approbe.png',
};
const avatarFrames = new Map();
let avatarPoseTimer;

const translations = {
  es: {
    brandSubtitle: 'Asistente de LinkedIn · QA Automation Engineer · SDET',
    profileDetails: 'Estudios y certificaciones',
    heroTitle: 'SDET - Ingeniero de Pruebas',
    heroDescription: 'Especialista en automatización de pruebas, calidad de software y validación de sistemas con foco en robustez, velocidad y trazabilidad.',
    studiesLabel: 'Estudios',
    study1: 'Gobierno de España — FP Grado 3. Ciclo Formativo de Grado Superior en Informática.',
    study2: 'Colegio Salesiano San José — Técnico en Programación Informática.',
    certsLabel: 'Certificaciones',
    cert1: 'IFCT0109 — Seguridad Informática.',
    cert2: 'Google Cloud — GenAI Leader.',
    cert3: 'AWS Machine Learning MLA CO1',
    cert4: 'Inglés Nivel C1',
    typingIndicator: 'Juan Pablo está escribiendo...',
    inputLabel: 'Escribe tu pregunta',
    inputPlaceholder: 'Pregunta sobre mi experiencia documentada en LinkedIn...',
    inputPlaceholderMobile: 'Pregunta sobre mi LinkedIn...',
    sendButton: 'Enviar',
    themeToggleDark: 'Cambiar a tema claro',
    themeToggleLight: 'Cambiar a tema oscuro',
    welcome: '¡Hola! Soy el asistente virtual de Juan Pablo. Puedes preguntarme sobre su experiencia profesional, stack o certificaciones documentados en LinkedIn. ¿Qué te gustaría saber?',
    answerDisclaimer: 'La información completa está disponible en mi LinkedIn; esta respuesta es solo orientativa.',
    infoNotice: '',
    loadingPlaceholder: 'Estoy preparando la respuesta...',
    errorResponse: 'Lo siento, no pude responder ahora mismo: ',
    responseError: 'No se pudo obtener la respuesta.'
  },
  en: {
    brandSubtitle: 'LinkedIn Assistant · QA Automation Engineer · SDET',
    profileDetails: 'Education and certifications',
    heroTitle: 'SDET - Software Test Engineer',
    heroDescription: 'Specialist in test automation, software quality, and system validation with a focus on robustness, speed, and traceability.',
    studiesLabel: 'Education',
    study1: 'Government of Spain — FP Grado 3. Higher Vocational Training in Computer Science.',
    study2: 'Colegio Salesiano San José — Computer Programming Technician.',
    certsLabel: 'Certifications',
    cert1: 'IFCT0109 — Information Security.',
    cert2: 'Google Cloud — GenAI Leader.',
    cert3: 'AWS Machine Learning MLA CO1',
    cert4: 'English Level C1',
    typingIndicator: 'Juan Pablo is typing...',
    inputLabel: 'Write your question',
    inputPlaceholder: 'Ask about my experience documented on LinkedIn...',
    inputPlaceholderMobile: 'Ask about my LinkedIn...',
    sendButton: 'Send',
    themeToggleDark: 'Switch to light theme',
    themeToggleLight: 'Switch to dark theme',
    welcome: 'Hello! I am Juan Pablo\'s virtual assistant. You can ask about his professional experience, tech stack, or certifications documented on LinkedIn. What would you like to know?',
    answerDisclaimer: 'The complete information is available on my LinkedIn; this response is for guidance only.',
    infoNotice: '',
    loadingPlaceholder: 'Preparing the answer...',
    errorResponse: 'Sorry, I could not answer right now: ',
    responseError: 'Could not get a response.'
  }
};

let isLoading = false;
let currentLanguage = localStorage.getItem('language') || 'es';

function updateAvatarState() {
  avatarScene.classList.toggle('thinking', isLoading);
  if (isLoading) {
    setAvatarPose('thinking');
  }
}

function setAvatarPose(pose) {
  window.clearTimeout(avatarPoseTimer);
  const activeFrame = avatarFrames.get(pose);
  if (!activeFrame) {
    console.error(`Avatar pose is unavailable: ${pose}`);
    return;
  }

  avatarFrames.forEach((frame) => {
    frame.classList.toggle('is-active', frame === activeFrame);
  });
  avatarScene.dataset.avatarState = pose;
  avatarScene.classList.toggle('speaking', pose === 'talking');
}

function playAvatarSequence(sequence) {
  const [current, ...remaining] = sequence;
  if (!current) {
    return;
  }

  setAvatarPose(current.pose);
  if (remaining.length) {
    avatarPoseTimer = window.setTimeout(() => {
      playAvatarSequence(remaining);
    }, current.duration);
  }
}

function initializeAvatarFrames() {
  document.querySelectorAll('.hero-avatar[data-avatar-state]').forEach((frame) => {
    avatarFrames.set(frame.dataset.avatarState, frame);
  });

  Object.entries(avatarPoseSources).forEach(([pose, source]) => {
    const frame = document.createElement('img');
    frame.className = 'hero-avatar';
    frame.dataset.avatarState = pose;
    frame.src = source;
    frame.alt = '';
    frame.setAttribute('aria-hidden', 'true');
    frame.addEventListener('error', () => {
      console.error(`Failed to load avatar image for pose: ${pose}`);
      frame.remove();
      avatarFrames.delete(pose);
      if (avatarScene.dataset.avatarState === pose) {
        setAvatarPose('standing');
      }
    });
    avatarFrames.set(pose, frame);
    avatarScene.querySelector('.portrait-frame').appendChild(frame);
  });

  playAvatarSequence([
    { pose: 'greeting', duration: 2000 },
    { pose: 'standing', duration: 0 },
  ]);
}

function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.body.classList.toggle('dark', isDark);
  document.body.classList.toggle('light', !isDark);
  themeToggle.textContent = isDark ? '☀️' : '🌙';
  const languageText = currentLanguage === 'en' ? translations.en : translations.es;
  themeToggle.setAttribute('aria-label', isDark ? languageText.themeToggleDark : languageText.themeToggleLight);
  localStorage.setItem('theme', theme);
}

function initializeTheme() {
  const storedTheme = localStorage.getItem('theme');
  applyTheme(storedTheme || 'dark');
}

function applyLanguage(lang) {
  currentLanguage = lang;
  const text = translations[lang];
  document.documentElement.lang = lang;
  localStorage.setItem('language', lang);

  document.querySelectorAll('[data-i18n]').forEach((element) => {
    const key = element.getAttribute('data-i18n');
    if (text[key]) {
      element.textContent = text[key];
    }
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach((element) => {
    const key = element.getAttribute('data-i18n-placeholder');
    const isMobile = window.matchMedia('(max-width: 640px)').matches;
    const placeholder = key === 'inputPlaceholder' && isMobile
      ? text.inputPlaceholderMobile
      : text[key];
    if (placeholder) {
      element.setAttribute('placeholder', placeholder);
    }
  });

  langButtons.forEach((button) => {
    const isActive = button.dataset.lang === lang;
    button.classList.toggle('active', isActive);
    button.setAttribute('aria-pressed', String(isActive));
  });

  if (chatMessages && chatMessages.children.length) {
    const introWelcome = chatMessages.querySelector('[data-intro="welcome"]');
    const introNotice = chatMessages.querySelector('[data-intro="notice"]');
    if (introWelcome) {
      introWelcome.textContent = text.welcome;
    }
    if (introNotice) {
      introNotice.textContent = text.infoNotice;
    }
  }

  if (userInput) {
    userInput.setAttribute('aria-label', text.inputLabel);
  }

  if (themeToggle) {
    const isDark = document.body.classList.contains('dark');
    themeToggle.setAttribute('aria-label', isDark ? text.themeToggleDark : text.themeToggleLight);
  }
}

function initializeLanguage() {
  applyLanguage(currentLanguage);
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function addMessage(role, text, options = {}) {
  const wrapper = document.createElement('div');
  wrapper.className = `message-row ${role}`;
  const messageText = String(text || '');
  const displayedText = role === 'assistant'
    && !messageText.includes(translations[currentLanguage].answerDisclaimer)
    ? `${messageText}\n\n${translations[currentLanguage].answerDisclaimer}`
    : messageText;

  if (role === 'assistant') {
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    const avatarImg = document.createElement('img');
    avatarImg.src = '/static/avatar-chat.png';
    avatarImg.alt = 'Juan Pablo Cintioli';
    avatarImg.onerror = () => {
      avatarImg.src = '/static/profile-photo.jpg';
    };
    avatar.appendChild(avatarImg);
    wrapper.appendChild(avatar);
  }

  const bubble = document.createElement('div');
  bubble.className = `message-bubble ${role === 'user' ? 'user' : 'assistant'}`;
  if (options.intro) {
    bubble.dataset.intro = options.intro;
  }
  bubble.innerHTML = `<div class="whitespace-pre-wrap">${escapeHtml(displayedText)}</div>`;

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function addInfoNotice(message, options = {}) {
  if (!message) return;

  const bubble = document.createElement('div');
  bubble.className = 'info-bubble';
  if (options.intro) {
    bubble.dataset.intro = options.intro;
  }
  bubble.textContent = message;
  chatMessages.appendChild(bubble);
  scrollToBottom();
}

function setLoadingState(loading) {
  isLoading = loading;
  typingIndicator.classList.toggle('hidden', !loading);
  sendButton.disabled = loading;
  userInput.disabled = loading;
  updateAvatarState();
  if (loading) {
    userInput.placeholder = translations[currentLanguage].loadingPlaceholder;
  } else {
    const text = translations[currentLanguage];
    userInput.placeholder = window.matchMedia('(max-width: 640px)').matches
      ? text.inputPlaceholderMobile
      : text.inputPlaceholder;
  }
}

async function sendMessage() {
  const message = userInput.value.trim();
  if (!message || isLoading) return;

  addMessage('user', message);
  userInput.value = '';
  setLoadingState(true);

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || translations[currentLanguage].responseError);
    }

    addMessage('assistant', data.reply);
    playAvatarSequence([
      { pose: 'talking', duration: 1400 },
      { pose: 'pointing', duration: 1000 },
      { pose: 'approval', duration: 700 },
      { pose: 'standing', duration: 0 },
    ]);
  } catch (error) {
    addMessage('assistant', `${translations[currentLanguage].errorResponse}${error.message}`);
    setAvatarPose('standing');
  } finally {
    setLoadingState(false);
  }
}

chatForm.addEventListener('submit', (event) => {
  event.preventDefault();
  sendMessage();
});

userInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

themeToggle.addEventListener('click', () => {
  const isDark = document.body.classList.contains('dark');
  applyTheme(isDark ? 'light' : 'dark');
});

langButtons.forEach((button) => {
  button.addEventListener('click', () => {
    applyLanguage(button.dataset.lang);
  });
});

initializeTheme();
initializeLanguage();
updateAvatarState();
initializeAvatarFrames();

if (profileDetails) {
  const compactProfileQuery = window.matchMedia('(max-width: 640px)');
  const updateProfileDetails = () => {
    profileDetails.open = !compactProfileQuery.matches;
  };
  updateProfileDetails();
  compactProfileQuery.addEventListener('change', updateProfileDetails);
}

const welcomeText = translations[currentLanguage].welcome;
const welcomeMessage = addMessage('assistant', welcomeText, { intro: 'welcome' });
const infoNotice = addInfoNotice(translations[currentLanguage].infoNotice, { intro: 'notice' });
