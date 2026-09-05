// app.js — Dynamic Student Dashboard Logic for markkundo

document.addEventListener('DOMContentLoaded', async () => {
  // Load initial student dashboard data concurrently in parallel
  await Promise.all([
    loadStudentSubjects(),
    loadExamsData()
  ]);

  // If a target subject was passed via SSO or query param, select it
  const urlParams = new URLSearchParams(window.location.search);
  const targetSubject = urlParams.get('subject') || window.TARGET_SUBJECT;
  if (targetSubject) {
    const dropdown = document.getElementById('subjectDropdown');
    if (dropdown) {
      for (let i = 0; i < dropdown.options.length; i++) {
        if (dropdown.options[i].value.toLowerCase() === targetSubject.toLowerCase()) {
          dropdown.selectedIndex = i;
          switchSubject(dropdown.options[i].value);
          break;
        }
      }
    }
  }

  // Live filter search for subjects
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase().trim();
      const cards = document.querySelectorAll('.subject-mark-card');
      cards.forEach(card => {
        const title = card.querySelector('.subject-card-title')?.textContent.toLowerCase() || '';
        card.style.display = title.includes(query) ? '' : 'none';
      });
    });
  }
});

let cachedExamsData = {};

// 1. Fetch Subjects from DB and populate Subject Dropdown
async function loadStudentSubjects() {
  try {
    const res = await fetch('/api/student/subjects', { cache: 'no-store' });
    if (!res.ok) return;
    const subjects = await res.json();
    
    const dropdown = document.getElementById('subjectDropdown');
    if (!dropdown) return;
    
    dropdown.innerHTML = '<option value="">All Subjects</option>';
    subjects.forEach(subj => {
      const opt = document.createElement('option');
      opt.value = subj.name;
      opt.textContent = subj.name;
      dropdown.appendChild(opt);
    });
  } catch (err) {
    console.error('Error loading subjects:', err);
  }
}

// 2. Fetch Exams and performance data
async function loadExamsData() {
  try {
    const res = await fetch('/api/student/exams', { cache: 'no-store' });
    if (!res.ok) return;
    cachedExamsData = await res.json();
    
    const countEl = document.getElementById('examCount');
    const examTypes = Object.keys(cachedExamsData);
    if (countEl) countEl.textContent = examTypes.length;

    // Calculate Overall Score across all marks in DB
    let totalScore = 0;
    let totalMax = 0;
    let hasAnyMarks = false;

    examTypes.forEach(type => {
      const exam = cachedExamsData[type];
      if (exam && exam.marks) {
        exam.marks.forEach(m => {
          if (m.score !== null && m.score !== undefined && !isNaN(Number(m.score))) {
            totalScore += Number(m.score);
            totalMax += Number(m.max) || 100;
            hasAnyMarks = true;
          }
        });
      }
    });

    const overallDisplay = document.getElementById('overallScoreDisplay');
    const readinessBar = document.getElementById('readinessProgressBar');
    const readinessScoreVal = document.getElementById('readinessScoreVal');

    if (!hasAnyMarks || totalMax === 0) {
      if (overallDisplay) overallDisplay.innerHTML = '<span style="font-size: 15px; font-weight: 700; color: var(--amber);">Enter marks</span>';
      if (readinessBar) readinessBar.style.width = '0%';
      if (readinessScoreVal) readinessScoreVal.textContent = 'Enter marks';
    } else {
      const overallPct = Math.round((totalScore / totalMax) * 100);
      if (overallDisplay) overallDisplay.textContent = `${overallPct}%`;
      if (readinessBar) readinessBar.style.width = `${Math.min(overallPct, 100)}%`;
      if (readinessScoreVal) {
        if (overallPct >= 75) readinessScoreVal.textContent = 'High Mastery';
        else if (overallPct >= 50) readinessScoreVal.textContent = 'Steady Progress';
        else readinessScoreVal.textContent = 'Action Needed';
      }
    }

    // Render initial active exam tab (default ISA or first available)
    const initialExam = examTypes.includes('ISA') ? 'ISA' : (examTypes[0] || 'ISA');
    const activeBtn = Array.from(document.querySelectorAll('.exam-tab')).find(b => b.textContent.trim() === initialExam) || document.querySelector('.exam-tab');
    switchExamTab(activeBtn, initialExam);
  } catch (err) {
    console.error('Error loading exams:', err);
  }
}

