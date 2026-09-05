// admin.js — Admin Dashboard Logic for markkundo

document.addEventListener('DOMContentLoaded', () => {
  loadAdminStats();
  loadStudentsTable();
  loadClusterDistribution('ISA');
  loadAtRiskStudents('ISA');

  const entryStudentSelect = document.getElementById('entryStudentSelect');
  if (entryStudentSelect) {
    entryStudentSelect.addEventListener('change', loadStudentMarksForEntry);
  }

  const entryExamType = document.getElementById('entryExamType');
  if (entryExamType) {
    entryExamType.addEventListener('change', loadStudentMarksForEntry);
  }
});

let clusterChartInstance = null;

async function loadAdminStats() {
  try {
    const res = await fetch('/admin/api/db-status');
    if (!res.ok) return;
    const data = await res.json();
    
    const studentsEl = document.getElementById('totalStudents');
    const marksEl = document.getElementById('totalMarks');
    const insightsEl = document.getElementById('totalInsights');

    if (studentsEl) studentsEl.textContent = data.students || 0;
    if (marksEl) marksEl.textContent = data.marks || 0;
    if (insightsEl) insightsEl.textContent = data.insights || 0;
  } catch (e) {
    console.error('Error loading admin stats:', e);
  }
}

async function loadStudentsTable() {
  try {
    const res = await fetch('/admin/api/students');
    if (!res.ok) return;
    const students = await res.json();
    
    const tbody = document.getElementById('studentsTable');
    if (!tbody) return;
    
    if (students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding: 12px; text-align: center; color: var(--secondary-text);">No students found</td></tr>';
      return;
    }
    
    tbody.innerHTML = students.map(s => `
      <tr style="border-bottom: 1px solid var(--card-border);">
        <td style="padding: 12px; font-weight: 600; color: var(--text-main);">${escapeHtml(s.name)}</td>
        <td style="padding: 12px; color: var(--secondary-text);">${escapeHtml(s.email)}</td>
        <td style="padding: 12px;">${escapeHtml(s.reg_no)}</td>
        <td style="padding: 12px;">Semester ${s.semester}</td>
        <td style="padding: 12px; text-align: right;">
          <button onclick="deleteStudent(${s.id}, '${escapeHtml(s.name)}')" 
            style="background: var(--rose-subtle); color: var(--rose); border: 1px solid #fecdd3; padding: 4px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 600; cursor: pointer; transition: all 0.2s ease;">
            Delete
          </button>
        </td>
      </tr>
    `).join('');
    
    // Also populate student dropdown in Enter Marks tab
    const entrySelect = document.getElementById('entryStudentSelect');
    if (entrySelect) {
      entrySelect.innerHTML = '<option value="">Select Student ▾</option>' + 
        students.map(s => `<option value="${s.id}">${escapeHtml(s.name)} (${escapeHtml(s.reg_no)})</option>`).join('');
    }
  } catch (e) {
    console.error('Error loading students table:', e);
  }
}

async function addStudent() {
  const name = document.getElementById('studentName')?.value?.trim();
  const email = document.getElementById('studentEmail')?.value?.trim();
  const reg_no = document.getElementById('studentRegNo')?.value?.trim();
  const semester = parseInt(document.getElementById('studentSemester')?.value || '5', 10);

  if (!name || !email || !reg_no) {
    alert('Please fill in name, email, and registration number');
    return;
  }

  try {
    const res = await fetch('/admin/api/students', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, reg_no, semester })
    });
    const data = await res.json();
    if (res.ok) {
      document.getElementById('studentName').value = '';
      document.getElementById('studentEmail').value = '';
      document.getElementById('studentRegNo').value = '';
      await loadStudentsTable();
      await loadAdminStats();
      alert('Student added successfully');
    } else {
      alert(data.error || 'Failed to add student');
    }
  } catch (err) {
    console.error('Error adding student:', err);
    alert('Network error while adding student');
  }
}

