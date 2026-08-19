// Integração com a API de Recordes do Backend FastAPI

/**
 * Busca a lista de recordes do backend e renderiza na interface
 */
async function fetchScores() {
    const scoresListElement = document.getElementById('scores-list');
    if (!scoresListElement) return;

    try {
        const response = await fetch('/api/scores');
        if (!response.ok) {
            throw new Error('Falha ao obter pontuações.');
        }
        const scores = await response.json();
        renderScores(scores);
        return scores;
    } catch (error) {
        console.error('Erro ao buscar placar:', error);
        scoresListElement.innerHTML = `<li class="loading" style="color: var(--neon-red)">Erro ao carregar recordes.</li>`;
        return [];
    }
}

/**
 * Renderiza os recordes na listagem da página
 * @param {Array} scores Lista de objetos contendo {name, score, level, lines}
 */
function renderScores(scores) {
    const scoresListElement = document.getElementById('scores-list');
    if (!scoresListElement) return;

    if (scores.length === 0) {
        scoresListElement.innerHTML = `<li class="loading">Nenhum recorde ainda.</li>`;
        return;
    }

    // Limpa a lista
    scoresListElement.innerHTML = '';

    scores.forEach((entry, index) => {
        const li = document.createElement('li');
        
        const rankSpan = document.createElement('span');
        rankSpan.className = 'score-rank';
        rankSpan.textContent = `#${index + 1}`;
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'score-name';
        nameSpan.textContent = entry.name.toUpperCase();
        
        const valSpan = document.createElement('span');
        valSpan.className = 'score-val';
        valSpan.textContent = entry.score.toLocaleString();

        li.appendChild(rankSpan);
        li.appendChild(nameSpan);
        li.appendChild(valSpan);
        
        scoresListElement.appendChild(li);
    });
}

/**
 * Envia uma nova pontuação de recorde para o backend
 * @param {string} name Nome do jogador
 * @param {number} score Pontuação total
 * @param {number} level Nível atingido
 * @param {number} lines Quantidade de linhas completadas
 */
async function submitScore(name, score, level, lines) {
    try {
        const trimmedName = name.trim().toUpperCase() || 'ANÔNIMO';
        const response = await fetch('/api/scores', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: trimmedName,
                score: score,
                level: level,
                lines: lines
            })
        });

        if (!response.ok) {
            throw new Error('Erro ao enviar pontuação para o servidor.');
        }

        const updatedScores = await response.json();
        renderScores(updatedScores);
        return true;
    } catch (error) {
        console.error('Erro ao registrar pontuação:', error);
        alert('Não foi possível salvar sua pontuação no ranking da nuvem, mas parabéns pela partida!');
        return false;
    }
}

/**
 * Verifica se a pontuação se qualifica para o Top 10 atual
 * @param {number} score Pontuação final do jogador
 * @param {Array} scoresList Lista atual de recordes
 * @returns {boolean} True se for um novo recorde
 */
function isHighScore(score, scoresList) {
    if (score <= 0) return false;
    // Se a lista tiver menos de 10 entradas, qualquer pontuação maior que 0 se qualifica
    if (scoresList.length < 10) return true;
    // Se não, verifica se é maior que o menor score do top 10
    const lowestHighScore = scoresList[scoresList.length - 1].score;
    return score > lowestHighScore;
}

// Executar busca de placar ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    fetchScores();
});
