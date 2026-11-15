/**
 * QUIZLY – QUIZ SETUP, TAKING & RESULTS ENGINE
 */

document.addEventListener('DOMContentLoaded', () => {

  // =========================================================================
  // 1. QUIZ SETUP & GENERATION FORM
  // =========================================================================
  const setupForm = document.getElementById('quizSetupForm');
  const generateBtn = document.getElementById('generateQuizBtn');
  const generationLoader = document.getElementById('generationLoader');

  if (setupForm && generateBtn) {
    setupForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const docId = setupForm.dataset.docId;
      const titleInput = document.getElementById('quizTitle');
      const numQuestions = document.querySelector('input[name="num_questions"]:checked')?.value || 10;
      const difficulty = document.querySelector('input[name="difficulty"]:checked')?.value || 'Mixed';
      const explanations = document.querySelector('input[name="include_explanations"]:checked')?.value !== 'no';

      generateBtn.disabled = true;
      generateBtn.style.display = 'none';
      if (generationLoader) generationLoader.style.display = 'block';

      try {
        const res = await fetch('/api/quiz/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            document_id: parseInt(docId),
            title: titleInput ? titleInput.value.trim() : '',
            num_questions: parseInt(numQuestions),
            difficulty: difficulty,
            include_explanations: explanations
          })
        });

        const data = await res.json();

        if (res.ok && data.success) {
          Quizly.showToast('Quiz generated successfully! Starting test...', 'success');
          setTimeout(() => {
            window.location.href = data.quiz_url;
          }, 800);
        } else {
          Quizly.showToast(data.message || 'Generation failed. Please try again.', 'error');
          generateBtn.disabled = false;
          generateBtn.style.display = 'inline-flex';
          if (generationLoader) generationLoader.style.display = 'none';
        }
      } catch (err) {
        Quizly.showToast('Network error during AI generation.', 'error');
        generateBtn.disabled = false;
        generateBtn.style.display = 'inline-flex';
        if (generationLoader) generationLoader.style.display = 'none';
      }
    });
  }

  // =========================================================================
  // 2. INTERACTIVE QUIZ TAKING ENGINE
  // =========================================================================
  const quizContainer = document.getElementById('takeQuizContainer');

  if (quizContainer) {
    const quizId = quizContainer.dataset.quizId;
    let questions = [];
    let currentIndex = 0;
    let userAnswers = {}; // { questionId: 'A' }
    let secondsElapsed = 0;
    let timerInterval = null;
    let isSubmitted = false;

    // DOM Elements
    const qNumEl = document.getElementById('currentQNum');
    const totalQEl = document.getElementById('totalQNum');
    const progressBar = document.getElementById('quizProgressBar');
    const qTextEl = document.getElementById('questionText');
    const optionsContainer = document.getElementById('optionsContainer');
    const prevBtn = document.getElementById('prevQBtn');
    const nextBtn = document.getElementById('nextQBtn');
    const submitBtn = document.getElementById('submitQuizBtn');
    const timerDisplay = document.getElementById('quizTimerDisplay');
    const confirmModal = document.getElementById('confirmSubmitModal');
    const modalConfirmBtn = document.getElementById('modalConfirmSubmit');
    const modalCancelBtn = document.getElementById('modalCancelSubmit');
    const unansweredCountEl = document.getElementById('unansweredCount');

    // Fetch quiz questions
    fetch(`/api/quiz/${quizId}`)
      .then(res => res.json())
      .then(data => {
        if (!data.success || !data.quiz.questions.length) {
          Quizly.showToast('Could not load quiz questions.', 'error');
          return;
        }
        questions = data.quiz.questions;
        if (totalQEl) totalQEl.textContent = questions.length;

        // Start Timer
        startTimer();

        // Render first question
        renderQuestion(currentIndex);
      })
      .catch(() => {
        Quizly.showToast('Error loading quiz.', 'error');
      });

    function startTimer() {
      if (!timerDisplay) return;
      timerInterval = setInterval(() => {
        secondsElapsed++;
        const mins = String(Math.floor(secondsElapsed / 60)).padStart(2, '0');
        const secs = String(secondsElapsed % 60).padStart(2, '0');
        timerDisplay.textContent = `${mins}:${secs}`;
      }, 1000);
    }

    function renderQuestion(index) {
      if (!questions[index]) return;
      const q = questions[index];

      if (qNumEl) qNumEl.textContent = index + 1;

      // Progress bar
      if (progressBar) {
        const percent = ((index + 1) / questions.length) * 100;
        progressBar.style.width = `${percent}%`;
      }

      if (qTextEl) qTextEl.textContent = q.question_text;

      // Render 4 options
      if (optionsContainer) {
        optionsContainer.innerHTML = '';
        const currentChoice = userAnswers[q.id];

        ['A', 'B', 'C', 'D'].forEach(letter => {
          const optText = q.options[letter];
          if (!optText) return;

          const optDiv = document.createElement('div');
          optDiv.className = `option-item ${currentChoice === letter ? 'selected' : ''}`;
          optDiv.innerHTML = `
            <div class="option-badge">${letter}</div>
            <div class="option-text">${optText}</div>
          `;

          if (!isSubmitted) {
            optDiv.addEventListener('click', () => {
              userAnswers[q.id] = letter;
              // Update visual selection
              optionsContainer.querySelectorAll('.option-item').forEach(el => el.classList.remove('selected'));
              optDiv.classList.add('selected');
            });
          }

          optionsContainer.appendChild(optDiv);
        });
      }

      // Update Navigation Buttons
      if (prevBtn) prevBtn.disabled = (index === 0);

      if (index === questions.length - 1) {
        if (nextBtn) nextBtn.style.display = 'none';
        if (submitBtn) submitBtn.style.display = 'inline-flex';
      } else {
        if (nextBtn) nextBtn.style.display = 'inline-flex';
        if (submitBtn) submitBtn.style.display = 'none';
      }
    }

    // Previous Button
    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        if (currentIndex > 0) {
          currentIndex--;
          renderQuestion(currentIndex);
        }
      });
    }

    // Next Button
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (currentIndex < questions.length - 1) {
          currentIndex++;
          renderQuestion(currentIndex);
        }
      });
    }

    // Submit Prompt
    if (submitBtn) {
      submitBtn.addEventListener('click', () => {
        const answeredCount = Object.keys(userAnswers).length;
        const unanswered = questions.length - answeredCount;

        if (unansweredCountEl) {
          if (unanswered > 0) {
            unansweredCountEl.textContent = `You have ${unanswered} unanswered question(s). Are you sure you want to finish?`;
          } else {
            unansweredCountEl.textContent = `You have answered all ${questions.length} questions. Ready to see your score?`;
          }
        }

        if (confirmModal) confirmModal.style.display = 'flex';
      });
    }

    // Modal Cancel
    if (modalCancelBtn) {
      modalCancelBtn.addEventListener('click', () => {
        if (confirmModal) confirmModal.style.display = 'none';
      });
    }

    // Modal Confirm Submission
    if (modalConfirmBtn) {
      modalConfirmBtn.addEventListener('click', async () => {
        clearInterval(timerInterval);
        isSubmitted = true;
        modalConfirmBtn.disabled = true;
        modalConfirmBtn.innerHTML = '<span class="spinner"></span> Evaluating...';

        try {
          const res = await fetch(`/api/quiz/${quizId}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              answers: userAnswers,
              time_taken: secondsElapsed
            })
          });

          const data = await res.json();
          if (res.ok && data.success) {
            Quizly.showToast('Quiz evaluated!', 'success');
            setTimeout(() => {
              window.location.href = data.result_url;
            }, 600);
          } else {
            Quizly.showToast(data.message || 'Submission error.', 'error');
            modalConfirmBtn.disabled = false;
            modalConfirmBtn.textContent = 'Yes, Submit Quiz';
          }
        } catch (e) {
          Quizly.showToast('Network error during submission.', 'error');
          modalConfirmBtn.disabled = false;
          modalConfirmBtn.textContent = 'Yes, Submit Quiz';
        }
      });
    }
  }

  // =========================================================================
  // 3. RESULTS ANIMATION
  // =========================================================================
  const radialBar = document.getElementById('resultRadialBar');
  if (radialBar) {
    const targetPercent = parseFloat(radialBar.dataset.percent || 0);
    // Circumference = 2 * PI * 70 = 440
    const circumference = 440;
    const offset = circumference - (targetPercent / 100) * circumference;

    setTimeout(() => {
      radialBar.style.strokeDashoffset = offset;
    }, 250);
  }
});

