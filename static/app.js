// app.js — Dynamic Student Dashboard Logic for markkundo

document.addEventListener('DOMContentLoaded', async () => {
  await loadStudentSubjects();
  await loadExamsData();
  await loadNotifications();

  // If a target subject was passed via SSO or query param, select it
  const urlParams = new URLSearchParams(window.location.search);
  const targetSubject = urlParams.get('subject') || window.TARGET_SUBJECT;
  if (targetSubject) {
    const dropdown = document.getElementById('subjectDropdown');
    if (dropdown) {
      // Find matching option
      for (let i = 0; i < dropdown.options.length; i++) {
        if (dropdown.options[i].value.toLowerCase() === targetSubject.toLowerCase()) {
          dropdown.selectedIndex = i;
          switchSubject(dropdown.options[i].value);
          break;
        }
      }
    }
  }
});

let cachedExamsData = {};

// 1. Fetch Subjects from DB and populate Subject Dropdown
async function loadStudentSubjects() {
  try {
    const res = await fetch('/api/student/subjects');
    if (!res.ok) return;
    const subjects = await res.json();
    
    const dropdown = document.getElementById('subjectDropdown');
    if (!dropdown) return;
    
    dropdown.innerHTML = '<option value="">All Subjects ▾</option>';
    subjects.forEach(subj => {
      const opt = document.createElement('option');
      opt.value = subj.name;
      opt.textContent = `${subj.name} ▾`;
      dropdown.appendChild(opt);
    });
  } catch (err) {
    console.error('Error loading subjects:', err);
  }
}

// 2. Fetch Exams and performance data
async function loadExamsData() {
  try {
    const res = await fetch('/api/student/exams');
    if (!res.ok) return;
    cachedExamsData = await res.json();
    
    const countEl = document.getElementById('examCount');
    const examTypes = Object.keys(cachedExamsData);
    if (countEl) countEl.textContent = examTypes.length;

    // Calculate Overall Score across all marks in DB
    let totalScore = 0;
    let totalMax = 0;
    examTypes.forEach(type => {
      const exam = cachedExamsData[type];
      if (exam && exam.marks) {
        exam.marks.forEach(m => {
          totalScore += Number(m.score) || 0;
          totalMax += Number(m.max) || 100;
        });
      }
    });

    const overallPct = totalMax > 0 ? Math.round((totalScore / totalMax) * 100) : 0;
    const overallDisplay = document.getElementById('overallScoreDisplay');
    if (overallDisplay) overallDisplay.textContent = `${overallPct}%`;

    // Render initial active exam tab (default ISA or first available)
    const initialExam = examTypes.includes('ISA') ? 'ISA' : (examTypes[0] || 'ISA');
    const activeBtn = Array.from(document.querySelectorAll('.exam-tab')).find(b => b.textContent.trim() === initialExam) || document.querySelector('.exam-tab');
    switchExamTab(activeBtn, initialExam);
  } catch (err) {
    console.error('Error loading exams:', err);
  }
}

