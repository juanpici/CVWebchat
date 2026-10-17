const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const typingIndicator = document.getElementById('typingIndicator');

let isLoading = false;

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(value) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function addMessage(role, text) {
  const wrapper = document.createElement('div');
  wrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;

  const bubble = document.createElement('div');
  bubble.className = `message-bubble rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
    role === 'user'
      ? 'bg-blue-600 text-white'
      : 'border border-slate-200 bg-slate-100 text-slate-700'
  }`;
  bubble.innerHTML = `<div class="whitespace-pre-wrap">${escapeHtml(text || '')}</div>`;

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function addInfoNotice(message) {
  const wrapper = document.createElement('div');
  wrapper.className = 'flex justify-center';

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800';
  bubble.textContent = message;

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  scrollToBottom();
}

function setLoadingState(loading) {
  isLoading = loading;
  typingIndicator.classList.toggle('hidden', !loading);
  sendButton.disabled = loading;
  userInput.disabled = loading;
  if (loading) {
    userInput.placeholder = 'Estoy preparando la respuesta...';
  } else {
    userInput.placeholder = 'Pregunta sobre mi experiencia, stack, certificaciones o CV...';
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
      throw new Error(data.error || 'No se pudo obtener la respuesta.');
    }

    addMessage('assistant', data.reply);
  } catch (error) {
    addMessage('assistant', `Lo siento, no pude responder ahora mismo: ${error.message}`);
  } finally {
    setLoadingState(false);
    userInput.focus();
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

const welcomeText = '¡Hola! Soy el asistente virtual de Juan Pablo. Puedes preguntarme sobre su experiencia con Selenium, Playwright, sus certificaciones o cualquier detalle de su CV. ¿Qué te gustaría saber?';
addMessage('assistant', welcomeText);
addInfoNotice('Nota: la capa gratuita de Gemini tiene cuota y límites. Si se agota, la app mostrará un mensaje claro en lugar de fallar en silencio.');
userInput.focus();
