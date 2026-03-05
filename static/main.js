document.getElementById('matcher-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const name1 = document.getElementById('name1').value.trim();
    const name2 = document.getElementById('name2').value.trim();
    const use_carlton = document.getElementById('chk-carlton').checked;
    const use_wikidata = document.getElementById('chk-wikidata').checked;
    const use_jrc = document.getElementById('chk-jrc').checked;
    const use_l2_model = document.getElementById('chk-l2').checked;
    const strict_order = document.getElementById('chk-strict-order').checked;
    const allow_initials = document.getElementById('chk-allow-initials').checked;
    const strict_unknowns = document.getElementById('chk-strict-unknowns').checked;
    const allow_stepwise = document.getElementById('chk-allow-stepwise').checked;
    const compound_strategy = document.querySelector('input[name="compound_strategy"]:checked').value;

    const btn = e.target.querySelector('button');
    const originalText = btn.innerHTML;

    // UI DASHBOARD TRANSITION
    document.getElementById('empty-state').classList.add('hidden');
    document.getElementById('processing-state').classList.remove('hidden');
    document.getElementById('result-container').classList.add('hidden');

    btn.disabled = true;

    try {
        const response = await fetch('api/match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name1, name2, compound_strategy, use_carlton, use_wikidata, use_jrc, use_l2_model, strict_order, allow_initials, strict_unknowns, allow_stepwise })
        });

        const data = await response.json();
        displayResult(data);
    } catch (err) {
        console.error(err);
        alert('API Connection Failed.');
        document.getElementById('empty-state').classList.remove('hidden');
    } finally {
        document.getElementById('processing-state').classList.add('hidden');
        btn.disabled = false;
    }
});

function resetResultUI() {
    const resultContainer = document.getElementById('result-container');
    resultContainer.classList.add('hidden');
}

// Knowledge Base Override Mechanics
const btnToggleKb = document.getElementById('btn-toggle-kb');
const kbPanel = document.getElementById('kb-panel');
const kbChevron = document.getElementById('kb-chevron');

btnToggleKb.addEventListener('click', () => {
    kbPanel.classList.toggle('hidden');
    if (kbPanel.classList.contains('hidden')) {
        kbChevron.style.transform = 'rotate(0deg)';
    } else {
        kbChevron.style.transform = 'rotate(180deg)';
    }
});