// 3. Switch active exam tab & render clean cards
async function switchExamTab(btn, examType) {
  document.querySelectorAll('.exam-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  
  // Sync examDropdown if present
  const examDropdown = document.getElementById('examDropdown');
  if (examDropdown && examDropdown.value !== examType) {
    examDropdown.value = examType;
  }

  const panel = document.getElementById('examResultsPanel');
  if (!panel) return;
  
  panel.innerHTML = '<div class="focus-row-placeholder">Loading subject assessments...</div>';
  
  try {
    const examData = cachedExamsData[examType] || (await (await fetch('/api/student/exams')).json())[examType];
    
    if (!examData || !examData.marks || examData.marks.length === 0) {
      panel.innerHTML = `
        <div style="text-align: center; padding: 36px 20px; color: var(--text-muted);">
          <svg width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="margin-bottom: 10px; color: var(--text-dim);">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div style="font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 4px;">No assessment records for ${examType}</div>
          <div style="font-size: 12.5px;">Scores will appear here as soon as assessments are synced from Padikkunnundo.</div>
        </div>
      `;
      updateMetricTiles(examType, null, null, null);
      loadSubjectInsights(examType);
      return;
    }
    
    const subjectFilter = document.getElementById('subjectDropdown')?.value?.toLowerCase() || '';

    const cardsHtml = examData.marks
      .filter(m => !subjectFilter || m.subject.toLowerCase().includes(subjectFilter))
      .map(m => {
        const isEntered = (m.score !== null && m.score !== undefined && !isNaN(Number(m.score)));
        const score = isEntered ? Number(m.score) : null;
        const max = Number(m.max) || 100;
        const pct = (isEntered && max > 0) ? Math.round((score / max) * 100) : null;

        let badgeClass = 'badge-primary';
        let badgeLabel = 'Proficient';
        let barColor = 'linear-gradient(90deg, #4f46e5, #0284c7)';
        let scoreHtml = '';
        let pctHtml = '';
        let barWidth = 0;

        if (!isEntered) {
          badgeClass = 'badge-warning';
          badgeLabel = 'Enter Marks';
          barColor = 'var(--amber)';
          barWidth = 0;
          scoreHtml = `<div class="subject-card-score" style="font-size: 14px; font-weight: 700; color: var(--amber);">Enter marks</div>`;
          pctHtml = `<div class="subject-card-pct" style="font-size: 11.5px; color: var(--text-dim);">Pending</div>`;
        } else if (pct >= 85) {
          badgeClass = 'badge-success';
          badgeLabel = 'Outstanding';
          barColor = 'linear-gradient(90deg, #059669, #10b981)';
          barWidth = Math.min(pct, 100);
          scoreHtml = `<div class="subject-card-score">${score} <span style="font-size: 12px; color: var(--text-dim); font-weight: 500;">/ ${max}</span></div>`;
          pctHtml = `<div class="subject-card-pct">${pct}%</div>`;
        } else if (pct >= 60) {
          badgeClass = 'badge-primary';
          badgeLabel = 'Strong';
          barColor = 'linear-gradient(90deg, #4f46e5, #0284c7)';
          barWidth = Math.min(pct, 100);
          scoreHtml = `<div class="subject-card-score">${score} <span style="font-size: 12px; color: var(--text-dim); font-weight: 500;">/ ${max}</span></div>`;
          pctHtml = `<div class="subject-card-pct">${pct}%</div>`;
        } else if (pct >= 40) {
          badgeClass = 'badge-warning';
          badgeLabel = 'Developing';
          barColor = 'linear-gradient(90deg, #d97706, #f59e0b)';
          barWidth = Math.min(pct, 100);
          scoreHtml = `<div class="subject-card-score">${score} <span style="font-size: 12px; color: var(--text-dim); font-weight: 500;">/ ${max}</span></div>`;
          pctHtml = `<div class="subject-card-pct">${pct}%</div>`;
        } else {
          badgeClass = 'badge-danger';
          badgeLabel = 'Needs Focus';
          barColor = 'linear-gradient(90deg, #e11d48, #f43f5e)';
          barWidth = Math.min(pct, 100);
          scoreHtml = `<div class="subject-card-score">${score} <span style="font-size: 12px; color: var(--text-dim); font-weight: 500;">/ ${max}</span></div>`;
          pctHtml = `<div class="subject-card-pct">${pct}%</div>`;
        }

        return `
          <div class="subject-mark-card">
            <div class="subject-card-header">
              <div>
                <div class="subject-card-title">${m.subject}</div>
                <div class="subject-card-semester">${m.semester ? `Semester ${m.semester}` : 'Core Subject'} · ${examType}</div>
              </div>
              <div class="subject-card-score-box">
                ${scoreHtml}
                ${pctHtml}
              </div>
            </div>

            <div class="progress-track">
              <div class="progress-bar" style="width: ${barWidth}%; background: ${barColor};"></div>
            </div>

            <div class="subject-card-footer">
              <span class="badge ${badgeClass}">${badgeLabel}</span>
              <span>Weight: ${max} pts</span>
            </div>
          </div>
        `;
      }).join('');

    panel.innerHTML = `<div class="subject-mark-grid">${cardsHtml}</div>`;
    
    // Fetch Rank and Class Score
    fetchClassMetrics(examType);

    // Update performance insights
    loadSubjectInsights(examType);
  } catch (err) {
    panel.innerHTML = '<div style="color:var(--color-danger); padding: 16px;">Failed to load marks</div>';
  }
}

// 4. Fetch Class Rank & Average Metrics
async function fetchClassMetrics(examType) {
  const subject = document.getElementById('subjectDropdown')?.value || '';
  let url = `/api/student/class-rank/${examType}`;
  if (subject) url += `?subject=${encodeURIComponent(subject)}`;

  try {
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      const avgScoreVal = document.getElementById('avgScoreVal');
      const classScoreVal = document.getElementById('classScoreVal');
      const improvementVal = document.getElementById('improvementVal');

      if (avgScoreVal) {
        if (data.student_avg === null || data.student_avg === undefined) {
          avgScoreVal.textContent = 'Enter marks';
          avgScoreVal.style.fontSize = '16px';
        } else {
          avgScoreVal.textContent = `${data.student_avg}%`;
          avgScoreVal.style.fontSize = '';
        }
      }
      if (classScoreVal) classScoreVal.textContent = (data.class_avg !== undefined && data.class_avg !== null) ? `${data.class_avg}%` : '—';

      if (improvementVal) {
        if (data.student_avg === null || data.student_avg === undefined) {
          improvementVal.textContent = '—';
          improvementVal.style.color = 'var(--text-dim)';
        } else {
          const gap = Number(data.student_avg) - Number(data.class_avg || 0);
          improvementVal.textContent = gap >= 0 ? `+${gap.toFixed(1)}%` : `${gap.toFixed(1)}%`;
          improvementVal.style.color = gap >= 0 ? 'var(--emerald)' : 'var(--rose)';
        }
      }
    }
  } catch (e) {
    console.error('Error loading class rank metrics:', e);
  }
}