async function deleteStudent(studentId, studentName) {
  if (!confirm(`Are you sure you want to delete student "${studentName}"? This will permanently remove their records, marks, and analytics.`)) {
    return;
  }

  try {
    const res = await fetch(`/admin/api/students/${studentId}`, {
      method: 'DELETE'
    });
    const data = await res.json();
    if (res.ok && data.success) {
      await loadStudentsTable();
      await loadAdminStats();
    } else {
      alert(data.error || 'Failed to delete student');
    }
  } catch (err) {
    console.error('Error deleting student:', err);
    alert('Network error while deleting student');
  }
}

async function uploadMarks() {
  const examType = document.getElementById('examTypeSelect')?.value;
  const fileInput = document.getElementById('csvUpload');
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
    alert('Please select a CSV file');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('exam_type', examType);

  try {
    const res = await fetch('/admin/api/upload-marks', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Marks uploaded successfully! Processed: ${data.marks_processed || 0}`);
      fileInput.value = '';
      await loadAdminStats();
    } else {
      alert(data.error || 'Failed to upload marks');
    }
  } catch (e) {
    console.error('Error uploading marks:', e);
    alert('Failed to upload marks');
  }
}

async function runAnalysis() {
  const examType = document.getElementById('analysisExamSelect')?.value || 'ISA';
  const statusEl = document.getElementById('analysisStatus');
  if (statusEl) {
    statusEl.style.display = 'block';
    statusEl.textContent = `Running ML clustering and analysis for ${examType}...`;
  }

  try {
    const res = await fetch(`/admin/api/run-analysis/${examType}`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      if (statusEl) {
        statusEl.textContent = `Analysis complete! Processed ${data.insights_created || 0} students.`;
      }
      await loadClusterDistribution(examType);
      await loadAtRiskStudents(examType);
      await loadAdminStats();
    } else {
      if (statusEl) statusEl.textContent = data.error || 'Analysis failed';
    }
  } catch (e) {
    console.error('Error running analysis:', e);
    if (statusEl) statusEl.textContent = 'Analysis failed due to a network error';
  }
}

async function loadClusterDistribution(examType) {
  try {
    const label = document.getElementById('clusterExamLabel');
    if (label) label.textContent = examType;

    const res = await fetch(`/admin/api/cluster-distribution/${examType}`);
    if (!res.ok) return;
    const data = await res.json();

    const topper = document.getElementById('topperCount');
    const average = document.getElementById('averageCount');
    const atRisk = document.getElementById('atRiskCount');

    if (topper) topper.textContent = data.Topper || 0;
    if (average) average.textContent = data.Average || 0;
    if (atRisk) atRisk.textContent = data['At-Risk'] || 0;

    const canvas = document.getElementById('clusterChart');
    if (!canvas) return;

    if (clusterChartInstance) {
      clusterChartInstance.destroy();
    }

    clusterChartInstance = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Topper', 'Average', 'At-Risk'],
        datasets: [{
          data: [data.Topper || 0, data.Average || 0, data['At-Risk'] || 0],
          backgroundColor: ['#4f46e5', '#9CA3AF', '#F472B6'],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false }
        }
      }
    });
  } catch (e) {
    console.error('Error loading cluster distribution:', e);
  }
}

async function loadAtRiskStudents(examType) {
  try {
    const label = document.getElementById('atRiskExamLabel');
    if (label) label.textContent = examType;

    const res = await fetch(`/admin/api/at-risk-students/${examType}`);
    if (!res.ok) return;
    const students = await res.json();

    const tbody = document.getElementById('atRiskTable');
    if (!tbody) return;

    if (students.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="padding: 12px; text-align: center; color: var(--secondary-text);">No at-risk students</td></tr>';
      return;
    }

    tbody.innerHTML = students.map(s => `
      <tr style="border-bottom: 1px solid var(--card-border);">
        <td style="padding: 12px; font-weight: 600;">${escapeHtml(s.name)}</td>
        <td style="padding: 12px;">${escapeHtml(s.reg_no)}</td>
        <td style="padding: 12px; color: var(--rose);">${(s.weak_subjects || []).join(', ') || '—'}</td>
        <td style="padding: 12px;">${Math.round(s.avg_score || 0)}</td>
        <td style="padding: 12px;"><span class="badge badge-danger">${escapeHtml(s.risk_level || 'At-Risk')}</span></td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Error loading at-risk students:', e);
  }
}

async function loadStudentMarksForEntry() {
  const studentId = document.getElementById('entryStudentSelect')?.value;
  const examType = document.getElementById('entryExamType')?.value;
  const tbody = document.getElementById('entryMarksTableBody');

  if (!studentId || !tbody) {
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" style="padding: 12px; text-align: center; color: var(--secondary-text);">Select a student to load marks</td></tr>';
    return;
  }

  try {
    const res = await fetch(`/admin/api/marks/${examType}/${studentId}`);
    if (!res.ok) return;
    const marks = await res.json();

    if (marks.length === 0) {
      tbody.innerHTML = '';
      addEntryRow();
      return;
    }

    tbody.innerHTML = marks.map(m => `
      <tr style="border-bottom: 1px solid var(--card-border);">
        <td style="padding: 8px;"><input type="text" class="entry-subject" value="${escapeHtml(m.subject)}" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
        <td style="padding: 8px;"><input type="number" class="entry-score" value="${m.score}" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
        <td style="padding: 8px;"><input type="number" class="entry-max" value="${m.max_score}" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
        <td style="padding: 8px; text-align: center;"><button type="button" onclick="this.closest('tr').remove()" style="background: none; border: none; color: var(--rose); cursor: pointer; font-size: 14px;">✕</button></td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Error loading marks for entry:', e);
  }
}

function addEntryRow() {
  const tbody = document.getElementById('entryMarksTableBody');
  if (!tbody) return;

  const tr = document.createElement('tr');
  tr.style.borderBottom = '1px solid var(--card-border)';
  tr.innerHTML = `
    <td style="padding: 8px;"><input type="text" class="entry-subject" placeholder="Subject Name" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
    <td style="padding: 8px;"><input type="number" class="entry-score" placeholder="Score" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
    <td style="padding: 8px;"><input type="number" class="entry-max" placeholder="Max" value="10" style="width: 100%; padding: 6px; border: 1px solid var(--card-border); border-radius: 6px;" /></td>
    <td style="padding: 8px; text-align: center;"><button type="button" onclick="this.closest('tr').remove()" style="background: none; border: none; color: var(--rose); cursor: pointer; font-size: 14px;">✕</button></td>
  `;
  tbody.appendChild(tr);
}

async function saveEntryMarks() {
  const studentId = document.getElementById('entryStudentSelect')?.value;
  const examType = document.getElementById('entryExamType')?.value;

  if (!studentId || !examType) {
    alert('Please select both a student and an exam type');
    return;
  }

  const rows = document.querySelectorAll('#entryMarksTableBody tr');
  const marks = [];

  rows.forEach(r => {
    const subject = r.querySelector('.entry-subject')?.value?.trim();
    const score = r.querySelector('.entry-score')?.value;
    const max = r.querySelector('.entry-max')?.value;

    if (subject) {
      marks.push({
        subject: subject,
        score: score !== '' ? parseFloat(score) : 0,
        max_score: max !== '' ? parseFloat(max) : 100
      });
    }
  });

  try {
    const res = await fetch('/admin/api/marks/entry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: parseInt(studentId, 10),
        exam_type: examType,
        marks: marks
      })
    });
    const data = await res.json();
    if (res.ok) {
      alert('Marks saved successfully!');
      await loadAdminStats();
    } else {
      alert(data.error || 'Failed to save marks');
    }
  } catch (e) {
    console.error('Error saving marks:', e);
    alert('Failed to save marks');
  }
}

function switchAdminTab(tabName) {
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.admin-tab').forEach(v => v.classList.remove('active'));
  
  const activeTab = document.getElementById(`tab-admin-${tabName}`);
  const activeView = document.getElementById(`admin-${tabName}`);
  
  if (activeTab) activeTab.classList.add('active');
  if (activeView) activeView.classList.add('active');
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
