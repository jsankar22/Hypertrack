// Fitness Coach chat UI for MSc Fitness Assistant

document.addEventListener('DOMContentLoaded', () => {
    const messagesEl = document.getElementById('chatMessages');
    const emptyState = document.getElementById('emptyState');
    const inputEl = document.getElementById('chatInput');
    const sendBtn = document.getElementById('chatSend');
    const errorEl = document.getElementById('chatError');
    const clearBtn = document.getElementById('clearChatBtn');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    let pending = false;

    // ---- rendering -------------------------------------------------
    function escapeHtml(text) {
        return text.replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function inline(text) {
        return text
            .replace(/`([^`]+)`/g, '<code class="px-1 rounded bg-gray-200 text-[0.85em]">$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    }

    // Small, safe markdown subset: headings, bullet/numbered lists, bold, inline code, tables, rules.
    // All text is HTML-escaped first, so model output can never inject markup.
    const isTableRow = l => /^\s*\|.*\|\s*$/.test(l);
    const isSeparator = l => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
    const splitRow = l => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());

    function renderTable(rows) {
        const body = rows.filter(r => !isSeparator(r)).map(splitRow);
        if (!body.length) return '';
        const [head, ...rest] = body;
        const th = head.map(c => `<th class="border border-gray-200 bg-gray-50 px-2.5 py-1.5 text-left font-semibold">${inline(c)}</th>`).join('');
        const trs = rest.map(r =>
            '<tr>' + r.map(c => `<td class="border border-gray-200 px-2.5 py-1.5 align-top">${inline(c)}</td>`).join('') + '</tr>'
        ).join('');
        return `<div class="overflow-x-auto my-2"><table class="w-full border-collapse text-[0.85em]"><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>`;
    }

    function formatReply(raw) {
        const lines = escapeHtml(raw).split('\n');
        let html = '';
        let list = null;
        const closeList = () => { if (list) { html += `</${list}>`; list = null; } };

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // table: consume consecutive |...| lines
            if (isTableRow(line)) {
                closeList();
                const rows = [];
                while (i < lines.length && isTableRow(lines[i])) { rows.push(lines[i]); i++; }
                i--;
                html += renderTable(rows);
                continue;
            }

            const bullet = line.match(/^\s*[-*\u2022]\s+(.*)/);
            const numbered = line.match(/^\s*\d+[.)]\s+(.*)/);
            const heading = line.match(/^#{1,4}\s+(.*)/);
            const boldLine = line.match(/^\s*\*\*([^*]+)\*\*:?\s*$/);   // a line that is only **Title**
            const rule = /^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(line);

            if (bullet || numbered) {
                const type = bullet ? 'ul' : 'ol';
                if (list !== type) {
                    closeList();
                    html += type === 'ul'
                        ? '<ul class="list-disc pl-5 space-y-1 my-2">'
                        : '<ol class="list-decimal pl-5 space-y-1 my-2">';
                    list = type;
                }
                html += `<li>${inline((bullet || numbered)[1])}</li>`;
            } else {
                closeList();
                if (rule) html += '<hr class="my-3 border-gray-200">';
                else if (heading) html += `<p class="font-bold text-gray-900 mt-4 mb-1">${inline(heading[1])}</p>`;
                else if (boldLine) html += `<p class="font-semibold text-gray-900 mt-3 mb-0.5">${inline(boldLine[1])}</p>`;
                else if (line.trim()) html += `<p class="my-1.5">${inline(line)}</p>`;
            }
        }
        closeList();
        return html;
    }

    function addMessage(role, content, sources) {
        emptyState.classList.add('hidden');
        const wrap = document.createElement('div');
        wrap.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';

        const bubble = document.createElement('div');
        if (role === 'user') {
            bubble.className = 'max-w-[85%] md:max-w-[75%] rounded-2xl rounded-br-md bg-brand-accent text-white px-4 py-3 text-sm whitespace-pre-wrap break-words';
            bubble.textContent = content;
        } else {
            bubble.className = 'max-w-[90%] md:max-w-[80%] rounded-2xl rounded-bl-md bg-white border border-gray-200 text-gray-800 px-4 py-2.5 text-sm leading-relaxed break-words';
            bubble.innerHTML = formatReply(content);
            if (sources && sources.length) {
                const src = document.createElement('p');
                src.className = 'mt-2 pt-2 border-t border-gray-100 text-xs text-gray-400';
                src.textContent = 'Reference material: ' + sources.join(', ');
                bubble.appendChild(src);
            }
        }
        wrap.appendChild(bubble);
        messagesEl.appendChild(wrap);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return wrap;
    }

    function addTyping() {
        const wrap = document.createElement('div');
        wrap.className = 'flex justify-start';
        wrap.innerHTML = '<div class="rounded-2xl rounded-bl-md bg-white border border-gray-200 px-4 py-3 text-sm text-gray-400">thinking...</div>';
        messagesEl.appendChild(wrap);
        messagesEl.scrollTop = messagesEl.scrollHeight;
        return wrap;
    }

    function showError(message) {
        errorEl.textContent = message;
        errorEl.classList.toggle('hidden', !message);
    }

    // ---- actions ---------------------------------------------------
    async function send(text) {
        text = text.trim();
        if (!text || pending) return;
        pending = true;
        sendBtn.disabled = true;
        showError('');
        addMessage('user', text);
        inputEl.value = '';
        autoGrow();
        const typing = addTyping();

        try {
            const resp = await fetch('/chatbot/api/message/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ message: text }),
            });
            const data = await resp.json().catch(() => ({}));
            typing.remove();
            if (!resp.ok) {
                showError(data.error || 'Something went wrong. Please try again.');
                inputEl.value = text;  // let the user resend without retyping
                return;
            }
            addMessage('assistant', data.reply, data.sources);
        } catch (err) {
            typing.remove();
            showError('Could not reach the server. Check your connection and try again.');
            inputEl.value = text;
        } finally {
            pending = false;
            sendBtn.disabled = false;
            inputEl.focus();
        }
    }

    function autoGrow() {
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    }

    sendBtn.addEventListener('click', () => send(inputEl.value));
    inputEl.addEventListener('input', autoGrow);
    inputEl.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            send(inputEl.value);
        }
    });
    document.querySelectorAll('[data-suggestion]').forEach(btn =>
        btn.addEventListener('click', () => send(btn.dataset.suggestion))
    );

    clearBtn.addEventListener('click', async () => {
        if (!confirm('Delete this conversation? This cannot be undone.')) return;
        const resp = await fetch('/chatbot/api/clear/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
        });
        if (resp.ok) {
            messagesEl.querySelectorAll(':scope > div:not(#emptyState)').forEach(el => el.remove());
            emptyState.classList.remove('hidden');
            showError('');
        }
    });

    // ---- initial state ---------------------------------------------
    const history = JSON.parse(document.getElementById('chatHistory').textContent);
    if (history.length) {
        history.forEach(m => addMessage(m.role, m.content, m.sources));
    } else {
        emptyState.classList.remove('hidden');
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
});