function updateMetricTiles(examType, studentAvg, classAvg, improvement) {
  const avgScoreVal = document.getElementById('avgScoreVal');
  const classScoreVal = document.getElementById('classScoreVal');
  const improvementVal = document.getElementById('improvementVal');

  if (avgScoreVal) {
    if (studentAvg === null || studentAvg === undefined) {
      avgScoreVal.textContent = 'Enter marks';
      avgScoreVal.style.fontSize = '16px';
    } else {
      avgScoreVal.textContent = `${studentAvg}%`;
      avgScoreVal.style.fontSize = '';
    }
  }
  if (classScoreVal) classScoreVal.textContent = classAvg !== null ? `${classAvg}%` : '—';
  if (improvementVal) {
    if (improvement === null || improvement === undefined) {
      improvementVal.textContent = '—';
      improvementVal.style.color = 'var(--text-dim)';
    } else {
      improvementVal.textContent = `${improvement}%`;
      improvementVal.style.color = improvement >= 0 ? 'var(--emerald)' : 'var(--rose)';
    }
  }
}

// 5. Exam dropdown change listener
function switchExam(examType) {
  const activeBtn = Array.from(document.querySelectorAll('.exam-tab')).find(b => b.textContent.trim() === examType);
  switchExamTab(activeBtn, examType);
}

