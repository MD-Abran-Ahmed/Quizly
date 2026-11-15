/**
 * QUIZLY – DASHBOARD & PERFORMANCE ANALYTICS
 */

document.addEventListener('DOMContentLoaded', () => {
  const statsOverview = document.getElementById('dashboardStatsOverview');
  const recentDocsList = document.getElementById('recentDocsList');
  const recentQuizzesList = document.getElementById('recentQuizzesList');

  // Load Overview Data if on dashboard
  if (statsOverview) {
    loadDashboardStats();
  }

  // Load Performance Analytics if on performance tab/page
  const analyticsContainer = document.getElementById('analyticsSection');
  if (analyticsContainer) {
    loadAnalyticsData();
  }

  async function loadDashboardStats() {
    try {
      const res = await fetch('/api/dashboard/stats');
      const data = await res.json();

      if (data.success) {
        // Animate counter values
        animateValue('statTotalDocs', 0, data.stats.total_documents, 800);
        animateValue('statTotalQuizzes', 0, data.stats.quizzes_generated, 800);
        animateValue('statQuestionsAttempted', 0, data.stats.questions_attempted, 800);

        const avgEl = document.getElementById('statAvgScore');
        if (avgEl) avgEl.textContent = `${data.stats.average_score}%`;

        // Render Recent Documents
        if (recentDocsList) {
          if (data.recent_documents.length === 0) {
            recentDocsList.innerHTML = `
              <div class="empty-state">
                <p>No documents uploaded yet.</p>
                <a href="/upload" class="btn btn-sm btn-primary">Upload Your First PDF</a>
              </div>
            `;
          } else {
            recentDocsList.innerHTML = data.recent_documents.map(doc => `
              <div class="activity-item">
                <div class="item-left">
                  <div class="item-badge-icon">
                    <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                  </div>
                  <div class="item-text">
                    <h5>${escapeHtml(doc.original_filename)}</h5>
                    <span>${doc.file_size_formatted} &bull; ${doc.page_count} pages &bull; ${doc.created_at}</span>
                  </div>
                </div>
                <div class="item-right">
                  <a href="/quiz/setup/${doc.id}" class="btn btn-sm btn-glass">Generate Quiz</a>
                </div>
              </div>
            `).join('');
          }
        }

        // Render Recent Quizzes
        if (recentQuizzesList) {
          if (data.recent_quizzes.length === 0) {
            recentQuizzesList.innerHTML = `
              <div class="empty-state">
                <p>No quizzes created yet.</p>
                <a href="/upload" class="btn btn-sm btn-glass">Upload PDF to Begin</a>
              </div>
            `;
          } else {
            recentQuizzesList.innerHTML = data.recent_quizzes.map(quiz => {
              let scoreBadge = '<span class="score-badge score-mid">Unattempted</span>';
              if (quiz.last_score !== null && quiz.last_score !== undefined) {
                const roundedScore = Math.round(Number(quiz.last_score));
                const scoreClass = roundedScore >= 80 ? 'score-high' : (roundedScore >= 60 ? 'score-mid' : 'score-low');
                scoreBadge = `<span class="score-badge ${scoreClass}">${roundedScore}%</span>`;
              }
              return `
                <div class="activity-item">
                  <div class="item-left">
                    <div class="item-badge-icon">
                      <svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
                    </div>
                    <div class="item-text">
                      <h5>${escapeHtml(quiz.title)}</h5>
                      <span>${quiz.num_questions} Questions &bull; ${escapeHtml(quiz.difficulty)}</span>
                    </div>
                  </div>
                  <div class="item-right">
                    ${scoreBadge}
                    <a href="/quiz/${quiz.id}" class="btn btn-sm btn-primary">Take Quiz</a>
                  </div>
                </div>
              `;
            }).join('');
          }
        }
      }
    } catch (e) {
      console.error('Error fetching dashboard stats:', e);
    }
  }

  async function loadAnalyticsData() {
    try {
      const res = await fetch('/api/analytics');
      const data = await res.json();
      if (!data.success) return;

      const totalCompletedEl = document.getElementById('analyticTotalCompleted');
      const highestScoreEl = document.getElementById('analyticHighestScore');
      const totalCorrectEl = document.getElementById('analyticTotalCorrect');
      const totalIncorrectEl = document.getElementById('analyticTotalIncorrect');

      if (totalCompletedEl) totalCompletedEl.textContent = data.total_quizzes_completed;
      if (highestScoreEl) highestScoreEl.textContent = `${data.highest_score}%`;
      if (totalCorrectEl) totalCorrectEl.textContent = data.total_correct;
      if (totalIncorrectEl) totalIncorrectEl.textContent = data.total_incorrect;

      // Render Weekly Bar Chart
      const chartContainer = document.getElementById('weeklyActivityChart');
      if (chartContainer && data.weekly_activity) {
        chartContainer.innerHTML = '';
        const days = Object.keys(data.weekly_activity);
        const maxVal = Math.max(...Object.values(data.weekly_activity), 1);

        days.forEach(day => {
          const val = data.weekly_activity[day];
          const heightPercent = Math.max((val / maxVal) * 100, 8);

          const col = document.createElement('div');
          col.style.cssText = 'flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.5rem;';
          col.innerHTML = `
            <div style="font-size: 0.76rem; color: var(--gold-light); font-weight: 600;">${val > 0 ? val : ''}</div>
            <div style="width: 100%; height: 140px; background: rgba(255, 255, 255, 0.04); border-radius: 8px; display: flex; align-items: flex-end; padding: 3px;">
              <div style="width: 100%; height: ${heightPercent}%; background: linear-gradient(180deg, #D6BC83, rgba(214, 188, 131, 0.2)); border-radius: 6px; transition: height 0.6s ease;"></div>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted);">${day}</div>
          `;
          chartContainer.appendChild(col);
        });
      }
    } catch (e) {
      console.error('Error loading analytics:', e);
    }
  }

  function animateValue(id, start, end, duration) {
    const el = document.getElementById(id);
    if (!el) return;
    if (start === end) {
      el.textContent = end;
      return;
    }
    const range = end - start;
    let current = start;
    const increment = end > start ? 1 : -1;
    const stepTime = Math.abs(Math.floor(duration / range)) || 20;

    const timer = setInterval(() => {
      current += increment;
      el.textContent = current;
      if (current === end) {
        clearInterval(timer);
      }
    }, stepTime);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
});

// Global Quiz Deletion Helper
window.deleteQuiz = async function(quizId, quizTitle) {
  if (!confirm(`Delete quiz "${quizTitle}"? All attempts and records will be removed.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/quizzes/${quizId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.success) {
      Quizly.showToast('Quiz deleted.', 'success');
      const card = document.getElementById(`quiz-card-${quizId}`);
      if (card) {
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => card.remove(), 300);
      } else {
        setTimeout(() => window.location.reload(), 400);
      }
    } else {
      Quizly.showToast(data.message || 'Could not delete quiz.', 'error');
    }
  } catch (e) {
    Quizly.showToast('Error deleting quiz.', 'error');
  }
};

