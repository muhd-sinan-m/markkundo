// app.js — Student Dashboard Logic for markkundo

document.addEventListener('DOMContentLoaded', () => {
  loadStudentSubjects();
  loadExamsData();
  loadNotifications();
});

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
    const data = await res.json();
    
    const countEl = document.getElementById('examCount');
    if (countEl) countEl.textContent = Object.keys(data).length;
    
    // Render initial ISA results
    switchExamTab(document.querySelector('.exam-tab'), 'ISA');
  } catch (err) {
    console.error('Error loading exams:', err);
  }
}

// 3. Switch active exam tab
async function switchExamTab(btn, examType) {
  document.querySelectorAll('.exam-tab').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  
  const panel = document.getElementById('examResultsPanel');
  if (!panel) return;
  
  panel.innerHTML = '<div style="color:var(--secondary-text); padding: 16px;">Loading marks...</div>';
  
  try {
    const res = await fetch('/api/student/exams');
    const data = await res.json();
    const examData = data[examType];
    
    if (!examData || !examData.marks || examData.marks.length === 0) {
      panel.innerHTML = `<div style="color:var(--secondary-text); padding: 16px;">No marks recorded for ${examType}</div>`;
      return;
    }
    
    panel.innerHTML = examData.marks.map(m => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: var(--card-surface); border: 1px solid var(--card-border); border-radius: 10px;">
        <span style="font-weight: 500;">${m.subject}</span>
        <span style="font-weight: 700; color: var(--data-blue);">${m.score} / ${m.max}</span>
      </div>
    `).join('');
    
    // Also update performance analysis
    loadSubjectInsights(examType);
  } catch (err) {
    panel.innerHTML = '<div style="color:var(--secondary-text); padding: 16px;">Failed to load marks</div>';
  }
}

// 4. Load ML insights & study tips for selected exam / subject
async function loadSubjectInsights(examType) {
  const subject = document.getElementById('subjectDropdown')?.value || '';
  let url = `/api/student/insights/${examType}`;
  if (subject) url += `?subject=${encodeURIComponent(subject)}`;
  
  const focusList = document.getElementById('studyFocusList');
  if (!focusList) return;

  try {
    const res = await fetch(url);
    let insightText = "";
    if (res.ok) {
      const insight = await res.json();
      insightText = insight.recommendation || "";
    }

    const tips = [
      "⚡ <strong>Active Recall:</strong> Practice previous year questions for core concepts instead of passive re-reading.",
      "⏱️ <strong>Time Allocation:</strong> Spend 45 minutes on weak areas followed by 15 minutes of revision daily.",
      "📝 <strong>Exam Strategy:</strong> Answer high-weightage theory and code questions first to secure core marks."
    ];

    let content = `
      <div style="display: flex; flex-direction: column; gap: 12px;">
        ${insightText ? `
          <div style="padding: 12px; background: var(--tile-blue); border-left: 4px solid var(--grad-start); border-radius: 8px; font-size: 13px; color: var(--body-text); line-height: 1.5;">
            <strong>Target Insight:</strong> ${insightText}
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

// 5. Subject dropdown change listener
function switchSubject(subjectName) {
  const currentExam = document.getElementById('examDropdown')?.value || 'ISA';
  loadSubjectInsights(currentExam);
}

// 6. Notifications panel toggle
function toggleNotifPanel() {
  const panel = document.getElementById('notifPanel');
  if (panel) panel.classList.toggle('active');
}

// 7. Load Notifications
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
        list.innerHTML = '<div style="color:var(--secondary-text); font-size: 12px;">No notifications</div>';
      } else {
        list.innerHTML = notifs.map(n => `
          <div style="padding: 10px; background: var(--color-bg); border-radius: 8px; margin-bottom: 8px; font-size: 12px; border-left: 3px solid ${n.is_read ? 'var(--card-border)' : 'var(--grad-start)'};">
            <div style="color: var(--body-text);">${n.message}</div>
            <div style="color: var(--secondary-text); font-size: 10px; margin-top: 4px;">${n.exam || ''}</div>
          </div>
        `).join('');
      }
    }
  } catch (err) {
    console.error('Error loading notifications:', err);
  }
}

// 8. Load Priority Subjects & Schedule
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
    const exams = await examRes.json();
    let insight = {};
    if (insightRes.ok) {
      insight = await insightRes.json();
    }

    const weakSubjects = insight.weak_subjects || [];
    
    // Sort subjects: Weakest / highest priority first
    const sorted = subjects.map(s => {
      let isHighPriority = weakSubjects.includes(s.name);
      let explanation = isHighPriority 
        ? `ML Analysis flagged a score gap in ${s.name}. Dedicated review is strongly recommended before upcoming assessments.`
        : `Performance in ${s.name} is stable. Maintain weekly revision schedule to keep mastery high.`;
      
      return {
        name: s.name,
        program: s.program,
        semester: s.semester,
        numPapers: s.num_papers,
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
          <span>Past Papers: <strong>${item.numPapers} available</strong></span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error loading priority schedule:', err);
    container.innerHTML = '<div class="card" style="padding: 24px; color: var(--color-danger);">Failed to load priority schedule</div>';
  }
}

// 9. Navigation tab switching
function switchTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.page-view').forEach(v => v.classList.remove('active'));
  
  const activeTab = document.getElementById(`tab-${tabName}`);
  const activeView = document.getElementById(`view-${tabName === 'exams' ? 'exams' : tabName}`);
  
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.active ? null : activeView.classList.add('active');

  if (tabName === 'schedule') {
    loadPrioritySchedule();
  }
}