// 3. Switch active exam tab
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
  
  panel.innerHTML = '<div style="color:var(--secondary-text); padding: 16px;">Loading marks...</div>';
  
  try {
    const examData = cachedExamsData[examType] || (await (await fetch('/api/student/exams')).json())[examType];
    
    if (!examData || !examData.marks || examData.marks.length === 0) {
      panel.innerHTML = `<div style="color:var(--secondary-text); padding: 16px;">No marks recorded for ${examType}</div>`;
      updateMetricTiles(examType, 0, null, 0);
      loadSubjectInsights(examType);
      return;
    }
    
    panel.innerHTML = examData.marks.map(m => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; background: var(--card-surface); border: 1px solid var(--card-border); border-radius: 10px;">
        <div>
          <span style="font-weight: 600; font-size: 14px; color: var(--body-text);">${m.subject}</span>
          ${m.semester ? `<span style="font-size: 11px; color: var(--secondary-text); margin-left: 8px;">Sem ${m.semester}</span>` : ''}
        </div>
        <span style="font-weight: 700; color: var(--data-blue); font-size: 15px;">${m.score} / ${m.max}</span>
      </div>
    `).join('');
    
    // Fetch Rank and Class Score
    fetchClassMetrics(examType);

    // Update performance insights
    loadSubjectInsights(examType);
  } catch (err) {
    panel.innerHTML = '<div style="color:var(--secondary-text); padding: 16px;">Failed to load marks</div>';
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

      if (avgScoreVal) avgScoreVal.textContent = `${data.student_avg || 0}%`;
      if (classScoreVal) classScoreVal.textContent = `${data.class_avg || '—'}%`;

      const gap = (data.student_avg || 0) - (data.class_avg || 0);
      if (improvementVal) {
        improvementVal.textContent = gap >= 0 ? `+${gap.toFixed(1)}%` : `${gap.toFixed(1)}%`;
        improvementVal.style.color = gap >= 0 ? 'var(--color-accent)' : 'var(--color-danger)';
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

  if (avgScoreVal) avgScoreVal.textContent = `${studentAvg}%`;
  if (classScoreVal) classScoreVal.textContent = classAvg !== null ? `${classAvg}%` : '—';
  if (improvementVal) improvementVal.textContent = `${improvement}%`;
}

// 5. Exam dropdown change listener
function switchExam(examType) {
  const activeBtn = Array.from(document.querySelectorAll('.exam-tab')).find(b => b.textContent.trim() === examType);
  switchExamTab(activeBtn, examType);
}

// 6. Subject dropdown change listener
function switchSubject(subjectName) {
  const currentExam = document.getElementById('examDropdown')?.value || 'ISA';
  fetchClassMetrics(currentExam);
  loadSubjectInsights(currentExam);
}

// 7. Load ML insights & study tips for selected exam / subject
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
      'hard': 'background: rgba(255, 77, 109, 0.15); color: #ff6b8b; border: 1px solid rgba(255, 77, 109, 0.3);',
      'moderate': 'background: rgba(108, 99, 255, 0.15); color: var(--grad-start); border: 1px solid rgba(108, 99, 255, 0.3);',
      'easy': 'background: rgba(0, 212, 170, 0.15); color: #00d4aa; border: 1px solid rgba(0, 212, 170, 0.3);'
    };

    const tips = [
      "⚡ <strong>Active Recall:</strong> Practice previous year questions for core concepts instead of passive re-reading.",
      "⏱️ <strong>Time Allocation:</strong> Spend 45 minutes on weak areas followed by 15 minutes of revision daily.",
      "📝 <strong>Exam Strategy:</strong> Answer high-weightage theory and code questions first to secure core marks."
    ];

    let content = `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
          <span style="font-size: 12px; font-weight: 700; color: var(--secondary-text); text-transform: uppercase; letter-spacing: 0.05em;">Cohort Assessment Context</span>
          <span style="font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 20px; ${diffBadgeStyles[difficultyLevel] || diffBadgeStyles['moderate']}">
            📊 ${difficulty} Exam · Class Avg: ${classAvgPct}%
          </span>
        </div>

        ${insightText ? `
          <div style="padding: 14px 16px; background: var(--tile-blue); border-left: 4px solid ${riskLevel === 'critical' ? 'var(--color-danger)' : 'var(--grad-start)'}; border-radius: 8px; font-size: 13px; color: var(--body-text); line-height: 1.6;">
            <strong>Analysis & Feedback:</strong> ${insightText}
          </div>
        ` : ''}

        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 4px;">
          <span style="font-size: 12px; font-weight: 700; color: var(--secondary-text); text-transform: uppercase; letter-spacing: 0.05em;">Recommended Study Practices</span>
          ${tips.map(tip => `
            <div style="padding: 10px 14px; background: var(--color-bg); border: 1px solid var(--card-border); border-radius: 8px; font-size: 13px; color: var(--secondary-text); line-height: 1.5;">
              ${tip}
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

// 8. Notifications toggle and actions
function toggleNotifPanel() {
  const panel = document.getElementById('notifPanel');
  if (panel) panel.classList.toggle('active');
}

async function loadNotifications() {
  try {
    const res = await fetch('/api/student/notifications');
    if (!res.ok) return;
    const notifs = await res.json();
    
    const badge = document.getElementById('notifBadge');
    const unread = notifs.filter(n => !n.is_read).length;
    if (badge) badge.textContent = unread;
    
    const list = document.getElementById('notifList');
    if (list) {
      if (notifs.length === 0) {
        list.innerHTML = '<div style="color:var(--secondary-text); font-size: 13px; padding: 16px; text-align: center;">No notifications</div>';
      } else {
        list.innerHTML = notifs.map(n => `
          <div style="padding: 12px; background: var(--color-bg); border-radius: 8px; margin-bottom: 8px; font-size: 12px; border-left: 3px solid ${n.is_read ? 'var(--card-border)' : 'var(--grad-start)'};">
            <div style="color: var(--body-text); font-size: 13px;">${n.message}</div>
            <div style="color: var(--secondary-text); font-size: 11px; margin-top: 4px;">${n.exam || ''} · ${n.timestamp ? new Date(n.timestamp).toLocaleDateString() : ''}</div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Error loading notifications:', err);
  }
}

async function markAllAsRead() {
  try {
    await fetch('/api/student/notifications/read-all', { method: 'POST' });
    await loadNotifications();
  } catch (err) {
    console.error('Error marking notifications as read:', err);
  }
}

// 9. Load Priority Subjects & Schedule
async function loadPrioritySchedule() {
  const container = document.getElementById('prioritySubjectsContainer');
  if (!container) return;

  try {
    const [subRes, examRes, insightRes] = await Promise.all([
      fetch('/api/student/subjects'),
      fetch('/api/student/exams'),
      fetch('/api/student/insights/ISA')
    ]);

    const subjects = await subRes.json();
    let insight = {};
    if (insightRes.ok) {
      insight = await insightRes.json();
    }

    const weakSubjects = insight.weak_subjects || [];
    
    if (subjects.length === 0) {
      container.innerHTML = '<div class="card" style="padding: 24px; text-align: center; color: var(--secondary-text);">No subjects found for this semester.</div>';
      return;
    }

    // Sort subjects: Weakest / highest priority first
    const sorted = subjects.map(s => {
      let isHighPriority = weakSubjects.includes(s.name);
      let explanation = isHighPriority 
        ? `ML Analysis flagged a score gap in ${s.name}. Dedicated review is strongly recommended before upcoming assessments.`
        : `Performance in ${s.name} is stable. Maintain weekly revision schedule to keep mastery high.`;
      
      return {
        name: s.name,
        program: s.program || 'BCA',
        semester: s.semester,
        credits: s.credits || 4,
        numPapers: s.num_papers || 0,
        priority: isHighPriority ? 'HIGH PRIORITY' : 'MODERATE / STABLE',
        badgeClass: isHighPriority ? 'badge-danger' : 'badge-success',
        explanation: explanation,
        hoursPerWeek: isHighPriority ? '6-8 hrs/week' : '3-4 hrs/week'
      };
    }).sort((a, b) => (a.priority === 'HIGH PRIORITY' ? -1 : 1));

    container.innerHTML = sorted.map(item => `
      <div class="card" style="display: flex; flex-direction: column; gap: 12px; border-left: 4px solid ${item.priority === 'HIGH PRIORITY' ? 'var(--color-danger)' : 'var(--color-accent)'};">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <h3 style="font-size: 16px; font-weight: 700;">${item.name}</h3>
            <span class="badge ${item.badgeClass}">${item.priority}</span>
          </div>
          <span style="font-size: 13px; font-weight: 600; color: var(--grad-start); background: var(--tile-blue); padding: 4px 12px; border-radius: 20px;">
            📅 Recommended: ${item.hoursPerWeek}
          </span>
        </div>
        <p style="font-size: 14px; color: var(--secondary-text); line-height: 1.5;">
          ${item.explanation}
        </p>
        <div style="display: flex; gap: 16px; font-size: 12px; color: var(--secondary-text); border-top: 1px solid var(--card-border); padding-top: 10px; margin-top: 4px;">
          <span>Program: <strong>${item.program}</strong></span>
          <span>Semester: <strong>${item.semester}</strong></span>
          <span>Credits: <strong>${item.credits}</strong></span>
          <span>Past Papers: <strong>${item.numPapers} available</strong></span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading priority schedule:', err);
    container.innerHTML = '<div class="card" style="padding: 24px; color: var(--color-danger);">Failed to load priority schedule</div>';
  }
}

// 10. Navigation tab switching
function switchTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
  
  const activeTab = document.getElementById(`tab-${tabName}`);
  const activeView = document.getElementById(`view-${tabName === 'exams' ? 'exams' : tabName}`);
  
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.add('active');

  if (tabName === 'schedule') {
    loadPrioritySchedule();
  }
}