// 6. Subject dropdown change listener
function switchSubject(subjectName) {
  const currentExam = document.getElementById('examDropdown')?.value || 'ISA';
  const activeBtn = Array.from(document.querySelectorAll('.exam-tab')).find(b => b.textContent.trim() === currentExam);
  switchExamTab(activeBtn, currentExam);
  fetchClassMetrics(currentExam);
  loadSubjectInsights(currentExam);
}

// 7. Load ML insights & study tips for selected exam / subject (clean, zero emojis)
async function loadSubjectInsights(examType) {
  const subject = document.getElementById('subjectDropdown')?.value || '';
  let url = `/api/student/insights/${examType}`;
  if (subject) url += `?subject=${encodeURIComponent(subject)}`;
  
  const focusList = document.getElementById('studyFocusList');
  if (!focusList) return;

  try {
    const res = await fetch(url);
    let insightText = "";
    let riskLevel = "info";
    let difficulty = "Moderate";
    let difficultyLevel = "moderate";
    let classAvgPct = 0;

    if (res.ok) {
      const insight = await res.json();
      insightText = insight.recommendation || "";
      riskLevel = insight.risk_level || "info";
      difficulty = insight.difficulty || "Moderate";
      difficultyLevel = insight.difficulty_level || "moderate";
      classAvgPct = insight.class_avg_pct || 0;
    }

    const diffBadgeStyles = {
      'hard': 'background: var(--rose-subtle); color: var(--rose); border: 1px solid #fecdd3;',
      'moderate': 'background: var(--primary-subtle); color: var(--primary); border: 1px solid #c7d2fe;',
      'easy': 'background: var(--emerald-subtle); color: var(--emerald); border: 1px solid #a7f3d0;'
    };

    const tips = [
      "<strong>Active Practice:</strong> Practice previous year question patterns and problems without looking at reference solutions.",
      "<strong>Spaced Revision:</strong> Dedicate regular focused sessions daily to high-credit subjects before semester exams.",
      "<strong>Targeted Review:</strong> Prioritize core chapters and difficult concepts to maximize subject performance."
    ];

    let benchmarkBadgeText = (classAvgPct !== null && classAvgPct !== undefined) 
      ? `${difficulty} Level · Class Avg: ${classAvgPct}%`
      : 'Pending Data · Class Avg: —';

    let content = `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
          <span style="font-size: 11.5px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;">Class Performance Benchmark</span>
          <span style="font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: var(--radius-full); ${diffBadgeStyles[difficultyLevel] || diffBadgeStyles['moderate']}">
            ${benchmarkBadgeText}
          </span>
        </div>

        ${insightText ? `
          <div class="insight-callout-card ${riskLevel === 'critical' ? 'insight-callout-critical' : 'insight-callout-info'}">
            <strong>Guidance & Analysis:</strong> ${insightText}
          </div>
        ` : ''}

        <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 2px;">
          <span style="font-size: 11.5px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;">Recommended Study Strategies</span>
          ${tips.map(tip => `
            <div class="study-tip-item">
              <div>${tip}</div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    focusList.innerHTML = content;

  } catch (err) {
    console.error('Error loading insights:', err);
  }
}