async function executeKB(action) {
    const name1 = document.getElementById('name1').value.trim();
    const name2 = document.getElementById('name2').value.trim();
    const relationship_type = document.getElementById('kb-rel-type').value;
    const feedback = document.getElementById('kb-feedback');

    feedback.className = 'text-[10px] font-medium min-h-[12px] text-slate-500 animate-pulse';
    feedback.textContent = 'Processing...';

    try {
        const body = action === 'add' ? { name1, name2, relationship_type } : { name1, name2 };
        const response = await fetch(`api/kb/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();

        if (data.success) {
            feedback.className = 'text-[10px] font-medium min-h-[12px] text-emerald-400';
            feedback.textContent = data.message;
            // No longer hiding result UI, so user can see the effect of the override if they re-run
        } else {
            feedback.className = 'text-[10px] font-medium min-h-[12px] text-rose-400';
            feedback.textContent = data.error;
        }
    } catch (error) {
        feedback.className = 'text-xs text-center font-medium min-h-[16px] text-red-400';
        feedback.textContent = 'Failed to connect to database.';
    }
}

document.getElementById('btn-kb-add').addEventListener('click', () => executeKB('add'));
document.getElementById('btn-kb-remove').addEventListener('click', () => executeKB('remove'));

function displayResult(data) {
    const container = document.getElementById('result-container');
    const accent = document.getElementById('result-accent');
    const icon = document.getElementById('result-icon');
    const title = document.getElementById('result-title');
    const explanation = document.getElementById('result-explanation');
    const confidenceText = document.getElementById('result-confidence');
    const confidenceBar = document.getElementById('confidence-bar');

    // UI DASHBOARD TRANSITION: SHOW RESULTS
    document.getElementById('processing-state').classList.add('hidden');
    container.classList.remove('hidden');
    setTimeout(() => container.classList.remove('opacity-0'), 20);

    const percentage = Math.round(data.confidence * 100);
    confidenceText.innerText = `${percentage}%`;

    // Reset bar width for animation
    confidenceBar.style.width = '0%';
    setTimeout(() => {
        confidenceBar.style.width = `${percentage}%`;
    }, 100);

    explanation.innerText = data.explanation;

    // Reset Color Classes
    const colorClasses = [
        'text-emerald-400', 'text-amber-400', 'text-yellow-400', 'text-rose-400', 'text-green-500', 'text-orange-500',
        'bg-emerald-500', 'bg-amber-500', 'bg-yellow-500', 'bg-rose-500', 'bg-green-600', 'bg-orange-600',
        'shadow-[0_0_15px_rgba(16,185,129,0.8)]', 'shadow-[0_0_15px_rgba(245,158,11,0.8)]', 'shadow-[0_0_15px_rgba(234,179,8,0.8)]', 'shadow-[0_0_15px_rgba(244,63,94,0.8)]', 'shadow-[0_0_15px_rgba(22,163,74,0.8)]', 'shadow-[0_0_15px_rgba(234,88,12,0.8)]',
        'shadow-[0_0_10px_rgba(16,185,129,0.5)]', 'shadow-[0_0_10px_rgba(245,158,11,0.5)]', 'shadow-[0_0_10px_rgba(234,179,8,0.5)]', 'shadow-[0_0_10px_rgba(244,63,94,0.5)]', 'shadow-[0_0_10px_rgba(22,163,74,0.5)]', 'shadow-[0_0_10px_rgba(234,88,12,0.5)]'
    ];
    [icon, title, confidenceText, accent, confidenceBar].forEach(el => {
        colorClasses.forEach(cls => el.classList.remove(cls));
    });

    if (percentage === 100) {
        title.innerText = "Exact Match";
        title.classList.add('text-emerald-400');
        icon.setAttribute('data-lucide', 'check-circle-2');
        icon.classList.add('text-emerald-400');
        accent.classList.add('bg-emerald-500', 'shadow-[0_0_15px_rgba(16,185,129,0.8)]');
        confidenceBar.classList.add('bg-emerald-500', 'shadow-[0_0_10px_rgba(16,185,129,0.5)]');
        confidenceText.classList.add('text-emerald-400');
    } else if (percentage >= 90) {
        title.innerText = "Strong Match";
        title.classList.add('text-emerald-400');
        icon.setAttribute('data-lucide', 'check-circle-2');
        icon.classList.add('text-emerald-400');
        accent.classList.add('bg-emerald-500', 'shadow-[0_0_15px_rgba(16,185,129,0.8)]');
        confidenceBar.classList.add('bg-emerald-500', 'shadow-[0_0_10px_rgba(16,185,129,0.5)]');
        confidenceText.classList.add('text-emerald-400');
    } else if (percentage >= 80) {
        title.innerText = "Probable Match";
        title.classList.add('text-green-500');
        icon.setAttribute('data-lucide', 'check-circle-2');
        icon.classList.add('text-green-500');
        accent.classList.add('bg-green-600', 'shadow-[0_0_15px_rgba(22,163,74,0.8)]');
        confidenceBar.classList.add('bg-green-600', 'shadow-[0_0_10px_rgba(22,163,74,0.5)]');
        confidenceText.classList.add('text-green-500');
    } else if (percentage >= 50) {
        title.innerText = "Needs Review";
        title.classList.add('text-amber-400');
        icon.setAttribute('data-lucide', 'help-circle');
        icon.classList.add('text-amber-400');
        accent.classList.add('bg-amber-500', 'shadow-[0_0_15px_rgba(245,158,11,0.8)]');
        confidenceBar.classList.add('bg-amber-500', 'shadow-[0_0_10px_rgba(245,158,11,0.5)]');
        confidenceText.classList.add('text-amber-400');
    } else if (percentage >= 21) {
        title.innerText = "Unlikely Match";
        title.classList.add('text-orange-500');
        icon.setAttribute('data-lucide', 'help-circle');
        icon.classList.add('text-orange-500');
        accent.classList.add('bg-orange-600', 'shadow-[0_0_15px_rgba(234,88,12,0.8)]');
        confidenceBar.classList.add('bg-orange-600', 'shadow-[0_0_10px_rgba(234,88,12,0.5)]');
        confidenceText.classList.add('text-orange-500');
    } else {
        title.innerText = "Definite Non-Match";
        title.classList.add('text-rose-400');
        icon.setAttribute('data-lucide', 'x-circle');
        icon.classList.add('text-rose-400');
        accent.classList.add('bg-rose-500', 'shadow-[0_0_15px_rgba(244,63,94,0.8)]');
        confidenceBar.classList.add('bg-rose-500', 'shadow-[0_0_10px_rgba(244,63,94,0.5)]');
        confidenceText.classList.add('text-rose-400');
    }

    lucide.createIcons();
}