// 8. Load Priority Subjects & Schedule (Dynamic credit-weighted study hours & mark-based priority)
async function loadPrioritySchedule() {
  const container = document.getElementById('prioritySubjectsContainer');
  if (!container) return;

  try {
    const [subRes, examRes, insightRes] = await Promise.all([
      fetch('/api/student/subjects', { cache: 'no-store' }),
      fetch('/api/student/exams', { cache: 'no-store' }),
      fetch('/api/student/insights/ISA', { cache: 'no-store' })
    ]);

    const subjects = await subRes.json();
    let examsData = {};
    if (examRes.ok) {
      examsData = await examRes.json();
    }
    let insight = {};
    if (insightRes.ok) {
      insight = await insightRes.json();
    }

    if (!subjects || subjects.length === 0) {
      container.innerHTML = '<div class="card" style="padding: 28px; text-align: center; color: var(--text-muted);">No subjects found for this active semester.</div>';
      return;
    }

    // Helper: Calculate dynamic target study hours based on credits and marks
    function calculateDynamicTargetHours(credits, avgPct) {
      const cr = Number(credits) || 4;
      if (avgPct === null) {
        if (cr >= 5) return '6-8 hrs/week';
        if (cr === 4) return '5-6 hrs/week';
        if (cr === 3) return '4-5 hrs/week';
        return '3-4 hrs/week';
      }
      if (avgPct < 50) {
        // Low marks -> intensive study needed before SEA2
        if (cr >= 5) return '8-10 hrs/week';
        if (cr === 4) return '7-8 hrs/week';
        if (cr === 3) return '5-6 hrs/week';
        return '4-5 hrs/week';
      } else if (avgPct < 75) {
        // Moderate marks
        if (cr >= 5) return '5-7 hrs/week';
        if (cr === 4) return '4-5 hrs/week';
        if (cr === 3) return '3-4 hrs/week';
        return '2-3 hrs/week';
      } else {
        // High marks -> maintenance revision
        if (cr >= 5) return '3-4 hrs/week';
        if (cr === 4) return '2-3 hrs/week';
        if (cr === 3) return '2 hrs/week';
        return '1-2 hrs/week';
      }
    }

    // Compute marks and priority for each subject
    const subjectItems = subjects.map(s => {
      let totalScore = 0;
      let totalMax = 0;
      let markCount = 0;

      Object.keys(examsData).forEach(examKey => {
        const exam = examsData[examKey];
        if (exam && exam.marks) {
          const m = exam.marks.find(item => item.subject && item.subject.toLowerCase() === s.name.toLowerCase());
          if (m && m.score !== null && m.score !== undefined && !isNaN(Number(m.score))) {
            totalScore += Number(m.score);
            totalMax += Number(m.max) || 100;
            markCount++;
          }
        }
      });

      const hasMarks = (totalMax > 0 && markCount > 0);
      const avgPct = hasMarks ? Math.round((totalScore / totalMax) * 100) : null;
      const credits = Number(s.credits) || 4;
      const targetHours = calculateDynamicTargetHours(credits, avgPct);

      let priority = 'STABLE MASTERY';
      let badgeClass = 'badge-success';
      let borderLeftColor = 'var(--emerald)';
      let rankOrder = 4;
      let explanation = '';
      let scoreBadgeHtml = '';

      if (avgPct === null) {
        priority = 'NO MARKS ENTERED';
        badgeClass = 'badge-warning';
        borderLeftColor = 'var(--amber)';
        rankOrder = 3;
        explanation = `No evaluation marks entered yet for ${s.name}. Enter marks in Padikkunnundo to activate personalized SEA2 recommendations.`;
        scoreBadgeHtml = `<span style="font-size: 11.5px; color: var(--amber); font-weight: 600;">Status: Enter marks in Padikkunnundo</span>`;
      } else if (avgPct < 40) {
        priority = 'CRITICAL PRIORITY';
        badgeClass = 'badge-danger';
        borderLeftColor = 'var(--rose)';
        rankOrder = 1;
        explanation = `Current evaluation aggregate is ${avgPct}%. With ${credits} course credits, intensive topic revision and targeted practice are urgently required before SEA2.`;
        scoreBadgeHtml = `<span style="font-size: 11.5px; color: var(--rose); font-weight: 700;">Score: ${avgPct}% (Critical Focus)</span>`;
      } else if (avgPct < 50) {
        priority = 'HIGH PRIORITY';
        badgeClass = 'badge-danger';
        borderLeftColor = 'var(--rose)';
        rankOrder = 2;
        explanation = `Current evaluation aggregate is ${avgPct}%. With ${credits} course credits, prioritize problem solving to bridge foundational gaps before SEA2.`;
        scoreBadgeHtml = `<span style="font-size: 11.5px; color: var(--rose); font-weight: 700;">Score: ${avgPct}% (Action Needed)</span>`;
      } else if (avgPct < 75) {
        priority = 'MODERATE PRIORITY';
        badgeClass = 'badge-warning';
        borderLeftColor = 'var(--amber)';
        rankOrder = 4;
        explanation = `Current evaluation aggregate is ${avgPct}%. Maintaining structured weekly study sessions will help elevate performance above the cohort benchmark in SEA2.`;
        scoreBadgeHtml = `<span style="font-size: 11.5px; color: var(--amber); font-weight: 600;">Score: ${avgPct}% (Developing)</span>`;
      } else {
        priority = 'STABLE MASTERY';
        badgeClass = 'badge-success';
        borderLeftColor = 'var(--emerald)';
        rankOrder = 5;
        explanation = `Strong performance at ${avgPct}%. Maintain standard weekly practice to reinforce mastery for SEA2.`;
        scoreBadgeHtml = `<span style="font-size: 11.5px; color: var(--emerald); font-weight: 600;">Score: ${avgPct}% (High Mastery)</span>`;
      }

      return {
        name: s.name,
        program: s.program || 'BCA',
        semester: s.semester,
        credits: credits,
        avgPct: avgPct,
        rankOrder: rankOrder,
        priority: priority,
        badgeClass: badgeClass,
        borderLeftColor: borderLeftColor,
        explanation: explanation,
        scoreBadgeHtml: scoreBadgeHtml,
        targetHours: targetHours
      };
    });

    // Sort: Lowest score / highest priority first
    subjectItems.sort((a, b) => {
      if (a.rankOrder !== b.rankOrder) return a.rankOrder - b.rankOrder;
      if (a.avgPct !== null && b.avgPct !== null) return a.avgPct - b.avgPct;
      return 0;
    });

    container.innerHTML = subjectItems.map(item => `
      <div class="card" style="display: flex; flex-direction: column; gap: 12px; border-left: 4px solid ${item.borderLeftColor};">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <h3 style="font-family: var(--font-display); font-size: 16px; font-weight: 700; color: var(--text-main);">${item.name}</h3>
            <span class="badge ${item.badgeClass}">${item.priority}</span>
          </div>
          <span style="font-family: var(--font-display); font-size: 12px; font-weight: 700; color: var(--primary); background: var(--primary-subtle); border: 1px solid rgba(99, 102, 241, 0.2); padding: 4px 12px; border-radius: var(--radius-full);">
            Target: ${item.targetHours}
          </span>
        </div>
        <p style="font-size: 13px; color: var(--text-muted); line-height: 1.5;">
          ${item.explanation}
        </p>
        <div style="display: flex; gap: 18px; font-size: 11.5px; color: var(--text-dim); border-top: 1px solid var(--border-glass-subtle); padding-top: 10px; margin-top: 2px; flex-wrap: wrap; align-items: center;">
          <span>Program: <strong style="color: var(--text-body);">${item.program}</strong></span>
          <span>Semester: <strong style="color: var(--text-body);">${item.semester}</strong></span>
          <span>Credits: <strong style="color: var(--text-body);">${item.credits} Credits</strong></span>
          ${item.scoreBadgeHtml}
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading priority schedule:', err);
    container.innerHTML = '<div class="card" style="padding: 24px; color: var(--rose);">Failed to load priority schedule</div>';
  }
}

// 10. Navigation tab switching
function switchTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
  
  const activeTab = document.getElementById(`tab-${tabName === 'exams' ? 'dashboard' : tabName}`);
  const activeView = document.getElementById(`view-${tabName === 'dashboard' ? 'exams' : tabName}`);
  
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.add('active');

  if (tabName === 'schedule') {
    loadPrioritySchedule();
  }
}

